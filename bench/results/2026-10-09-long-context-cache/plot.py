"""Summarize collected tier runs and draw latency/storage figures.

python plot.py /path/to/raw-runs
Raw runs contain context-N/results.json, memory-samples.json and per-tier logs.
"""
import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
LABELS = ['fresh-replay', 'live-reuse', 'ram-restore', 'disk-restore-after-restart']
NAMES = ['Fresh replay', 'Live GPU reuse', 'Parked RAM', 'Disk after restart']
COLORS = ['#718096', '#16a085', '#2677c9', '#9a52c2']


def context_label(n):
    return '1M' if n == 1048576 else f'{n//1024}K'


def collect(root):
    summary = []
    for run in sorted(root.glob('context-*'), key=lambda p: int(p.name.split('-')[-1])):
        if not (run / 'results.json').exists():
            continue
        raw = json.loads((run / 'results.json').read_text())
        rows = {r['label']: dict(r) for r in raw['rows'] if r['label'] in LABELS}
        samples = json.loads((run / 'memory-samples.json').read_text()) if (run / 'memory-samples.json').exists() else []
        for label, row in rows.items():
            row['correct_code_order'] = [x.strip() for x in row['answer'].split('|')] == ['CEDAR-731', 'MARBLE-482', 'QUARTZ-956']
            log = (run / row['mode'] / (label + '-native.log')).read_text()
            match = re.search(r'prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\), (\d+) generated in (\d+) ms \(([\d.]+) tok/s\)', log)
            if match:
                row['native'] = dict(zip(['prompt_tokens', 'reused_tokens', 'new_tokens', 'prefill_ms', 'prefill_tps', 'generated', 'decode_ms', 'decode_tps'], map(float, match.groups())))
            phase_samples = [s for s in samples if s['mode'] == row['mode'] and s['phase'] == label]
            row['peak_rss_gib'] = max(s.get('rss_kib', 0) for s in phase_samples) / 1024**2 if phase_samples else None
            row['peak_vram_gib'] = max(s.get('gpu_mib', 0) for s in phase_samples) / 1024 if phase_samples else None
        hashes = {r['input_sha256'] for r in rows.values()}
        assert len(hashes) <= 1, ('tier prompts differ', run, hashes)
        snapshot = next((r['checkpoint_bytes'] for r in raw['rows'] if r['mode'] == 'disk' and r['label'] == 'seed-prefill'), None)
        ram_log = run / 'ram/distraction-native.log'
        parked = re.search(r'snapshot_bytes=(\d+)', ram_log.read_text()) if ram_log.exists() else None
        park_time = re.search(r'parked \d+ tokens in ([\d.]+) ms', ram_log.read_text()) if ram_log.exists() else None
        free = [s['disk_free_bytes'] for s in samples if 'disk_free_bytes' in s]
        identities = [json.loads((run / m / 'execution-identity.json').read_text()) for m in ['live', 'ram', 'disk']
                      if (run / m / 'execution-identity.json').exists()]
        if identities:
            assert all(v == identities[0] for v in identities), ('execution identities differ', run)
        summary.append(dict(tokens=raw['prefix_tokens'], rope=raw['rope'], rope_factor=raw['rope_factor'],
                            complete=(run / 'COMPLETE').exists(), snapshot_bytes=snapshot,
                            parked_ram_bytes=int(parked.group(1)) if parked else None,
                            park_outgoing_s=float(park_time.group(1))/1000 if park_time else None,
                            peak_rss_gib=raw.get('peak_rss_gib'), peak_vram_gib=raw.get('peak_gpu_gib'),
                            max_swap_kib=max((s.get('swap_kib', 0) for s in samples), default=0),
                            observed_filesystem_growth_gib=(max(free)-min(free))/1024**3 if free else None,
                            minimum_free_disk_gib=min(free)/1024**3 if free else None,
                            rows=rows, audits=raw['audits']))
    return summary


def plot(data):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.spines.left': False,
                         'axes.labelcolor': '#334155', 'text.color': '#172b46', 'savefig.facecolor': '#f7f9fc'})
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.3), facecolor='#f7f9fc')
    fig.subplots_adjust(top=.74, bottom=.22, left=.07, right=.97, wspace=.24)
    fig.text(.06, .93, 'LONG CONTEXT, FOUR WAYS TO RESUME', fontsize=22, weight='bold')
    fig.text(.06, .87, 'Same continuation • ISTA IQ3_XXS • FP16 KV • RTX PRO 6000 96 GB', fontsize=12)
    fig.text(.06, .82, 'First token and full request are different costs: disk admission happens after generation.', fontsize=11)
    x = np.arange(len(data))
    for ax, field, title in zip(axes, ['ttft_s', 'total_s'], ['Time to first token', 'Full request, including checkpoint save']):
        ax.set_facecolor('#f7f9fc')
        for j, (label, name, color) in enumerate(zip(LABELS, NAMES, COLORS)):
            y = [d['rows'].get(label, {}).get(field, np.nan) for d in data]
            ax.plot(x, y, 'o-', color=color, label=name, linewidth=2.5, markersize=7)
            for xi, yi in zip(x, y):
                if np.isfinite(yi):
                    ax.annotate(f'{yi:.2f}s' if yi < 10 else f'{yi:.1f}s', (xi, yi),
                                textcoords='offset points', xytext=(0, 9 if j % 2 == 0 else -15),
                                ha='center', fontsize=9, color=color)
        ax.set_yscale('log')
        measured = [d['rows'][k][field] for d in data for k in LABELS if k in d['rows'] and d['rows'][k][field] is not None]
        if measured:
            ax.set_ylim(min(measured)*.65, max(measured)*1.7)
        ax.set_ylabel('Seconds · logarithmic scale')
        ax.set_xticks(x, [context_label(d['tokens']) for d in data])
        ax.set_title(title, loc='left', pad=20, weight='bold')
        ax.grid(axis='y', which='major', alpha=.15)
        ax.set_xlim(-.25, max(.75, len(data)-.75))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .10), ncol=4, frameon=False)
    fig.text(.06, .055, 'One observation per size/path; no percentile estimates. OS page cache not flushed; process startup excluded.\n128K/256K ordinary RoPE; 512K YaRN 2×; 1M YaRN 4×. MTP width 4. Retrieval answers retained in raw data.', fontsize=9, color='#526479')
    for suffix in ['png', 'svg']:
        fig.savefig(HERE / ('latency.' + suffix), dpi=170)
    svg = HERE / 'latency.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.7), facecolor='#f7f9fc')
    fig.subplots_adjust(top=.73, bottom=.23, left=.07, right=.97, wspace=.25)
    fig.text(.06, .91, 'WHAT A LONG CONVERSATION COSTS TO KEEP', fontsize=22, weight='bold')
    fig.text(.06, .85, 'Checkpoint payload and whole-server memory are separate measurements.', fontsize=12)
    for j, (key, label, color) in enumerate([('snapshot_bytes', 'Disk snapshot', '#9a52c2'), ('parked_ram_bytes', 'Parked RAM snapshot', '#2677c9')]):
        y = [(d.get(key) or 0)/1024**3 for d in data]
        bars = axes[0].bar(x + (j-.5)*.32, y, width=.30, color=color, label=label)
        axes[0].bar_label(bars, labels=[f'{v:.2f}' for v in y], padding=4, fontsize=10)
    axes[0].set_title('One reusable checkpoint', loc='left', weight='bold', pad=16)
    for key, label, color in [('peak_rss_gib', 'Host RAM peak (server + engine RSS)', '#2677c9'), ('peak_vram_gib', 'VRAM peak (whole device)', '#16a085')]:
        y = [d.get(key, np.nan) for d in data]
        axes[1].plot(x, y, 'o-', label=label, color=color, linewidth=2.5)
        for xi, yi in zip(x, y):
            if yi is not None: axes[1].annotate(f'{yi:.1f}', (xi, yi), xytext=(0, -17 if key == 'peak_rss_gib' else 8), textcoords='offset points', ha='center', color=color)
    axes[1].set_title('Peak during the complete tier experiment', loc='left', weight='bold', pad=16)
    for ax in axes:
        ax.set_facecolor('#f7f9fc'); ax.set_ylabel('GiB (1 GiB = 2³⁰ bytes)')
        ax.set_xticks(x, [context_label(d['tokens']) for d in data]); ax.grid(axis='y', alpha=.15)
        ax.set_axisbelow(True); ax.legend(loc='upper left', bbox_to_anchor=(0, -.13), frameon=False, fontsize=10)
        ax.set_ylim(bottom=0, top=ax.get_ylim()[1]*1.15)
    fig.text(.06, .045, 'Payload excludes model files, history and temporary copies. Save/restore requires staging space.\nRAM/VRAM sampled at ~1 s; RSS includes mapped/shared pages. Fixed settings as in the latency chart.', fontsize=9, color='#526479')
    for suffix in ['png', 'svg']:
        fig.savefig(HERE / ('capacity.' + suffix), dpi=170)
    svg = HERE / 'capacity.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('raw', type=Path)
    args = ap.parse_args()
    data = collect(args.raw)
    (HERE / 'summary.json').write_text(json.dumps(data, indent=2))
    plot(data)
