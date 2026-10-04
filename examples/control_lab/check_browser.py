"""Headless end-to-end checks of the actual educational interface.

Start the lab, then: python -m examples.control_lab.check_browser --base-url http://127.0.0.1:8876
Add --live only when its configured Strata backend is available.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8876')
    parser.add_argument('--output', default='docs/control-lab-evidence/browser')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    results, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1040}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        def open_page(name):
            page.goto(args.base_url + '/lab/' + name)
            expect(page.locator('#run')).to_be_enabled()
            expect(page.locator('#eyebrow')).not_to_be_empty()
        def run():
            page.locator('#run').click()
            page.wait_for_function("() => ['Completed','Failed'].includes(document.getElementById('status').textContent)", timeout=180000)
            assert page.locator('#status').inner_text() == 'Completed', page.locator('#result').inner_text()[:1000]
            expect(page.locator('#download')).to_be_enabled()
        for name in ['choice', 'boolean', 'score', 'candidates', 'controller', 'rerank', 'graph', 'scene', 'wire', 'speculation', 'performance']:
            open_page(name)
            run()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), name
            if name in ['choice', 'candidates', 'controller', 'graph', 'scene', 'speculation', 'performance']:
                page.screenshot(path=str(output / (name + '.png')), full_page=True)
            if name == 'candidates':
                page.screenshot(path=str(output / 'preview.png'), full_page=False)
            results.append({'case': name, 'mode': 'recorded', 'status': 'passed'})
        for name in ['choice', 'boolean', 'score']:
            open_page(name)
            page.locator('#input-strategy').select_option('fast')
            run()
            page.locator('#score-view').select_option('raw_probability')
            assert page.locator('#distribution-bars').inner_text()
            results.append({'case': name + '-fast-and-raw', 'status': 'passed'})
        open_page('controller')
        for next_state in ['inspected', 'edited', 'verified', 'done']:
            run()
            page.locator('#apply-step').click()
            expect(page.locator('#input-controller_state')).to_have_value(next_state)
        results.append({'case': 'four-step-controller', 'status': 'passed'})
        open_page('candidates')
        run()
        page.locator('#path-select').select_option('3')
        page.locator('#path-tokens .token').last.click()
        assert 'raw logprob' in page.locator('#path-tokens').inner_text()
        with page.expect_download() as download:
            page.locator('#download').click()
        downloaded = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
        assert len(downloaded['result']['groups']) == 2
        results.append({'case': 'multi-token-inspection-and-export', 'status': 'passed'})
        for case in ['decision', 'router', 'ambiguity', 'stream', 'grammar', 'json-schema', 'reasoning-json', 'tool-call', 'tool-result', 'selected-only']:
            open_page('wire')
            page.locator('#input-case').select_option(case)
            run()
            results.append({'case': 'wire-' + case, 'status': 'passed'})
        open_page('choice')
        page.locator('#input-state').fill('This changed example has no recording. <script>alert(1)</script>')
        page.locator('#run').click()
        expect(page.locator('#status')).to_have_text('Failed')
        assert 'No native recording matches' in page.locator('#result').inner_text()
        page.locator('#reset').click()
        run()
        results.append({'case': 'recorded-miss-and-reset', 'status': 'passed'})
        if args.live:
            open_page('graph')
            page.locator('#mode').select_option('live')
            page.locator('#run').click()
            expect(page.locator('#stop')).to_be_enabled()
            page.wait_for_timeout(600)
            page.locator('#stop').click()
            expect(page.locator('#status')).to_have_text('Stopped')
            open_page('choice')
            page.locator('#mode').select_option('live')
            page.locator('#input-strategy').select_option('fast')
            run()
            results.append({'case': 'live-cancel-drain-next-request', 'status': 'passed'})
        page.set_viewport_size({'width': 390, 'height': 844})
        for name in ['choice', 'candidates', 'controller', 'graph', 'scene', 'speculation', 'performance']:
            open_page(name)
            run()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), name
        page.screenshot(path=str(output / 'mobile.png'), full_page=True)
        results.append({'case': 'seven-mobile-layouts-390px', 'status': 'passed'})
        assert not errors, errors
        browser.close()
    receipt = {'browser': 'Playwright Chromium, headless', 'checks': results, 'page_errors': errors}
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
