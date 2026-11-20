
import argparse
import logging
import config as c
from onem2m_client import Client
from worker_state import State
from event_worker import run
from group_queries import sync_group
from resource_registry import (discover_machines, ensure_archive, ensure_cnt,
                               ensure_analyzer, register_machine)

from routing import guarded

@guarded
def step(mn, central, state):
    results = ensure_archive(central)
    archive = c.IN_BASE+'/archive'
    paths = []
    for machine in discover_machines(mn, c.MN_BASE):
        parent = ensure_cnt(central, archive, machine['collector_id'])

        target = register_machine(central, parent, machine)
        paths.append((machine['path']+'/telemetry', target+'/telemetry'))
    paths.append((ensure_analyzer(mn), results))
    for source, target in paths:
        for sample in mn.records(source):
            key = 'v3:'+source+':'+sample['sample_id']
            if state.has(key):
                continue
            if c.FLEX_ENABLED and source.endswith('/telemetry'):
                from flex_model import publish_readings
                publish_readings(central, target.rsplit('/',1)[0], sample)
            central.put(target, sample)
            state.mark(key)
            print('BACKED_UP', target, sample['sample_id'], flush=True)
    try:
        sync_group(central, [target for source, target in paths if source.endswith('/telemetry')])
    except Exception:
        logging.exception('Group synchronization failed; dashboard can use individual reads')
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--once', action='store_true')
    a = p.parse_args()
    c.require_mn()
    from onem2m_client import ArchiveViaMN
    from resource_registry import ensure_ae
    mn = Client(c.MN_URL, c.role_origin('forwarder'))
    ensure_ae(mn, c.MN_BASE, 'forwarder')
    central, state = ArchiveViaMN(mn), State('forwarder')
    run('forwarder', mn, lambda: step(mn, central, state), a.once)
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass


