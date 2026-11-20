
import json,os,sys,threading,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
from dashboard import PAGE

@unittest.skipUnless(os.getenv('QF_RUN_UI')=='1','Set QF_RUN_UI=1 with Playwright Chromium installed')
class DashboardUI(unittest.TestCase):
    def test_cards_details_refresh_keyboard_and_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        machines=[]
        for i,status in enumerate(['normal','abnormal','unassessed','normal','normal'],1):
            machines.append({'collector_id':'collector-01','machine_id':f'machine-{i:02}', 'machine_name':f'\uba38\uc2e0 {i}',
              'section_id':'a' if i<=2 else 'b' if i<=4 else 'unassigned','section_name':'A \uad6c\uc5ed' if i<=2 else 'B \uad6c\uc5ed' if i<=4 else '\ubbf8\ubc30\uc815',
              'state':'ready','sensors':[{'sensor_id':'t','type':'temperature','label':'\uc628\ub3c4','unit':'°C'}],
              'telemetry':{'sample_id':f's{i}','timestamp':'2026-11-18T22:00:00+09:00','sensors':[{'sensor_id':'t','type':'temperature','label':'\uc628\ub3c4','unit':'°C','value':78 if status=='abnormal' else 42}]},
              'analysis':{'status':status,'method':'demo_threshold_rule','sensors':[{'sensor_id':'t','status':status}]}})
        payload={'machines':machines,'sections':[{'id':'a','name':'A \uad6c\uc5ed'},{'id':'b','name':'B \uad6c\uc5ed'},{'id':'unassigned','name':'\ubbf8\ubc30\uc815'}],'alerts':[],'updated_at':'2026-11-18T22:00:01+09:00','error':None}
        mode={'fail':False}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                body=PAGE.encode() if self.path=='/' else json.dumps({**payload,'error':'offline' if mode['fail'] else None},ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if self.path=='/' else 'application/json');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,executable_path=os.getenv('QF_CHROMIUM'))
                page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                expect(page.locator('.machine')).to_have_count(5)
                self.assertEqual(page.locator('.section').nth(0).locator('.machine').count(),2)
                self.assertEqual(page.locator('.section').nth(1).locator('.machine').count(),2)
                expect(page.locator('.section').nth(2)).to_contain_text('\ubbf8\ubc30\uc815')
                self.assertNotIn('78',page.locator('#sections').inner_text())
                self.assertNotIn('°C',page.locator('#sections').inner_text())
                self.assertEqual(page.locator('.machine.normal').count(),3)
                self.assertEqual(page.locator('.machine.abnormal').count(),1)
                page.get_by_role('button',name='\uba38\uc2e0 2 \xb7 \uc774\uc0c1 \uac10\uc9c0 \xb7 \uc0c1\uc138 \ubcf4\uae30',exact=True).click()
                expect(page.locator('#detail-title')).to_have_text('\uba38\uc2e0 2 \uc0c1\uc138')
                expect(page.locator('#detail-body')).to_contain_text('78')

                machines[1]['telemetry']['sensors'][0]['value']=79
                expect(page.locator('#detail-body .metric strong')).to_contain_text('79',timeout=6000)
                expect(page.locator('.machine[aria-pressed=true]')).to_have_count(1)
                expect(page.locator('#close')).to_be_focused()
                machines[1]['analysis_pending']=True
                machines[1]['analysis']['sample_id']='previous'
                machines[1]['analysis']['timestamp']='2026-11-18T21:59:59+09:00'
                expect(page.locator('.machine.abnormal')).to_have_count(1,timeout=6000)
                expect(page.locator('#detail-body')).to_contain_text('\ucd5c\uc2e0\uac12 \ubd84\uc11d \uc911',timeout=6000)
                expect(page.locator('#detail-body .metric')).not_to_have_class('metric abnormal')
                expect(page.locator('#detail-body')).to_contain_text('\ubd84\uc11d \ub300\uc0c1 \uce21\uc815 \uc2dc\uac01')
                machines[1]['analysis_delayed']=True
                expect(page.locator('#detail-body')).to_contain_text('\ubd84\uc11d \uc9c0\uc5f0',timeout=6000)
                expect(page.locator('.machine.abnormal')).to_have_count(1)
                machines[1]['analysis_delayed']=False
                machines[1]['analysis_pending']=False
                machines[1]['analysis']['sample_id']='s2'
                machines[1]['analysis']['status']='normal'
                expect(page.locator('.machine.normal')).to_have_count(4,timeout=6000)
                machines[1]['analysis']['status']='abnormal'
                expect(page.locator('.machine.abnormal')).to_have_count(1,timeout=6000)
                screenshot=os.getenv('QF_UI_SCREENSHOT')
                if screenshot:page.screenshot(path=screenshot,full_page=True)
                page.keyboard.press('Escape')
                expect(page.locator('#close')).to_be_hidden()
                expect(page.get_by_role('button',name='\uba38\uc2e0 2 \xb7 \uc774\uc0c1 \uac10\uc9c0 \xb7 \uc0c1\uc138 \ubcf4\uae30',exact=True)).to_be_focused()
                page.keyboard.press('Enter');expect(page.locator('#close')).to_be_visible()
                mode['fail']=True
                expect(page.locator('.machine.normal')).to_have_count(0,timeout=6000)
                expect(page.locator('#error')).to_be_visible()
                expect(page.locator('#detail-body')).to_contain_text('\ud604\uc7ac \uc0c1\ud0dc\ub97c \ud655\uc778\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.')
                mode['fail']=False
                page.set_viewport_size({'width':390,'height':844})
                page.reload();expect(page.locator('.machine')).to_have_count(5)
                page.get_by_role('button',name='\uba38\uc2e0 1 \xb7 \uc815\uc0c1 \xb7 \uc0c1\uc138 \ubcf4\uae30',exact=True).click()
                expect(page.locator('#detail-title')).to_have_text('\uba38\uc2e0 1 \uc0c1\uc138')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                if screenshot:page.screenshot(path=screenshot.replace('.png','-mobile.png'),full_page=True)
                self.assertEqual(errors,[])
                browser.close()
        finally:server.shutdown();server.server_close();thread.join()


