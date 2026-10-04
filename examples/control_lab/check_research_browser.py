"""Headless UI qualification. Point at an offline lab whose model URL is unreachable."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

PAGES=['samplers','sampler-sandbox','tictactoe','chess','poker','thermal','scheduler','context',
       'observer','calibration','information','search','frontier','research-map']
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url',default='http://127.0.0.1:8877')
    p.add_argument('--expect-offline',action='store_true',help='Assert that Live model fails to connect before testing recorded replay')
    p.add_argument('--output',default='docs/control-lab-evidence/research-browser');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);results=[];errors=[];outside=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1500,'height':1060},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
            if not r.request.url.startswith(a.base_url+'/'):outside.append(r.request.url);r.abort()
            else:r.continue_()
        page.route('**/*',route)
        page.goto(a.base_url);expect(page.locator('.experiment-card')).to_have_count(25)
        page.screenshot(path=str(out/'index-desktop.png'),full_page=True)
        page.screenshot(path=str(out/'index-preview.png'))
        page.locator('[data-filter="control"]').click();expect(page.locator('.experiment-card')).to_have_count(7)
        page.locator('#search').fill('chess');expect(page.locator('.experiment-card')).to_have_count(1)
        page.locator('#search').fill('no-such-experiment');expect(page.locator('#empty')).to_be_visible()
        page.locator('#search').fill('');page.locator('[data-filter="all"]').click()
        page.locator('#motion').click();expect(page.locator('#motion')).to_have_attribute('aria-pressed','true')
        page.locator('#motion').click();results.append(dict(case='gallery-filter-search-motion',status='passed'))
        def run(name):
            page.goto(a.base_url+'/lab/'+name);expect(page.locator('#eyebrow')).not_to_be_empty()
            page.locator('#run').click()
            page.wait_for_function("() => ['Completed','Failed'].includes(document.getElementById('status').textContent)",timeout=180000)
            assert page.locator('#status').inner_text()=='Completed',(name,page.locator('#result').inner_text()[:900])
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),name
            if name in ['sampler-sandbox','frontier','research-map']:
                assert 'No model requests in this run' in page.locator('#timeline').inner_text()
        if a.expect_offline:
            page.goto(a.base_url+'/lab/choice');page.locator('#mode').select_option('live');page.locator('#run').click()
            expect(page.locator('#status')).to_have_text('Failed',timeout=30000)
            assert 'connect' in page.locator('#result').inner_text().lower()
            results.append(dict(case='live-connection-unavailable-confirmed',status='passed'))
            page.locator('#mode').select_option('recorded')
        for name in PAGES:
            run(name)
            if name in ['samplers','thermal','research-map','tictactoe','chess','sampler-sandbox']:
                page.screenshot(path=str(out/(name+'.png')),full_page=True)
            if name=='samplers':
                for i in range(9):
                    page.locator('#recipe-view').select_option(str(i));page.locator('[data-native-token]').last.click()
                    assert page.locator('.stage-train').inner_text()
            if name=='sampler-sandbox':
                for mode in ['minp','reverse','sigma','xtc','xtc-reverse','dry','dynamic','mirostat']:
                    page.locator('#sandbox-recipe').select_option(mode);assert page.locator('#sandbox-output').inner_text()
                page.locator('#sandbox-recipe').select_option('minp')
                before=page.locator('#sandbox-output').inner_text()
                page.locator('#sandbox-heat').fill('0.3');page.locator('#sandbox-heat').dispatch_event('input')
                assert page.locator('#sandbox-output').inner_text()!=before
            if name in ['tictactoe','thermal','scheduler','observer']:
                before=page.locator('#trace-position').inner_text();page.locator('#trace-next').click()
                assert page.locator('#trace-position').inner_text()!=before
                page.locator('#trace-back').click();expect(page.locator('#trace-position')).to_have_text(before)
                page.locator('#trace-play').click();expect(page.locator('#trace-play')).to_have_text('Pause trace')
                page.locator('#trace-play').click();expect(page.locator('#trace-play')).to_have_text('Play trace')
            if name=='chess':
                page.locator('#chess-toggle').click();expect(page.locator('.move-square')).to_have_count(2)
            if name=='poker':
                page.locator('[data-hand="2"]').click();assert 'bet' in page.locator('#poker-hand').inner_text()
            if name=='context':page.locator('[data-context="2"]').click();assert 'CONTROLLER STATE v2' in page.locator('#context-run').inner_text()
            if name=='calibration':
                page.locator('#calibration-cut').fill('1');page.locator('#calibration-cut').dispatch_event('input')
                assert 'no retained cases' in page.locator('#coverage').inner_text()
            if name=='information':
                index=page.locator('#test-choice').input_value();page.locator('#test-choice').select_option(str((int(index)+1)%3))
                assert 'Counterfactual' in page.locator('#information-test').inner_text()
            if name=='search':
                page.locator('#search-cost').fill('1');page.locator('#search-cost').dispatch_event('input');expect(page.locator('.retained')).to_have_count(1)
            if name=='frontier':
                before=page.locator('#cost-estimate').inner_text();page.locator('#forward').fill('120');page.locator('#forward').dispatch_event('input')
                assert page.locator('#cost-estimate').inner_text()!=before
            if name=='research-map':
                page.locator('[data-branch="11"]').click();assert 'not implemented' in page.locator('#branch-detail').inner_text()
                for index in range(12,20):
                    page.locator(f'[data-branch="{index}"]').click();expect(page.locator('.proposal-protocol dt')).to_have_count(5)
                page.evaluate('scrollTo(0,0)')
                page.screenshot(path=str(out/'research-protocol.png'),full_page=True)
            with page.expect_download() as dl:page.locator('#download').click()
            receipt=json.loads(Path(dl.value.path()).read_text(encoding='utf-8'));assert receipt['experiment']==name
            results.append(dict(case=name+'-controls-export-offline',status='passed',requests=receipt['receipt']['requests']))
        # Real content at phone size, not just an empty responsive shell.
        page.set_viewport_size({'width':390,'height':844})
        page.goto(a.base_url);expect(page.locator('.experiment-card')).to_have_count(25)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(out/'index-mobile.png'),full_page=True)
        for name in ['samplers','tictactoe','chess','thermal','frontier','research-map']:
            run(name);page.screenshot(path=str(out/(name+'-mobile.png')),full_page=True)
            results.append(dict(case=name+'-390px',status='passed'))
        page.emulate_media(reduced_motion='reduce');page.goto(a.base_url)
        expect(page.locator('#motion')).to_have_attribute('aria-pressed','true')
        page.get_by_role('link',name='Enter the control room').focus();assert page.evaluate('document.activeElement.tagName')=='A'
        results.append(dict(case='reduced-motion-keyboard',status='passed'))
        assert not errors,errors;assert not outside,outside
        browser.close()
    (out/'results.json').write_text(json.dumps(dict(checks=results,console_errors=errors,external_requests=outside,
        model_server='live connection failure verified' if a.expect_offline else 'not checked',viewport_desktop=[1500,1060],viewport_mobile=[390,844]),indent=2),encoding='utf-8')
    print(f'{len(results)} browser checks passed; no console errors or external browser requests')
if __name__=='__main__':main()
