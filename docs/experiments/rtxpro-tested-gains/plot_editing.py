"""Initial editing measurements, separate from the code/context matrix."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parent
data = json.loads((root/'followup-summary.json').read_text())
rows = {r['label']:r for r in data['rows']}
models = [('q8','Unsloth Q8_0'),('q4','Unsloth UD-Q4_K_XL'),('iq3_s','GSQ-RCO IQ3_S')]
paths = ['plain','mtp','ngram','combined']
labels = ['Plain','MTP','Ngram','MTP +\nngram']
plt.rcParams['svg.fonttype'] = 'none'
fig,axes = plt.subplots(1,3,figsize=(14.5,5.2),sharey=True)
for ax,(model,name) in zip(axes,models):
    x = np.arange(4)
    for offset,arm,label,color in [(-.2,'stock','Stock 1.40','#526d85'),(.2,'combined','Combined','#008c80')]:
        values = [rows[f'{model}-i32768-editing-{path}-{arm}']['decode_tps'] for path in paths]
        bars = ax.bar(x+offset,values,.38,label=label,color=color)
        ax.bar_label(bars,fmt='%.1f',padding=3,fontsize=9)
    ax.set_title(name)
    ax.set_xticks(x,labels)
    ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y',alpha=.15)
axes[0].set_ylabel('Committed output tokens/s')
axes[0].set_ylim(0,275)
fig.legend(*axes[0].get_legend_handles_labels(), frameon=False,
           loc='upper center', bbox_to_anchor=(.5,.92), ncol=2)
fig.suptitle('Editing | 32,768 input + 1,024 output tokens | FP16 KV | RTX PRO 6000 Blackwell 96GB',fontsize=13)
fig.text(.055,.025,'One observation per arm; MTP T4, 8K prefill chunks. Q8 outputs/work differ.\n'
    'Q4 matches tokens/work; IQ3_S matches tokens, with ngram work differences. No quality score or confidence interval.',
    fontsize=9,color='#444444')
fig.tight_layout(rect=(0,.12,1,.87))
fig.savefig(root/'three-model-editing.png',dpi=180)
fig.savefig(root/'three-model-editing.svg')
p=root/'three-model-editing.svg'
p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
