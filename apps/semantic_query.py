"""Find sensors by semantic property through SMD discovery and client SPARQL."""
import argparse,json
import config as c
from onem2m_client import Client
from semantics import discover_paths
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--property',choices=['temperature','vibration_rms','current'],required=True)
    p.add_argument('--central',action='store_true');a=p.parse_args()
    url,base,role=(c.IN_URL,c.IN_BASE+'/archive','dashboard') if a.central else (c.MN_URL,c.MN_BASE,'analyzer')
    print(json.dumps(discover_paths(Client(url,c.role_origin(role)),base,a.property),ensure_ascii=False,indent=2))
