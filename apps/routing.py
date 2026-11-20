
from contextlib import contextmanager
from functools import wraps
import fcntl,json,os
from pathlib import Path
import config as c
_controller=False

@contextmanager
def route_lock(exclusive=False):
    path=os.getenv('QF_ROUTE_FILE')
    if not path:yield;return
    with open(path+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def read_route():
    path=os.getenv('QF_ROUTE_FILE')
    if not path:return None
    with open(path) as source:value=json.load(source)
    from urllib.parse import urlsplit
    target=urlsplit(value['url'])
    if target.scheme not in ('http','https') or not target.hostname or not value['base'].strip('/'):
        raise ValueError('Invalid controlled MN route')
    return value

def atomic_write(path,value):
    import tempfile
    parent=Path(path).resolve().parent
    fd,temp=tempfile.mkstemp(dir=parent,prefix='.qf-route-')
    try:
        with os.fdopen(fd,'w') as out:json.dump(value,out);out.flush();os.fsync(out.fileno())
        os.replace(temp,path)
        directory=os.open(parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def guarded(function):
    @wraps(function)
    def run(*args,**kwargs):
        if _controller or not os.getenv('QF_ROUTE_FILE'):return function(*args,**kwargs)
        with route_lock():
            route=read_route();old=c.MN_URL
            c.MN_URL=route['url'].rstrip('/');c.MN_BASE=route['base'].strip('/')
            if route.get('cse_id'):c.MQTT_CSE_ID=route['cse_id']
            if route.get('mqtt_url'):c.MQTT_URL=route['mqtt_url']
            clients=list(args)
            if clients and hasattr(clients[0],'url'):
                if hasattr(clients[0],'mqtt'):
                    from onem2m_client import collector_client
                    clients[0]=collector_client()
                else:clients[0].url=c.MN_URL
            return function(*clients,**kwargs)
    return run

