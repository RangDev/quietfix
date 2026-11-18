"""Dynamic oneM2M resource registration and discovery; no separate database."""
import hashlib
import json
from urllib.parse import urlencode
import config as c
from device_model import identifier
from onem2m_client import OneM2MError

MACHINE_LABEL = 'quietfix-machine-v3'

def ensure_ae(client, base, name):
    identifier(name)
    if c.ACP_ENABLED:
        client.call('GET', base+'/'+name)  # Admin provisions AEs before secure runtime.
        return base+'/'+name
    client.ensure(base, 'm2m:ae', {'rn': name, 'api': 'NQuietFix', 'rr': False, 'srv': ['3']}, 2)
    return base+'/'+name

def ensure_cnt(client, parent, name, **attrs):
    if c.ACP_ENABLED:
        from access_control import policy_ref
        policy = 'archive' if parent.startswith(c.IN_BASE+'/archive') else ('analysis' if parent.startswith(c.MN_BASE+'/analyzer') else 'sensors')
        base = c.IN_BASE if policy == 'archive' else c.MN_BASE
        attrs['acpi'] = [policy_ref(base, policy)]
    client.ensure(parent, 'm2m:cnt', {'rn': name, 'mni': 1000, **attrs}, 3)
    return parent+'/'+name

def ensure_analyzer(client):
    return ensure_cnt(client, ensure_ae(client, c.MN_BASE, 'analyzer'), 'results')

def ensure_archive(client):
    return ensure_cnt(client, ensure_ae(client, c.IN_BASE, 'archive'), 'results')

def latest_or_none(client, path):
    try:
        return client.latest(path)
    except OneM2MError as e:
        if e.status != 404:
            raise
        return None

def register_machine(client, parent, sample):
    machine = identifier(sample['machine_id'])
    # Prefix avoids collision with old collector-01/telemetry, or archive/results.
    path = ensure_cnt(client, parent, 'machine-'+machine, lbl=[MACHINE_LABEL])
    ensure_cnt(client, path, 'telemetry')
    metadata = ensure_cnt(client, path, 'metadata', mni=1)
    previous = latest_or_none(client, metadata) or {}
    sensors = {s['sensor_id']: s for s in previous.get('sensors', [])}
    sensors.update({s['sensor_id']: {k: v for k, v in s.items() if k != 'value'}
                    for s in sample['sensors']})
    catalog = {'collector_id': sample['collector_id'], 'machine_id': machine,
               'machine_name': sample.get('machine_name', machine),
               'sensors': sorted(sensors.values(), key=lambda s: s['sensor_id'])}
    # Unchanged catalog produces no additional metadata write.
    catalog['sample_id'] = 'catalog-'+hashlib.sha256(
        json.dumps(catalog, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if previous != catalog:
        client.put(metadata, catalog)
    return path

from routing import guarded

@guarded
def publish(client, sample):
    parent = ensure_ae(client, c.MN_BASE, identifier(sample['collector_id']))
    path = register_machine(client, parent, sample)
    if c.FLEX_ENABLED:
        from flex_model import publish_readings
        publish_readings(client, path, sample)
    client.put(path+'/telemetry', sample)
    return path

def discover_machines(client, base):
    if c.FLEX_ENABLED:
        from flex_model import discover
        yield from discover(client, base)
        return
    # Use labels so unrelated containers and legacy resources are left untouched.
    query = urlencode({'fu': 1, 'ty': 3, 'lbl': MACHINE_LABEL, 'drt': 1, 'lim': 10000})
    result = client.call('GET', base+'?'+query)
    for path in sorted(result.get('m2m:uril', [])):
        catalog = latest_or_none(client, path+'/metadata')
        if catalog is not None:
            yield {**catalog, 'path': path}
