"""Separate configuration latency from logical refill bandwidth measurements."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parent
data = json.loads((root/'followup-summary.json').read_text())
plt.rcParams['svg.fonttype'] = 'none'
fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.0))
pairs = [next(p for p in data['pairs'] if p['candidate'] ==
    f'q8-i{n}-mtp-prefill16384') for n in [32768, 131072]]
x = np.arange(2)
for offset, key, label, color in [(-.19,'control_prefill_s','8K chunk','#526d85'),
                               (.19,'candidate_prefill_s','16K chunk','#008c80')]:
    bars = axes[0].bar(x+offset,[p[key] for p in pairs],.36,label=label,color=color)
    axes[0].bar_label(bars,fmt='%.2f',padding=3)
axes[0].set_xticks(x,['32K input','128K input'])
axes[0].set_ylabel('Prefill seconds (lower is better)')
axes[0].set_title('Q8: larger prefill chunks')
axes[0].set_ylim(0,38)
axes[0].legend(frameon=False)

rows = [next(r for r in data['rows'] if r['label'] ==
    f'q8-i32768-mtp-{task}-gpu-refill1') for task in ['code','editing']]
h2d = np.array([r['refill_logical_bytes']['primary_h2d']/1e9 for r in rows])
d2d = np.array([r['refill_logical_bytes']['secondary_d2d']/1e9 for r in rows])
axes[1].bar(x,h2d,.55,label='Primary refill H2D',color='#d88c4a')
axes[1].bar(x,d2d,.55,bottom=h2d,label='Secondary refill D2D',color='#008c80')
for i,r in enumerate(rows):
    axes[1].text(i,h2d[i]+d2d[i]+.5,
        f"{r['refill_logical_bytes']['replaced_primary_h2d_pct']:.1f}% D2D",
        ha='center',fontsize=11)
axes[1].set_xticks(x,['Code','Editing'])
axes[1].set_ylabel('Logical refill payload (decimal GB)')
axes[1].set_ylim(0,27)
axes[1].set_title('Q8: GPU refill reuse, blocking adaptation')
axes[1].legend(frameon=False,loc='upper left')
for ax in axes:
    ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y',alpha=.15)
fig.suptitle('RTX PRO 6000 Blackwell 96GB | Q8_0 | FP16 KV | MTP T4 | 1,024 output tokens',fontsize=13)
fig.text(.05,.025,'Initial observations. Chunk size changes numerical trajectory. Refill pairs match tokens/work.\n'
    'Refill counters exclude warm request; not total PCIe/DRAM traffic. Victim D2H remains. Profiles are separate.',
    fontsize=9,color='#444444')
fig.tight_layout(rect=(0,.11,1,.94))
fig.savefig(root/'q8-followup-wins.png',dpi=180)
fig.savefig(root/'q8-followup-wins.svg')
p=root/'q8-followup-wins.svg'
p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
