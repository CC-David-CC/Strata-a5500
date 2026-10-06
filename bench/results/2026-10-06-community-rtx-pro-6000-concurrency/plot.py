"""Regenerate the community overview from results.csv (requires matplotlib)."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent
rows = list(csv.DictReader((ROOT / 'results.csv').open(newline='', encoding='utf-8')))
models = [('q2_0', 'GSQ Q2_0'), ('iq3_xxs', 'GSQ IQ3_XXS'),
          ('iq3_s', 'GSQ IQ3_S'), ('coder_iq1_m', 'Pruned Coder IQ1_M'),
          ('unsloth_iq1', 'Unsloth IQ1_M'), ('unsloth_q4', 'Unsloth Q4_K_XL'),
          ('q8', 'Unsloth Q8_0')]
colors = {'nomtp': '#087f8c', 'mtp': '#e07935'}
ink, muted, grid = '#162c43', '#506176', '#e4eaf0'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'text.color': ink, 'axes.labelcolor': muted,
                     'xtick.color': muted, 'ytick.color': ink,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.spines.left': False, 'axes.spines.bottom': False,
                     'svg.fonttype': 'none'})
fig = plt.figure(figsize=(14, 11.5), facecolor='#f7f9fc')
gs = fig.add_gridspec(2, 2, left=.17, right=.975, bottom=.155, top=.76,
                      hspace=.35, wspace=.43)
fig.text(.04, .962, 'COMMUNITY MEASUREMENTS  /  EXPERIMENTAL STRATA',
         fontsize=10, fontweight='bold', color=colors['nomtp'])
fig.text(.04, .915, 'Flash-Next on RTX PRO 6000', fontsize=27, fontweight='bold')
fig.text(.04, .88, 'Eight concurrent requests  |  512 output tokens each  |  FP16 KV',
         fontsize=13, color=muted)
for x, value, label in [(.04, '320.9 tok/s', 'Peak combined streaming decode'),
                         (.39, '28.88 tok/s', 'Peak effective throughput, including prefill'),
                         (.80, '800 requests', 'Across 118 recorded cohorts')]:
    fig.text(x, .833, value, fontsize=20, fontweight='bold', color=ink)
    fig.text(x, .809, label, fontsize=9.5, color=muted)
fig.legend(handles=[Patch(color=colors['nomtp'], label='Non-MTP'),
                    Patch(color=colors['mtp'], label='Grouped MTP')],
           loc='upper right', bbox_to_anchor=(.974, .964), ncol=2,
           frameon=False, fontsize=11)

for ri, inp in enumerate([65536, 131072]):
    for ci, (metric, label, limit) in enumerate([
            ('aggregate_decode_tok_s', 'Streaming decode', 360),
            ('aggregate_effective_tok_s', 'Effective throughput', 34)]):
        ax = fig.add_subplot(gs[ri, ci], facecolor='white')
        ax.set_title(f'{inp // 1024}K input  /  {label}', loc='left',
                     fontsize=14, fontweight='bold', pad=18)
        for policy, offset in [('nomtp', -.20), ('mtp', .20)]:
            for i, (model, _) in enumerate(models):
                matching = [r for r in rows if r['model'] == model and r['policy'] == policy
                            and int(r['input_tokens_per_request']) == inp
                            and int(r['allocated_slots']) == 8 and int(r['requests']) == 8]
                assert len(matching) <= 1
                if not matching:
                    assert model == 'q8' and policy == 'mtp' and inp == 131072
                    ax.text(limit * .015, i + offset, 'N=8 unmeasured', va='center',
                            color=muted, fontsize=9, fontstyle='italic')
                    continue
                value = float(matching[0][metric])
                ax.barh(i + offset, value, height=.32, color=colors[policy], zorder=3)
                text = f'{value:.1f}' if ci == 0 else f'{value:.2f}'
                ax.text(value + limit * .014, i + offset, text, va='center',
                        fontsize=10, color=ink)
        ax.set_yticks(range(len(models)), [label for _, label in models])
        ax.tick_params(axis='both', length=0, pad=8)
        ax.set_ylim(len(models) - .4, -.6)
        ax.set_xlim(0, limit)
        ax.set_axisbelow(True)
        ax.grid(axis='x', color=grid, linewidth=.8)
        ax.set_xlabel('Aggregate output tokens / second', labelpad=10, fontsize=10)

fig.text(.04, .068, 'RTX PRO 6000 Blackwell Workstation 96 GB  /  400 W  /  Ryzen 9 7950X  /  128 GB RAM',
         fontsize=10, fontweight='bold')
fig.text(.04, .043, 'Measured fork cd9fcca; mostly one observation per point. Effective rates include all prefill; model loading is excluded.',
         fontsize=9, color=muted)
fig.text(.04, .021, 'Q4/Q8 placement and output differences are recorded. Q8 MTP at 128K completed N=2/4 after a cache change; N=8 was deferred.',
         fontsize=9, color=muted)
for ext in ['png', 'svg']:
    fig.savefig(ROOT / ('overview.' + ext), dpi=180, facecolor=fig.get_facecolor())
svg = ROOT / 'overview.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
