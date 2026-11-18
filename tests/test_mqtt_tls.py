"""Real authenticated TLS broker and publish/subscribe ACL verification."""
import json,os,socket,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from tls_fixture import certificates

@unittest.skipUnless(os.getenv('QF_RUN_BROKER_TLS')=='1','Opt in to amqtt TLS integration')
class BrokerTLS(unittest.TestCase):
    def test_tls_password_and_topic_acl(self):
        import paho.mqtt.client as mqtt
        from passlib.hash import sha512_crypt
        with tempfile.TemporaryDirectory() as tmp:
            root=certificates(tmp)
            (root/'passwords').write_text('\n'.join(u+':'+sha512_crypt.hash('test-secret') for u in ('collector','monitor')))
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            config={'listeners':{'default':{'type':'tcp','bind':f'127.0.0.1:{port}','ssl':True,'certfile':str(root/'server.crt'),'keyfile':str(root/'server.key')}},'plugins':{
              'amqtt.plugins.authentication.FileAuthPlugin':{'password_file':str(root/'passwords')},
              'amqtt.plugins.topic_checking.TopicAccessControlListPlugin':{'publish_acl':{'collector':['qf/collector']},'acl':{'collector':['qf/collector'],'monitor':['qf/#']}}}}
            (root/'config.json').write_text(json.dumps(config))
            code='import asyncio,json,sys; from amqtt.broker import Broker\nasync def run():\n b=Broker(json.load(open(sys.argv[1]))); await b.start(); await asyncio.Event().wait()\nasyncio.run(run())'
            log=open(root/'broker.log','w+')
            process=subprocess.Popen([sys.executable,'-c',code,str(root/'config.json')],stdout=log,stderr=log)
            clients=[]
            def connect(user,password,ca=True):
                client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2);clients.append(client)
                done=threading.Event();result={}
                client.on_connect=lambda cl,ud,fl,rc,pr:(result.update(failed=rc.is_failure),done.set())
                client.on_disconnect=lambda cl,ud,fl,rc,pr:(result.update(failed=True),done.set())
                client.username_pw_set(user,password)
                client.tls_set(ca_certs=str(root/'ca.crt') if ca else None)
                client.connect('localhost',port);client.loop_start()
                self.assertTrue(done.wait(4));return client,result['failed']
            try:
                for _ in range(100):
                    try:
                        with socket.create_connection(('127.0.0.1',port),.1):break
                    except OSError:
                        if process.poll() is not None:log.seek(0);self.fail(log.read())
                        time.sleep(.05)
                bad,failed=connect('collector','wrong');self.assertTrue(failed);bad.disconnect()
                monitor,failed=connect('monitor','test-secret');self.assertFalse(failed)
                seen=[];received=threading.Event();subscribed=threading.Event()
                monitor.on_message=lambda cl,ud,msg:(seen.append(msg.topic),received.set())
                monitor.on_subscribe=lambda *args:subscribed.set()
                monitor.subscribe('qf/#',1);self.assertTrue(subscribed.wait(3))
                sender,failed=connect('collector','test-secret');self.assertFalse(failed)
                sender.publish('qf/collector','good',1);self.assertTrue(received.wait(3))
                received.clear();sender.publish('qf/other','forbidden',1)
                self.assertFalse(received.wait(.5));self.assertEqual(seen,['qf/collector'])
                denied=threading.Event();codes=[]
                sender.on_subscribe=lambda cl,ud,mid,rc,pr:(codes.extend(rc),denied.set())
                sender.subscribe('qf/other',1);self.assertTrue(denied.wait(3));self.assertTrue(codes[0].is_failure)
                with self.assertRaises(Exception):connect('collector','test-secret',False)
            finally:
                for client in clients:client.disconnect();client.loop_stop()
                process.terminate();process.wait(5);log.close()
