"""Draw ordinary full-stage timings; no profiler/sanitizer timings included."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.rcParams['svg.fonttype'] = 'none'

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'stage-results.json').read_text())
rows = {(r['case'], r['arm']): r for r in data['rows']}
fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.6), sharey=True)
for ax, (case, title) in zip(axes, [
    ('tail-l7-p0', 'Skewed tail — selected'),
    ('tail-l3-p8192', 'Balanced contrast — excluded'),
]):
    for offset, arm, label, color in [
        (-0.18, 'native_prefill_q8_mmq', 'Native Q8 MMQ', '#536b84'),
        (0.18, 'native_cpp_hybrid', 'Native GU + DeepGEMM down', '#008b80'),
    ]:
        row = rows[case, arm]
        values = [row['us_median'], row['cold']['us_median']]
        bars = ax.bar([offset, 1 + offset], values, width=.34, color=color, label=label)
        ax.bar_label(bars, labels=[f'{v:.1f}' for v in values], padding=3, fontsize=10)
    ax.set_xticks([0, 1], ['Warm graph', 'Cold stage'])
    ax.set_title(title, fontsize=12)
    ax.set_ylim(0, 295)
    ax.grid(axis='y', alpha=.17)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_ylabel('Full expert stage (µs, lower is faster)')
fig.suptitle('9.4% less cold-stage time on a measured Q8 skewed tail', fontsize=15)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .10), ncol=2, frameon=False)
fig.text(.5, .035, 'RTX PRO 6000 Blackwell 96GB • five-sample medians • per-call conversion included\n'
         'Real expert weights / synthetic activations. Whole-request speedup not established.',
         ha='center', fontsize=9, color='#444444')
fig.tight_layout(rect=(0, .19, 1, .91))
fig.savefig(ROOT / 'stage-latency.png', dpi=180)
fig.savefig(ROOT / 'stage-latency.svg')
svg = ROOT / 'stage-latency.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
