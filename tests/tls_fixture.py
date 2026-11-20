
from pathlib import Path
import subprocess

def certificates(directory):
    root=Path(directory)
    def run(*args):subprocess.run(['openssl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    run('req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'ca.key'),'-out',str(root/'ca.crt'),'-days','1','-subj','/CN=QuietFix test CA')
    for name in ('server','collector','dashboard','rogue'):
        run('req','-newkey','rsa:2048','-nodes','-keyout',str(root/(name+'.key')),'-out',str(root/(name+'.csr')),'-subj','/CN='+name)
        ext=root/(name+'.ext');ext.write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth,clientAuth\n')
        run('x509','-req','-in',str(root/(name+'.csr')),'-CA',str(root/'ca.crt'),'-CAkey',str(root/'ca.key'),'-CAcreateserial','-out',str(root/(name+'.crt')),'-days','1','-extfile',str(ext))
    return root

