"""oneM2M TS-0010 JSON MQTT binding; QoS 1 is not an application response."""
import json
import ssl
import threading
import uuid
from urllib.parse import parse_qs, urlsplit
import config as c
from onem2m_client import Client, OneM2MError


def topic_id(value):
    result=value.lstrip('/').replace('/',':')
    if not result or any(x in result for x in ('+','#','\x00')):
        raise ValueError('Invalid oneM2M MQTT identifier')
    return result


def primitive(method,path,origin,rqi,body=None,ty=None):
    parsed=urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError('Expected a oneM2M resource path, not a URL')
    request={'op':{'POST':1,'GET':2,'PUT':3,'DELETE':4}[method],
             'to':parsed.path.lstrip('/'), 'fr':origin,'rqi':rqi,'rvi':'3'}
    if body is not None:request['pc']=body
    if ty is not None:request['ty']=ty
    for key,values in parse_qs(parsed.query).items():
        if key in ('ty','lbl','cnd'):
            request.setdefault('fc',{})[key]=[int(v) if key=='ty' else v for v in values]
        elif key in ('fu','lim','ofst'):
            request.setdefault('fc',{})[key]=int(values[0])
        elif key in ('drt','rcn'):
            request[key]=int(values[0])
        else:
            raise ValueError('Unsupported MQTT query parameter: '+key)
    return request


def response_content(response):
    rsc=response.get('rsc')
    if isinstance(rsc,bool) or not isinstance(rsc,int):
        raise ValueError('Missing or invalid oneM2M response status')
    if rsc>=4000:
        # Keep HTTP-compatible errors for ensure() and immutable CIN retry handling.
        status={4000:400,4004:404,4005:405,4103:403,4105:409,5000:500,5103:503}.get(rsc,400)
        class Response:
            status_code=status
            text=json.dumps(response.get('pc',{}),ensure_ascii=False)
        error=OneM2MError(Response())
        error.rsc=rsc
        raise error
    if rsc not in (2000,2001,2002,2004):
        raise RuntimeError(f'Unexpected non-final oneM2M response status {rsc}')
    return response.get('pc',{})


class MQTTClient(Client):
    def __init__(self,url,origin):
        super().__init__(url,origin)
        if not c.MQTT_CSE_ID.startswith('/'):
            raise ValueError('Set QF_MQTT_CSE_ID to the target CSE-ID including leading slash')
        import paho.mqtt.client as mqtt
        target=urlsplit(c.MQTT_URL)
        if target.scheme not in ('mqtt','mqtts') or not target.hostname or target.path not in ('','/') or target.query or target.fragment or target.username or target.password:
            raise ValueError('Use mqtt[s]://host[:port]; credentials belong in QF_MQTT_USERNAME/PASSWORD')
        if bool(c.MQTT_USERNAME)!=bool(c.MQTT_PASSWORD):
            raise ValueError('Set both MQTT username and password')
        sender,receiver=topic_id(origin),topic_id(c.MQTT_CSE_ID)
        if any(x in c.MQTT_TOPIC_PREFIX for x in ('+','#','\x00')):
            raise ValueError('MQTT topic prefix must not contain wildcards')
        prefix=c.MQTT_TOPIC_PREFIX+'/oneM2M'
        self.request_topic=f'{prefix}/req/{sender}/{receiver}/json'
        self.response_topic=f'{prefix}/resp/{sender}/{receiver}/json'
        self.ready=threading.Event();self.lock=threading.Lock();self.pending={}
        self.closed=False;self.subscribe_mid=None
        self.mqtt=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                              client_id='A::'+sender+'-'+uuid.uuid4().hex[:8], protocol=mqtt.MQTTv311)
        self.mqtt.on_connect=self._connected
        self.mqtt.on_subscribe=self._subscribed
        self.mqtt.on_disconnect=self._disconnected
        self.mqtt.on_message=self._message
        self.mqtt.reconnect_delay_set(min_delay=1,max_delay=15)
        if c.MQTT_USERNAME:self.mqtt.username_pw_set(c.MQTT_USERNAME,c.MQTT_PASSWORD)
        if target.scheme=='mqtts':
            self.mqtt.tls_set(ca_certs=c.MQTT_CA_FILE,cert_reqs=ssl.CERT_REQUIRED)
        self.mqtt.connect_async(target.hostname,target.port or (8883 if target.scheme=='mqtts' else 1883),keepalive=60)
        self.mqtt.loop_start()
    def _connected(self,client,userdata,flags,reason,properties):
        self.ready.clear()
        if reason.is_failure:return
        # SUBACK, rather than CONNACK alone, makes requests safe from response races.
        with self.lock:
            rc,self.subscribe_mid=client.subscribe(self.response_topic,qos=1)
            if rc!=0:self.subscribe_mid=None
    def _subscribed(self,client,userdata,mid,reasons,properties):
        with self.lock:
            if mid==self.subscribe_mid and reasons and all(not r.is_failure for r in reasons):self.ready.set()
    def _disconnected(self,client,userdata,flags,reason,properties):
        self.ready.clear()
        with self.lock:
            for entry in self.pending.values():
                if not entry['event'].is_set():
                    entry['error']=ConnectionError('MQTT connection lost before oneM2M response')
                    entry['event'].set()
    def _message(self,client,userdata,message):
        if message.topic!=self.response_topic or len(message.payload)>1048576:return
        try:
            response=json.loads(message.payload)
            if not isinstance(response,dict) or not isinstance(response.get('rqi'),str):return
            if response.get('to') not in (None,self.origin):return
            if response.get('fr') not in (None,c.MQTT_CSE_ID):return
        except (ValueError,UnicodeDecodeError):return
        with self.lock:
            entry=self.pending.get(response['rqi'])
            if entry is not None and not entry['event'].is_set():
                entry['response']=response;entry['event'].set()
    def call(self,method,path,body=None,ty=None,origin=None):
        if origin is not None and origin!=self.origin:
            raise ValueError('MQTT client may not change its Originator; provision AEs with HTTP first')
        if self.closed:raise RuntimeError('MQTT client is closed')
        if not self.ready.wait(c.TIMEOUT):raise TimeoutError('MQTT connection/subscription timeout')
        rqi=uuid.uuid4().hex
        entry={'event':threading.Event()}
        with self.lock:self.pending[rqi]=entry
        try:
            request=primitive(method,path,self.origin,rqi,body,ty)
            info=self.mqtt.publish(self.request_topic,json.dumps(request,ensure_ascii=False),qos=1,retain=False)
            if info.rc!=0:raise ConnectionError('MQTT publish failed')
            if not entry['event'].wait(c.TIMEOUT):raise TimeoutError('oneM2M MQTT response timeout')
            if 'error' in entry:raise entry['error']
            return response_content(entry['response'])
        finally:
            with self.lock:self.pending.pop(rqi,None)
    def close(self):
        if self.closed:return
        self.closed=True;self.ready.clear()
        self.mqtt.disconnect();self.mqtt.loop_stop()
        with self.lock:
            for entry in self.pending.values():
                entry['error']=ConnectionError('MQTT client closed');entry['event'].set()
