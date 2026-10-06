"""Graph the saved 128K cohorts, leaving unmeasured points empty."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'results.json').read_text())
models = [('iq3_s', 'GSQ IQ3_S'), ('iq3_xxs', 'GSQ IQ3_XXS'), ('q2_0', 'GSQ Q2_0'),
          ('coder_iq1_m', 'Pruned Coder IQ1_M'), ('unsloth_iq1', 'Unsloth IQ1_M'),
          ('unsloth_q4', 'Unsloth Q4_K_XL'), ('q8', 'Unsloth Q8_0')]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'svg.fonttype': 'none'})
fig, axes = plt.subplots(1, 2, figsize=(12, 6), layout='constrained')
for policy, offset, color, label in [('nomtp', -.19, '#25679a', 'Non-MTP'), ('mtp', .19, '#b76418', 'Grouped MTP')]:
    for i, (model, _) in enumerate(models):
        case = next(c for c in data['cases'] if c['model'] == model and c['policy'] == policy and c['capacity'] == 8)
        point = next((r for r in case['runs'] if r['n'] == 8), None)
        for ax, metric in zip(axes, ['steady_decode', 'effective']):
            if point:
                bar = ax.barh(i + offset, point[metric], height=.34, color=color, label=label if i == 0 else None)
                ax.bar_label(bar, labels=[f'{point[metric]:.2f}' if metric == 'effective' else f'{point[metric]:.1f}'], padding=4, fontsize=9)
            else:
                ax.text(2 if metric == 'steady_decode' else .15, i + offset, 'N=8 deferred after N=4', va='center', fontsize=8, color=color)
for ax in axes:
    ax.set_yticks(range(len(models)), [label for _, label in models])
    ax.invert_yaxis()
    ax.set_axisbelow(True)
    ax.grid(axis='x', alpha=.18)
    ax.legend(loc='lower right', fontsize=9)
axes[0].set(title='Combined committed decode', xlabel='Output tokens / second of steady decode', xlim=(0, 360))
axes[1].set(title='Effective throughput, including every prefill', xlabel='Output tokens / full cohort seconds', xlim=(0, 18))
fig.suptitle('128K input + 512 output per request; eight concurrent requests\nFP16 KV - RTX PRO 6000 Blackwell 96 GB, 400 W', fontweight='bold')
fig.supxlabel('Initial measurements; no confidence intervals. Q4/Q8 placement and output differences are recorded.\nQ8 MTP original placement failed; adjusted placement completed only N=2/4 before the user stop.', fontsize=9)
for ext in ['png', 'svg']:
    fig.savefig(ROOT / ('overview.' + ext), dpi=160, bbox_inches='tight')
svg = ROOT / 'overview.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
