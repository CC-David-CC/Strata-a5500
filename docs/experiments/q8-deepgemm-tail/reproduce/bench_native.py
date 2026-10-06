"""Real routes/weights, synthetic activations; full MMQ vs DeepGEMM expert stage."""
from pathlib import Path
import ctypes
import json
import os
import statistics
import sys
import time
import numpy as np
os.environ['STRATA_DEEPGEMM_TAIL']='1'
os.environ.setdefault('CUDA_HOME','/usr/local/cuda')
os.environ['PATH']='/usr/local/cuda/bin:'+os.environ['PATH']
import torch
import deep_gemm as dg

ROOT = Path(__file__).resolve().parent
torch.set_num_threads(2)
torch.manual_seed(761)
torch.backends.cuda.matmul.allow_tf32 = False
torch.cuda.set_stream(torch.cuda.Stream())
lib = ctypes.CDLL(str(ROOT / 'native-prefill-components.so'))
P, I, L = ctypes.c_void_p, ctypes.c_int, ctypes.c_int64
for name, args, ret in [
    ('context_create', [], P), ('context_destroy', [P], None),
    ('activation_bytes', [I,I], ctypes.c_size_t),
    ('quantize', [P,P,I,I,P], None), ('product', [P,P,P,P,P,P,I,I,I,I,I,P], None),
    ('swiglu', [P,P,I,P], None), ('dequantize_bf16', [P,P,L,P], None),
    ('pack', [P,P,P,I,I,I,P], None), ('activation', [P,P,P,I,I,P], None),
    ('unpack', [P,P,P,I,I,I,P], None)]:
    fn = getattr(lib,name); fn.argtypes=args; fn.restype=ret

dg.set_mk_alignment_for_contiguous_layout(32)
lib.compact_pack.argtypes=[P,P,P,I,I,P];lib.compact_pack.restype=None
lib.compact_activation.argtypes=[P,P,P,I,P];lib.compact_activation.restype=None
lib.compact_unpack.argtypes=[P,P,P,I,I,P];lib.compact_unpack.restype=None

manifest = json.loads((ROOT / 'weights/manifest.json').read_text())
state = {'scope': 'Actual production tail groups at recorded layers; real Q8 weights and counts; synthetic activations',
    'excluded': 'Routing, incoming PCIe upload, common gather and final route-weighted combine are excluded from both arms. This is not request throughput.',
    'release_commit': '1cbcacbcae2953f3be9edc46369f0c875bc6ab8b',
    'deepgemm_commit': 'b64107f2b9599ca76445b7f62eedf66bae1d095b',
    'hardware': torch.cuda.get_device_name(), 'rows': [], 'started_unix': time.time()}

def save():
    filename='native-tail-stage-result.json'
    (ROOT/filename).write_text(json.dumps(state,indent=2)+'\n')

def metric(a, reference):
    delta=a.float()-reference
    return {'finite':bool(torch.isfinite(a).all()),'max_abs':delta.abs().max().item(),
            'rms_abs':delta.square().mean().sqrt().item(),
            'relative_rms':(delta.square().mean()/reference.square().mean().clamp_min(1e-30)).sqrt().item()}

flush_buffer=torch.empty(400*1024*1024,device='cuda',dtype=torch.uint8)

def measure(fn, cold=False):
    for _ in range(3): fn()
    torch.cuda.synchronize()
    stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream): fn()
    torch.cuda.current_stream().wait_stream(stream)
    graph=torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph,stream=stream):
        for _ in range(1 if cold else 16): fn()
    samples=[]
    for _ in range(5):
        a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
        if cold: flush_buffer.zero_()  # Larger than the GPU's 128 MiB L2.
        a.record();graph.replay();b.record();b.synchronize()
        samples.append(a.elapsed_time(b)*1000/(1 if cold else 16))
    return {'us_median':statistics.median(samples),'us_samples':samples,
            'cache_policy':'400 MiB device fill before each one-stage replay, outside timing' if cold else 'warm repeated graph'}

def load(experts, role, suffix):
    return torch.stack([torch.from_numpy(np.load(ROOT/'weights'/f'e{e}-{role}-{suffix}.npy'))
                        for e in experts]).cuda()

native_lib=ctypes.CDLL(str(ROOT/'native-tail.so'))
native_lib.dg_create.argtypes=[];native_lib.dg_create.restype=P
native_lib.dg_run.argtypes=[P,P,P,P,P,P];native_lib.dg_run.restype=I
native_lib.dg_destroy.argtypes=[P];native_lib.dg_destroy.restype=None
native_lib.dg_selected.argtypes=[P,I,I,L,L];native_lib.dg_selected.restype=I
dg_context=native_lib.dg_create();assert dg_context
dispatch_cases=[(8,4,1156,1464,True),(8,4,1170,3107,False),
                (8,2,128,256,False),(7,4,1156,1464,False),
                (8,4,511,600,False),(8,4,1537,1600,False),
                (8,4,1200,1600,True),(8,4,1200,1601,False),
                (8,4,1102,1167,False),(8,4,1397,1548,False),
                (8,4,646,667,True),(8,4,1200,1333,False),
                (8,4,1200,1334,True),(8,4,1200,2**63-1,False)]
for dtype,groups,maximum,total,expected in dispatch_cases:
    assert bool(native_lib.dg_selected(dg_context,dtype,groups,maximum,total))==expected
state['dispatch_cases_passed']=len(dispatch_cases)
context=lib.context_create()
try:
    # Matched group sizes and actual nonuniform row counts. Small decode-like
    # shapes are a sanity contrast; 128/512 and measured masks test earlier wins.
    cases=[(c['label'],c['experts'],c['counts']) for c in manifest['cases'] if len(c['experts'])==4]
    if '--profile-actual16' in sys.argv:
        cases=[case for case in cases if case[0]=='actual-16']
        state['profiled_timings_not_headline']=True
    for label, experts, counts in cases:
        groups=len(experts);rows=sum(counts);cap=(max(counts)+31)//32*32
        state.setdefault('dispatch',{})[label]=bool(native_lib.dg_selected(dg_context,8,groups,max(counts),rows))
        wgu=load(experts,'gate_up','f32');wd=load(experts,'down','f32')
        raw_gu=load(experts,'gate_up','q8');raw_dn=load(experts,'down','q8')
        # Native MMQ allows a read tail after its last expert, as the real path.
        raw_gu=torch.cat([raw_gu.flatten(),torch.zeros(4096,device='cuda',dtype=torch.uint8)])
        raw_dn=torch.cat([raw_dn.flatten(),torch.zeros(4096,device='cuda',dtype=torch.uint8)])
        x=torch.randn(rows,2560,device='cuda')*0.25
        x[-1].zero_()
        bounds=torch.tensor([0,*np.cumsum(counts).tolist()],device='cuda',dtype=torch.int32)
        ids=torch.arange(rows,device='cuda',dtype=torch.int32)
        count=torch.tensor(counts,device='cuda',dtype=torch.int32)
        ref=torch.empty(rows,2560,device='cuda')
        gu_reference=torch.empty(rows,1280,device='cuda')
        h_reference=torch.empty(rows,640,device='cuda')
        for e in range(groups):
            a,b=int(bounds[e]),int(bounds[e+1]);gu=x[a:b]@wgu[e].T
            gu_reference[a:b]=gu
            h_reference[a:b]=torch.nn.functional.silu(gu[:,:640])*gu[:,640:]
            ref[a:b]=h_reference[a:b]@wd[e].T
        xq=torch.empty(lib.activation_bytes(rows,2560),device='cuda',dtype=torch.uint8)
        hq=torch.empty(lib.activation_bytes(rows,640),device='cuda',dtype=torch.uint8)
        gu=torch.empty(rows,1280,device='cuda');h=torch.empty(rows,640,device='cuda')
        dn=torch.empty(rows,2560,device='cuda')
        wb_gu=torch.empty_like(wgu,dtype=torch.bfloat16);wb_dn=torch.empty_like(wd,dtype=torch.bfloat16)
        row_map=[];labels=[];original=0
        for e,c in enumerate(counts):
            padding=(-c)%32
            row_map.extend(range(original,original+c));row_map.extend([-1]*padding)
            labels.extend([e]*c+[-1]*padding);original+=c
        packed_rows=len(row_map)
        row_map=torch.tensor(row_map,device='cuda',dtype=torch.int32)
        labels=torch.tensor(labels,device='cuda',dtype=torch.int32)
        a_b=torch.empty(packed_rows,2560,device='cuda',dtype=torch.bfloat16)
        gu_b=torch.empty(packed_rows,1280,device='cuda',dtype=torch.bfloat16)
        h_b=torch.empty(packed_rows,640,device='cuda',dtype=torch.bfloat16)
        dn_b=torch.empty(packed_rows,2560,device='cuda',dtype=torch.bfloat16)
        out_b=torch.empty_like(dn)
        def convert_weights():
            stream=torch.cuda.current_stream().cuda_stream
            lib.dequantize_bf16(raw_gu.data_ptr(),wb_gu.data_ptr(),wgu.numel(),stream)
            lib.dequantize_bf16(raw_dn.data_ptr(),wb_dn.data_ptr(),wd.numel(),stream)
        convert_weights();torch.cuda.synchronize()
        assert torch.equal(wb_gu,wgu.bfloat16()) and torch.equal(wb_dn,wd.bfloat16()),'Q8 GPU decoder mismatch'
        def native():
            stream=torch.cuda.current_stream().cuda_stream
            lib.quantize(x.data_ptr(),xq.data_ptr(),2560,rows,stream)
            lib.product(context,raw_gu.data_ptr(),xq.data_ptr(),bounds.data_ptr(),ids.data_ptr(),gu.data_ptr(),groups,rows,max(counts),1280,2560,stream)
            lib.swiglu(gu.data_ptr(),h.data_ptr(),rows,stream)
            lib.quantize(h.data_ptr(),hq.data_ptr(),640,rows,stream)
            lib.product(context,raw_dn.data_ptr(),hq.data_ptr(),bounds.data_ptr(),ids.data_ptr(),dn.data_ptr(),groups,rows,max(counts),2560,640,stream)
        def deepgemm(convert):
            stream=torch.cuda.current_stream().cuda_stream
            if convert: convert_weights()
            lib.compact_pack(x.data_ptr(),a_b.data_ptr(),row_map.data_ptr(),packed_rows,2560,stream)
            dg.m_grouped_bf16_gemm_nt_contiguous(a_b,wb_gu,gu_b,labels,ensure_zero_padding=False)
            lib.compact_activation(gu_b.data_ptr(),h_b.data_ptr(),row_map.data_ptr(),packed_rows,stream)
            dg.m_grouped_bf16_gemm_nt_contiguous(h_b,wb_dn,dn_b,labels,ensure_zero_padding=False)
            lib.compact_unpack(dn_b.data_ptr(),out_b.data_ptr(),row_map.data_ptr(),packed_rows,2560,stream)
        def native_gu_deepgemm_down():
            stream=torch.cuda.current_stream().cuda_stream
            lib.quantize(x.data_ptr(),xq.data_ptr(),2560,rows,stream)
            lib.product(context,raw_gu.data_ptr(),xq.data_ptr(),bounds.data_ptr(),ids.data_ptr(),gu.data_ptr(),groups,rows,max(counts),1280,2560,stream)
            lib.swiglu(gu.data_ptr(),h.data_ptr(),rows,stream)
            lib.dequantize_bf16(raw_dn.data_ptr(),wb_dn.data_ptr(),wd.numel(),stream)
            lib.compact_pack(h.data_ptr(),h_b.data_ptr(),row_map.data_ptr(),packed_rows,640,stream)
            dg.m_grouped_bf16_gemm_nt_contiguous(h_b,wb_dn,dn_b,labels,ensure_zero_padding=False)
            lib.compact_unpack(dn_b.data_ptr(),out_b.data_ptr(),row_map.data_ptr(),packed_rows,2560,stream)
        cpp_out=torch.empty_like(dn)
        counts_native=(ctypes.c_int32*4)(*counts)
        def cpp_down(h_input):
            assert native_lib.dg_run(dg_context,raw_dn.data_ptr(),h_input.data_ptr(),ctypes.addressof(counts_native),cpp_out.data_ptr(),torch.cuda.current_stream().cuda_stream)==1
        def cpp_hybrid():
            stream=torch.cuda.current_stream().cuda_stream
            lib.quantize(x.data_ptr(),xq.data_ptr(),2560,rows,stream)
            lib.product(context,raw_gu.data_ptr(),xq.data_ptr(),bounds.data_ptr(),ids.data_ptr(),gu.data_ptr(),groups,rows,max(counts),1280,2560,stream)
            lib.swiglu(gu.data_ptr(),h.data_ptr(),rows,stream)
            cpp_down(h)
        native_gu_deepgemm_down();torch.cuda.synchronize()
        torch_hybrid=out_b.clone()
        cpp_hybrid();torch.cuda.synchronize()
        print(json.dumps({'cpp_vs_torch_hybrid':label,'error':metric(cpp_out,torch_hybrid),'exact':bool(torch.equal(cpp_out,torch_hybrid))}),flush=True)
        arms=[('native_prefill_q8_mmq',native,dn),
              ('deepgemm_bf16_streamed_conversion',lambda:deepgemm(True),out_b),
              ('deepgemm_bf16_preconverted',lambda:deepgemm(False),out_b),
              ('native_gu_deepgemm_down_streamed_conversion',native_gu_deepgemm_down,out_b),
              ('native_cpp_hybrid',cpp_hybrid,cpp_out)]
        for name,fn,out in arms:
            fn();torch.cuda.synchronize();error=metric(out,ref)
            assert error['finite'] and error['relative_rms']<0.04,error
            assert out[-1].abs().max().item()==0,'Zero row must stay zero'
            timing=measure(fn)
            row={'case':label,'experts':experts,'counts':counts,'arm':name,'layout':'compact aligned32 segments','packed_rows':packed_rows,'active_rows':rows,'error':error,**timing}
            row['cold']=measure(fn,cold=True)
            state['rows'].append(row);save();print(json.dumps(row),flush=True)
        if True:
            gu_component=torch.empty_like(gu_reference)
            def native_gu():
                stream=torch.cuda.current_stream().cuda_stream
                lib.quantize(x.data_ptr(),xq.data_ptr(),2560,rows,stream)
                lib.product(context,raw_gu.data_ptr(),xq.data_ptr(),bounds.data_ptr(),ids.data_ptr(),gu.data_ptr(),groups,rows,max(counts),1280,2560,stream)
            def dg_gu():
                stream=torch.cuda.current_stream().cuda_stream
                lib.dequantize_bf16(raw_gu.data_ptr(),wb_gu.data_ptr(),wgu.numel(),stream)
                lib.compact_pack(x.data_ptr(),a_b.data_ptr(),row_map.data_ptr(),packed_rows,2560,stream)
                dg.m_grouped_bf16_gemm_nt_contiguous(a_b,wb_gu,gu_b,labels,ensure_zero_padding=False)
                lib.compact_unpack(gu_b.data_ptr(),gu_component.data_ptr(),row_map.data_ptr(),packed_rows,1280,stream)
            def native_dn():
                stream=torch.cuda.current_stream().cuda_stream
                lib.quantize(h_reference.data_ptr(),hq.data_ptr(),640,rows,stream)
                lib.product(context,raw_dn.data_ptr(),hq.data_ptr(),bounds.data_ptr(),ids.data_ptr(),dn.data_ptr(),groups,rows,max(counts),2560,640,stream)
            def dg_dn():
                stream=torch.cuda.current_stream().cuda_stream
                lib.dequantize_bf16(raw_dn.data_ptr(),wb_dn.data_ptr(),wd.numel(),stream)
                lib.compact_pack(h_reference.data_ptr(),h_b.data_ptr(),row_map.data_ptr(),packed_rows,640,stream)
                dg.m_grouped_bf16_gemm_nt_contiguous(h_b,wb_dn,dn_b,labels,ensure_zero_padding=False)
                lib.compact_unpack(dn_b.data_ptr(),out_b.data_ptr(),row_map.data_ptr(),packed_rows,2560,stream)
            for name,fn,out,oracle in [('native_gu_component',native_gu,gu,gu_reference),('deepgemm_gu_component',dg_gu,gu_component,gu_reference),('native_down_component',native_dn,dn,ref),('deepgemm_down_component',dg_dn,out_b,ref),('native_cpp_down',lambda:cpp_down(h_reference),cpp_out,ref)]:
                fn();torch.cuda.synchronize();error=metric(out,oracle)
                assert error['finite'] and error['relative_rms']<0.04,error
                row={'case':label,'arm':name,'experts':experts,'counts':counts,'error':error,**measure(fn)}
                row['cold']=measure(fn,cold=True)
                state['rows'].append(row);save();print(json.dumps(row),flush=True)
        # Replay changed activations, then compare to an independently recomputed
        # oracle. Finite output alone would not detect stale captured pointers.
        graphs=[]
        for fn in [native, lambda:deepgemm(True), cpp_hybrid]:
            stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream): fn()
            torch.cuda.current_stream().wait_stream(stream)
            graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph,stream=stream): fn()
            graphs.append(graph)
        x.mul_(0.8)
        for graph in graphs: graph.replay()
        for e in range(groups):
            a,b=int(bounds[e]),int(bounds[e+1]);g=x[a:b]@wgu[e].T
            ref[a:b]=(torch.nn.functional.silu(g[:,:640])*g[:,640:])@wd[e].T
        torch.cuda.synchronize()
        mutation={'native':metric(dn,ref),'deepgemm':metric(out_b,ref),'native_cpp':metric(cpp_out,ref)}
        assert all(v['finite'] and v['relative_rms']<0.04 for v in mutation.values()),mutation
        state['rows'][-1]['graph_mutation_errors']=mutation
        save()
    state.update(completed=True,finished_unix=time.time());save()
finally:
    torch.cuda.synchronize()
    native_lib.dg_destroy(dg_context)
    lib.context_destroy(context)
