"""Plot the isolated branch's completed Q4 screen, without mixing historical runs."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
d = json.loads((ROOT / 'focused-receipt.json').read_text())
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none'})
fig, axes = plt.subplots(1, 2, figsize=(11, 5), layout='constrained')
for policy, color, label in [('mtp', '#1767a1', 'Grouped MTP'), ('nomtp', '#c46712', 'Non-MTP')]:
    c = next(c for c in d['cases'] if c['options']['model'] == 'unsloth_q4' and c['options']['policy'] == policy)
    for ax, metric in zip(axes, ['combined_decode', 'effective']):
        xs = [r['n'] for r in c['runs']]
        ys = [r[metric] for r in c['runs']]
        ax.plot(xs, ys, '-o', label=label, color=color, markerfacecolor='white', linewidth=2)
        for x, y in zip(xs, ys):
            above = (policy == 'mtp') if x < 8 else (policy == 'nomtp')
            ax.annotate(f'{y:.1f}', (x, y), xytext=(0, 9 if above else -17),
                        textcoords='offset points', ha='center', color=color, fontsize=10)
        ax.set_xticks([2, 4, 8]); ax.set_xlabel('Concurrent requests')
        ax.grid(alpha=.2); ax.set_xlim(1.5, 8.5)
axes[0].set_title('Combined committed decode'); axes[0].set_ylabel('Output tokens/s')
axes[0].set_ylim(0, 330)
axes[1].set_title('Effective throughput, including all prefills')
axes[1].set_ylim(0, 40)
axes[1].set_ylabel('Output tokens / full cohort seconds')
axes[0].legend(loc='lower right')
fig.suptitle('Q4 concurrent serving: isolated branch 4d56320\n32,768 input + 512 output per request, FP16 KV', fontweight='bold')
fig.supxlabel('RTX PRO 6000 Blackwell 96 GB, 400 W; all target experts in GPU memory.\n'
              'One screening run per point; no confidence intervals. Eight physical verifier rows.', fontsize=9)
for ext in ['png', 'svg']:
    fig.savefig(ROOT / ('q4-focused-32k.' + ext), dpi=160, bbox_inches='tight')
svg = ROOT / 'q4-focused-32k.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
