"""Binding/correlation tests complement real broker + ACME integration."""
import json
from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
from onem2m_client import OneM2MError,collector_client
from mqtt_client import primitive,response_content,topic_id,MQTTClient

class MQTTBindingTests(unittest.TestCase):
    def test_topic_id(self):
        self.assertEqual(topic_id('/id-mn'),'id-mn')
        self.assertEqual(topic_id('//sp/id/ae'),'sp:id:ae')
        for value in ('','/','C+bad','C#bad'):
            with self.assertRaises(ValueError):topic_id(value)
    def test_mapping(self):
        p=primitive('POST','mn/a','Cae','r1',{'m2m:cin':{'con':'x'}},4)
        self.assertEqual((p['op'],p['ty'],p['fr'],p['to'],p['rqi']),(1,4,'Cae','mn/a','r1'))
        self.assertEqual(p['pc'],{'m2m:cin':{'con':'x'}})
        self.assertEqual(primitive('PUT','mn/a','Cae','r2')['op'],3)
    def test_discovery_query_mapping(self):
        p=primitive('GET','mn?fu=1&ty=4&drt=1&lim=10000','Cae','r')
        self.assertEqual(p['fc'],{'fu':1,'ty':[4],'lim':10000});self.assertEqual(p['drt'],1)
        self.assertNotIn('?',p['to'])
    def test_unsupported_query_and_absolute_url_rejected(self):
        for path in ('https://other/mn','mn?unknown=1'):
            with self.assertRaises(ValueError):primitive('GET',path,'Cae','r')
    def test_error_mapping_preserves_retry_semantics(self):
        for rsc,status in ((4004,404),(4105,409),(4103,403),(4000,400)):
            with self.assertRaises(OneM2MError) as raised:response_content({'rsc':rsc})
            self.assertEqual(raised.exception.status,status);self.assertEqual(raised.exception.rsc,rsc)
    def test_nonfinal_and_malformed_responses_rejected(self):
        for value in ({},{'rsc':True},{'rsc':'2000'}):
            with self.assertRaises(ValueError):response_content(value)
        with self.assertRaises(RuntimeError):response_content({'rsc':1000})
    def test_success_returns_pc(self):
        self.assertEqual(response_content({'rsc':2001,'pc':{'m2m:cin':{'con':'x'}}}),{'m2m:cin':{'con':'x'}})
    def bare(self):
        client=MQTTClient.__new__(MQTTClient)
        client.origin='Cae';client.response_topic='/oneM2M/resp/Cae/id-mn/json'
        client.lock=threading.Lock();client.pending={'r':{'event':threading.Event()}}
        client.ready=threading.Event();client.ready.set()
        return client
    def test_wrong_topic_rqi_or_origin_ignored(self):
        client=self.bare()
        for topic,body in [('wrong',{'rqi':'r'}),(client.response_topic,{'rqi':'other'}),
                            (client.response_topic,{'rqi':'r','to':'other'}),(client.response_topic,{'rqi':'r','fr':'other'})]:
            client._message(None,None,SimpleNamespace(topic=topic,payload=json.dumps(body).encode()))
        self.assertFalse(client.pending['r']['event'].is_set())
        client._message(None,None,SimpleNamespace(topic=client.response_topic,payload=b'{'))
        self.assertFalse(client.pending['r']['event'].is_set())
    def test_matching_response_and_disconnect(self):
        client=self.bare()
        with patch.object(c,'MQTT_CSE_ID','/id-mn'):
            client._message(None,None,SimpleNamespace(topic=client.response_topic,payload=b'{"rqi":"r","rsc":2000,"fr":"/id-mn"}'))
        self.assertTrue(client.pending['r']['event'].is_set())
        client.pending['s']={'event':threading.Event()}
        client._disconnected(None,None,None,None,None)
        self.assertFalse(client.ready.is_set());self.assertIsInstance(client.pending['s']['error'],ConnectionError)
    def test_collector_mode_never_silently_falls_back(self):
        with patch.object(c,'COLLECTOR_PROTOCOL','mqtt'),patch.object(c,'ACP_ENABLED',False):
            with self.assertRaises(ValueError):collector_client()
        with patch.object(c,'COLLECTOR_PROTOCOL','invalid'):
            with self.assertRaises(ValueError):collector_client()
    def test_http_stays_default(self):
        with patch.object(c,'COLLECTOR_PROTOCOL','http'):
            self.assertNotIsInstance(collector_client(),MQTTClient)

    def test_publish_ack_is_not_a_oneM2M_response(self):
        client=self.bare();client.closed=False;client.pending={}
        client.mqtt=Mock();client.mqtt.publish.return_value=SimpleNamespace(rc=0)
        client.request_topic='/oneM2M/req/Cae/id-mn/json'
        with patch.object(c,'TIMEOUT',.01):
            with self.assertRaises(TimeoutError):client.call('GET','mn')
        self.assertEqual(client.pending,{})
    def test_persistent_connection_reused_by_adaptive_sender(self):
        import onem2m_client as module
        with patch.object(c,'ACP_ENABLED',True),patch.object(c,'COLLECTOR_PROTOCOL','mqtt'),patch.dict(module._collector_clients,{},clear=True),patch('mqtt_client.MQTTClient') as factory:
            self.assertIs(collector_client(),collector_client())
            factory.assert_called_once()
