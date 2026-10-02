#!/usr/bin/env python3
"""Illustrative full-expert weight/transfer bounds; not a performance predictor.

Example: Q8, 4 verified / 3 emitted tokens, 25 unique experts per layer,
70% GPU hits, all remaining weights in RAM:
  python tools/full_expert_roofline.py --quant q8 --verified 4 --emitted 3 \
      --expert-union 25 --gpu-hit .7 --ram-hit 1 --draft-ms 1.2

Units are decimal GB, GB/s and milliseconds. KV/state/activation traffic, IOPS,
dequantization, launch overhead and real overlap must be measured separately.
"""
import argparse
import json


def model(quant, verified=1, emitted=1, expert_union=None, gpu_hit=1, ram_hit=1,
          gpu_gbs=1792, pcie_gbs=28.9, nvme_gbs=5, draft_ms=0,
          dense_gb=None, other_gpu_gb=0, disk_read_amplification=1,
          context_tokens=0):
    if quant not in ('q4', 'q8'):
        raise ValueError('quant must be q4 or q8')
    if not (verified >= emitted > 0 and verified >= 1):
        raise ValueError('require verified >= emitted > 0 and verified >= 1')
    if not (0 <= gpu_hit <= 1 and 0 <= ram_hit <= 1):
        raise ValueError('hit fractions must be in [0,1]')
    if min(gpu_gbs, pcie_gbs, nvme_gbs) <= 0 or min(draft_ms, other_gpu_gb) < 0:
        raise ValueError('bandwidth must be positive; costs cannot be negative')
    if disk_read_amplification < 1:
        raise ValueError('read amplification must be >= 1')
    if context_tokens < 0:
        raise ValueError('context tokens cannot be negative')
    union = min(512, 10 * verified) if expert_union is None else expert_union
    if not 10 <= union <= min(512, 10 * verified):
        raise ValueError('union must be between 10 and min(512,10*verified)')
    # Actual compatibility packs: Q4 adds 450,396,160 bytes and Q8 adds
    # 487,936,000 bytes to their GGUF dense weights. Both end at the same
    # read-every-step bytes; this includes one 2,720-byte input embedding row.
    dense_default, total_experts = {'q4': (5.28055312, 77.0179072),
                                   'q8': (5.28055312, 128.3457024)}[quant]
    dense = dense_default if dense_gb is None else dense_gb
    if dense < 0:
        raise ValueError('dense bytes cannot be negative')
    expert_gb = total_experts * union / 512
    h2d_gb = expert_gb * (1 - gpu_hit)
    disk_gb = h2d_gb * (1 - ram_hit) * disk_read_amplification
    # QSA has 12 layers. Int8 K/V plus FP16 scales use 12,672 bytes per
    # context cell across those layers. Attention selects at most 2,051
    # cells; the FP32 pooled indexer keys still scan 1,536 bytes/context cell.
    # These are ideal reads, not measured DRAM transactions or a full KV/
    # recurrent/activation accounting. Count candidate positions separately.
    attention_gb = verified * (12672 * min(context_tokens, 2051)
                               + 1536 * context_tokens) / 1e9
    gpu_gb = dense + expert_gb + h2d_gb + other_gpu_gb + attention_gb
    times = {'gpu_weight_and_supplied_other': 1000 * gpu_gb / gpu_gbs,
             'host_to_gpu': 1000 * h2d_gb / pcie_gbs,
             'nvme': 1000 * disk_gb / nvme_gbs}
    serial = sum(times.values()) + draft_ms
    overlap = max(times.values()) + draft_ms
    return {'quant': quant, 'verified_per_window': verified, 'emitted_per_window': emitted,
            'unique_experts_per_layer': union,
            'context_tokens': context_tokens,
            'known_attention_read_GB_per_window': attention_gb,
            'window_bytes_GB': {'gpu': gpu_gb, 'host_to_gpu': h2d_gb, 'nvme': disk_gb},
            'component_ms': times, 'draft_ms': draft_ms,
            'serialized_reference_tps': 1000 * emitted / serial,
            'ideal_overlap_reference_tps': 1000 * emitted / overlap,
            'notes': ['All-GPU Q8 reference is hypothetical on a 96 GB card.',
                      'Dense weights are assumed read once per verify window.',
                      'GPU bytes include H2D writes as well as expert reads.',
                      'Context option counts ideal selected int8 KV and pooled indexer reads only.',
                      'Recurrent state, activations, extra reads and dequantization are omitted.',
                      'PLE random-read latency/IOPS and CPU expert compute are not modeled.',
                      'Assumptions must be replaced by measured bytes, acceptance and overlap.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--quant', choices=['q4', 'q8'], default='q4')
    for name, default in [('verified',1),('emitted',1),('expert-union',None),
                          ('gpu-hit',1),('ram-hit',1),('gpu-gbs',1792),('pcie-gbs',28.9),
                          ('nvme-gbs',5),('draft-ms',0),('dense-gb',None),('other-gpu-gb',0),
                          ('disk-read-amplification',1),('context-tokens',0)]:
        p.add_argument('--'+name,type=float,default=default)
    args = p.parse_args()
    try:
        result = model(**vars(args))
    except ValueError as e:
        p.error(str(e))
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
