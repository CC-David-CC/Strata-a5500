from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent

from gguf import GGUFReader,GGMLQuantizationType
from gguf.quants import dequantize
folder=Path(sys.argv[1]).expanduser().resolve()
readers=[GGUFReader(str(p)) for p in sorted(folder.glob('*.gguf'))]
tensors={t.name:(p,t) for p in readers for t in p.tensors}
out=ROOT/'weights';out.mkdir(exist_ok=False)
manifest={'cases':[],'matrices':[],'oracle':'Independent Q8 scalar decoder exactly matches gguf.quants dequantize'}
for group in json.loads((ROOT/'selected-groups.json').read_text()):
 layer=group['layer'];experts=[]
 for expert in group['ids']:
  key=f'l{layer}-e{expert}';experts.append(key)
  for role in ('gate_up','down'):
   roles=['gate','up'] if role=='gate_up' else ['down']
   raw=np.concatenate([np.array(tensors[f'blk.{layer}.ffn_{a}_exps.weight'][1].data[expert],copy=True) for a in roles],axis=0)
   blocks=raw.reshape(-1,34)
   scales=blocks[:,:2].copy().view('<f2').astype(np.float32)
   values=blocks[:,2:].copy().view(np.int8).astype(np.float32)
   fp=(values*scales).reshape(raw.shape[0],raw.shape[1]//34*32)
   assert np.array_equal(fp,dequantize(raw,GGMLQuantizationType.Q8_0))
   np.save(out/f'e{key}-{role}-q8.npy',raw);np.save(out/f'e{key}-{role}-f32.npy',fp)
   manifest['matrices'].append({'key':key,'role':role,'shape':list(fp.shape),'sha256':hashlib.sha256(raw.tobytes()).hexdigest(),'scalar_oracle_exact':True})
 manifest['cases'].append({'label':f"tail-l{layer}-p{group['position']}",'experts':experts,'counts':group['counts'],'recorded_group':group})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest['cases']))
