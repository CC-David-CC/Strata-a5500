"""Check completed pages which make no inference request, using headless Chromium."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8877')
    parser.add_argument('--output',default='docs/control-lab-evidence/research-browser')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True);checks=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1500,'height':1060})
        for name in ['sampler-sandbox','frontier','research-map','speculation','controller']:
            page.goto(args.base_url+'/lab/'+name)
            if name=='controller':page.locator('#input-controller_state').select_option('done')
            page.locator('#run').click();expect(page.locator('#status')).to_have_text('Completed',timeout=30000)
            text=page.locator('#timeline').inner_text()
            assert 'No model requests in this run' in text and 'Preparing' not in text
            if name=='research-map':
                page.locator('[data-branch="19"]').click();page.evaluate('scrollTo(0,0)')
                page.screenshot(path=str(out/'research-protocol.png'),full_page=True)
            checks.append(dict(case=name+'-zero-request-receipt',status='passed'))
        browser.close()
    (out/'zero-request-results.json').write_text(json.dumps(dict(checks=checks),indent=2),encoding='utf-8')
    print('5 zero-request receipt checks passed')


if __name__=='__main__':main()
