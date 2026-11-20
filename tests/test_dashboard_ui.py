
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
            machines.append({'collector_id':'collector-01','machine_id':f'machine-{i:02}', 'machine_name':f'Machine {i}',
              'section_id':'a' if i<=2 else 'b' if i<=4 else 'unassigned','section_name':'Zone A' if i<=2 else 'Zone B' if i<=4 else 'Unassigned',
              'state':'ready','sensors':[{'sensor_id':'t','type':'temperature','label':'Temperature','unit':'°C'}],
              'telemetry':{'sample_id':f's{i}','timestamp':'2026-11-18T22:00:00+09:00','sensors':[{'sensor_id':'t','type':'temperature','label':'Temperature','unit':'°C','value':78 if status=='abnormal' else 42}]},
              'analysis':{'status':status,'method':'demo_threshold_rule','sensors':[{'sensor_id':'t','status':status}]}})
        payload={'machines':machines,'sections':[{'id':'a','name':'Zone A'},{'id':'b','name':'Zone B'},{'id':'unassigned','name':'Unassigned'}],'alerts':[],'updated_at':'2026-11-18T22:00:01+09:00','error':None}
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
                expect(page.locator('.section').nth(2)).to_contain_text('Unassigned')
                self.assertNotIn('78',page.locator('#sections').inner_text())
                self.assertNotIn('°C',page.locator('#sections').inner_text())
                self.assertEqual(page.locator('.machine.normal').count(),3)
                self.assertEqual(page.locator('.machine.abnormal').count(),1)
                page.get_by_role('button',name='Machine 2 \xb7 Anomaly detected \xb7 View details',exact=True).click()
                expect(page.locator('#detail-title')).to_have_text('Machine 2 Details')
                expect(page.locator('#detail-body')).to_contain_text('78')

                machines[1]['telemetry']['sensors'][0]['value']=79
                expect(page.locator('#detail-body .metric strong')).to_contain_text('79',timeout=6000)
                expect(page.locator('.machine[aria-pressed=true]')).to_have_count(1)
                expect(page.locator('#close')).to_be_focused()
                machines[1]['analysis_pending']=True
                machines[1]['analysis']['sample_id']='previous'
                machines[1]['analysis']['timestamp']='2026-11-18T21:59:59+09:00'
                expect(page.locator('.machine.abnormal')).to_have_count(1,timeout=6000)
                expect(page.locator('#detail-body')).to_contain_text('Analyzing latest data',timeout=6000)
                expect(page.locator('#detail-body .metric')).not_to_have_class('metric abnormal')
                expect(page.locator('#detail-body')).to_contain_text('Analyzed Measurement Time')
                machines[1]['analysis_delayed']=True
                expect(page.locator('#detail-body')).to_contain_text('Analysis delayed',timeout=6000)
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
                expect(page.get_by_role('button',name='Machine 2 \xb7 Anomaly detected \xb7 View details',exact=True)).to_be_focused()
                page.keyboard.press('Enter');expect(page.locator('#close')).to_be_visible()
                mode['fail']=True
                expect(page.locator('.machine.normal')).to_have_count(0,timeout=6000)
                expect(page.locator('#error')).to_be_visible()
                expect(page.locator('#detail-body')).to_contain_text('Current status is unavailable.')
                mode['fail']=False
                page.set_viewport_size({'width':390,'height':844})
                page.reload();expect(page.locator('.machine')).to_have_count(5)
                page.get_by_role('button',name='Machine 1 \xb7 Normal \xb7 View details',exact=True).click()
                expect(page.locator('#detail-title')).to_have_text('Machine 1 Details')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                if screenshot:page.screenshot(path=screenshot.replace('.png','-mobile.png'),full_page=True)
                self.assertEqual(errors,[])
                browser.close()
        finally:server.shutdown();server.server_close();thread.join()


