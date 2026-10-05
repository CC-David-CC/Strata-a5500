"""Check archived payloads, rotation token/work equality and reported gains; no GPU needed."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).parent
manifest = json.loads((root / 'history-manifest.json').read_text())
summary = json.loads((root / 'summary.json').read_text())
archive = root / 'experiment-history.tar.gz'
assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == summary['raw_archive_sha256']
with tarfile.open(archive) as a:
    for m in manifest:
        if m.get('included') is False: continue
        raw = a.extractfile(m['path']).read()
        assert len(raw) == m['bytes']
        assert hashlib.sha256(raw).hexdigest() == m['sha256'], m['path']
    def read(name): return json.loads(a.extractfile(name).read())
    d = read('adaptation-no-rotation-20261005/q8-screen/result.json')
    assert d['completed']
    by_name = {r['label']: r for r in d['runs']}
    counters = ['generated', 'prompt_read', 'drafts_accepted', 'drafts_offered', 'reused',
                'hits', 'lookups', 'offloaded', 'ram_blobs', 'file_blobs', 'file_mb']
    for rep in range(2):
        off, on = (by_name[f'q8-32k-r{rep}-rot{rot}-layer1'] for rot in range(2))
        x, y = off['requests'][0], on['requests'][0]
        assert len(x['token_ids']) == len(y['token_ids']) == 1024
        assert x['token_ids'] == y['token_ids']
        assert all(x['timings'][k] == y['timings'][k] for k in counters)
        for k in ['async_counters', 'duplex_counters', 'resident_exchanges']:
            assert off[k] == on[k], k
        gain = 100 * (y['decode_tok_s'] / x['decode_tok_s'] - 1)
        assert 24 < gain < 29
        print(f'Rotation pair {rep}: {x["decode_tok_s"]:.3f} -> {y["decode_tok_s"]:.3f} tok/s; +{gain:.3f}%; exact token/work checks PASS')
    b = read('adaptation-publication-20261005/q8-screen/result.json')
    assert b['completed'] and len(b['runs']) == 4
    for c in b['comparisons']:
        print('Baseline comparison:', c)
print('Archive payload hashes and measured claims verified')
