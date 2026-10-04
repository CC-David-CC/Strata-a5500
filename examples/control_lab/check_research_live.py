"""Opt-in headless checks against the lab's already configured native server."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8876')
    parser.add_argument('--output',default='docs/control-lab-evidence/research-live-browser')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    errors=[];results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1500,'height':1060})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def complete():
            page.wait_for_function("() => ['Completed','Failed'].includes(document.getElementById('status').textContent)",timeout=180000)
            assert page.locator('#status').inner_text()=='Completed',page.locator('#result').inner_text()[:2000]
        def download(name):
            with page.expect_download() as pending:page.locator('#download').click()
            receipt=json.loads(Path(pending.value.path()).read_text(encoding='utf-8'))
            assert receipt['receipt']['mode']=='live'
            (out/name).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
            return receipt
        page.goto(args.base_url+'/lab/samplers');page.locator('#mode').select_option('live')
        page.locator('#input-state').fill('Choose a useful workshop tool for tightening a bolt. Answer with one word.')
        page.locator('#run').click();complete();receipt=download('samplers.json')
        assert len(receipt['result']['runs'])==9 and receipt['receipt']['requests']==9
        for index in [6,7,8]:
            page.locator('#recipe-view').select_option(str(index))
            assert 'VALID OUTPUTS FIRST' in page.locator('#sampler-run').inner_text()
        page.evaluate('scrollTo(0,0)')
        page.screenshot(path=str(out/'native-json-sampler.png'),full_page=True)
        results.append(dict(case='edited-live-prompt-nine-native-profiles-including-gbnf-json',status='passed'))
        page.goto(args.base_url+'/lab/graph');page.locator('#mode').select_option('live');page.locator('#run').click()
        expect(page.locator('#stop')).to_be_enabled();page.wait_for_timeout(600);page.locator('#stop').click()
        expect(page.locator('#status')).to_have_text('Stopped')
        results.append(dict(case='stop-active-native-workflow',status='passed'))
        page.goto(args.base_url+'/lab/choice');page.locator('#mode').select_option('live')
        page.locator('#input-strategy').select_option('fast');page.locator('#run').click();complete()
        receipt=download('next-ordinary-request.json');assert receipt['receipt']['requests']==1
        assert not any('strata_sampler' in call['request'] for call in receipt['receipt']['calls'])
        results.append(dict(case='next-ordinary-native-request-after-stop',status='passed'))
        assert not errors,errors
        browser.close()
    (out/'results.json').write_text(json.dumps(dict(checks=results,console_errors=errors),indent=2),encoding='utf-8')
    print(f'{len(results)} live browser checks passed')


if __name__=='__main__':main()
