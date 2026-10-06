"""Scientific figures from ordinary single-observation request measurements."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'matrix-summary.json').read_text())
rows = {(r['model'], r['input_tokens'], r['path'], r['arm']): r for r in data['rows']}
models = [('q8', 'Unsloth Q8_0'), ('q4', 'Unsloth UD-Q4_K_XL'), ('iq3_s', 'GSQ-RCO IQ3_S')]
paths = ['plain', 'mtp', 'ngram', 'combined']
labels = ['Plain', 'MTP', 'Ngram', 'MTP +\nngram']
colors = ['#526d85', '#008c80']
matplotlib.rcParams['svg.fonttype'] = 'none'

def save(fig, name):
    fig.savefig(ROOT / (name + '.png'), dpi=180)
    fig.savefig(ROOT / (name + '.svg'))
    p = ROOT / (name + '.svg')
    p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines()) + '\n')

fig, axes = plt.subplots(2, 3, figsize=(15.8, 8.4), sharey=True)
for y, tokens in enumerate([32768, 131072]):
    for x, (model, title) in enumerate(models):
        ax = axes[y, x]
        for offset, arm, legend, color in zip([-.18, .18], ['stock', 'combined'], ['Strata 1.40', 'Experimental stack'], colors):
            values = [rows[model, tokens, path, arm]['decode_tps'] for path in paths]
            bars = ax.bar(np.arange(4) + offset, values, width=.34, color=color, label=legend)
            ax.bar_label(bars, labels=[f'{n:.1f}' for n in values], fontsize=8.5, padding=3)
        ax.set_xticks(range(4), labels, fontsize=10)
        ax.set_title(f'{title}\n{tokens:,} input tokens', fontsize=12)
        ax.set_ylim(0, 340)
        ax.grid(axis='y', alpha=.16)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
        if x == 0: ax.set_ylabel('Committed output tokens/s')
fig.suptitle('Current Strata 1.40 vs the combined experimental stack', fontsize=17)
handles, legend = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, legend, ncol=2, frameon=False, loc='lower center', bbox_to_anchor=(.5, .065))
fig.text(.5, .018, 'RTX PRO 6000 Blackwell 96GB · 128GB RAM · FP16 KV · 8,192-token prefill chunks · 1,024 output tokens\n'
    'One observation per arm. Q8 token streams differ; Q4 and IQ3_S token streams match. Ngram work can differ. Quality not scored.',
    ha='center', fontsize=9)
fig.tight_layout(rect=(0, .12, 1, .94))
save(fig, 'three-model-decode')

fig, axes = plt.subplots(1, 2, figsize=(11.6, 5.0), sharey=True)
for ax, tokens in zip(axes, [32768, 131072]):
    for offset, arm, legend, color in zip([-.18, .18], ['stock', 'combined'], ['Strata 1.40', 'Experimental stack'], colors):
        values = [rows['q8', tokens, path, arm]['model_cpu_s'] for path in paths]
        bars = ax.bar(np.arange(4) + offset, values, width=.34, color=color, label=legend)
        ax.bar_label(bars, labels=[f'{n:.1f}' for n in values], fontsize=9, padding=3)
    ax.set_xticks(range(4), labels)
    ax.set_title(f'{tokens:,} input tokens')
    ax.grid(axis='y', alpha=.16)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_ylabel('Aggregate model CPU seconds/request\n(lower is less CPU work or waiting)')
fig.suptitle('Q8 uses less CPU across all four decoding paths', fontsize=16)
handles, legend = axes[0].get_legend_handles_labels()
fig.legend(handles, legend, ncol=2, frameon=False, loc='lower center', bbox_to_anchor=(.5, .07))
fig.text(.5, .025, 'Includes prefill and generation; excludes startup. Linux process CPU ticks, not energy or system-wide CPU.\n'
    '1,024 outputs/request; token streams and measured expert work differ. Single observations.', ha='center', fontsize=9)
fig.tight_layout(rect=(0, .18, 1, .93))
save(fig, 'q8-cpu-time')
