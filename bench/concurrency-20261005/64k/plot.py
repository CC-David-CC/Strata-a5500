"""Plot the completed 64K screen at equal eight-request concurrency."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'results.json').read_text())
models = [('iq3_s', 'GSQ IQ3_S'), ('iq3_xxs', 'GSQ IQ3_XXS'),
          ('q2_0', 'GSQ Q2_0'), ('coder_iq1_m', 'Pruned Coder IQ1_M'),
          ('unsloth_iq1', 'Unsloth IQ1_M'), ('unsloth_q4', 'Unsloth Q4_K_XL'),
          ('q8', 'Unsloth Q8_0')]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none'})
fig, axes = plt.subplots(1, 2, figsize=(12, 5.8), layout='constrained')
for policy, offset, color, label in [('nomtp', -.19, '#25679a', 'Non-MTP'),
                                     ('mtp', .19, '#b76418', 'Grouped MTP')]:
    points = []
    for model, _ in models:
        case = next(c for c in data['cases']
                    if c['model'] == model and c['policy'] == policy and c['capacity'] == 8)
        points.append(next(r for r in case['runs'] if r['n'] == 8))
    for ax, metric in zip(axes, ['steady_decode', 'effective']):
        values = [p[metric] for p in points]
        bars = ax.barh([i + offset for i in range(len(models))], values,
                       height=.34, color=color, label=label)
        ax.bar_label(bars, labels=[f'{v:.1f}' for v in values], padding=4, fontsize=9)
for ax in axes:
    ax.set_yticks(range(len(models)), [label for _, label in models])
    ax.invert_yaxis()
    ax.set_axisbelow(True)
    ax.grid(axis='x', alpha=.18)
    ax.legend(loc='lower right', fontsize=9)
axes[0].set_title('Combined committed decode')
axes[0].set_xlabel('Output tokens / second of steady decode')
axes[0].set_xlim(0, 370)
axes[1].set_title('Effective throughput, including every prefill')
axes[1].set_xlabel('Output tokens / full cohort seconds')
axes[1].set_xlim(0, 34)
fig.suptitle('64K input + 512 output per request; eight concurrent requests\n'
             'FP16 KV - RTX PRO 6000 Blackwell 96 GB, 400 W', fontweight='bold')
fig.supxlabel('One observation per configuration; no confidence intervals. Q4/Q8 use RAM experts and show output differences.\n'
              'Both policies use research engine cd9fcca. This is a policy comparison, not an upstream speedup measurement.', fontsize=9)
for ext in ['png', 'svg']:
    fig.savefig(ROOT / ('overview.' + ext), dpi=160, bbox_inches='tight')
svg = ROOT / 'overview.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
