"""Finite development-consumer checks. Never discover acceptance tests or import SDK."""
import sys, socket, json, hashlib, importlib.metadata as md
from pathlib import Path

# Audit hook is active and proved BEFORE any third-party import.
def deny_network(event, args):
    if event.startswith('socket.') and event != 'socket.gethostname':
        raise PermissionError('offline network denied')


def resolve_example():
    return socket.getaddrinfo('example.invalid', 443)


# Paramiko expands a local hostname even for empty SSH configuration.
# This reads no network/configuration; all socket creation and DNS remain denied.
sys.addaudithook(deny_network)
for probe in (socket.socket, resolve_example):
    try:
        probe()
    except PermissionError:
        pass
    else:
        raise RuntimeError('network guard failed')
root = Path(__file__).resolve().parent.parent
binding = json.loads((root / 'ci/dev-closure.json').read_text())
for name, expected in binding['inputs'].items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
        raise RuntimeError('development closure input drift: ' + name)
for name, expected in binding['packages'].items():
    if md.version(name) != expected:
        raise RuntimeError('development closure version drift: ' + name)
if len(binding['packages']) != 25:
    raise RuntimeError('unexpected closure size')
import fabric,paramiko,paramiko.config,requests,nacl.signing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives import hashes,hmac
assert paramiko.config.invoke.exceptions.UnexpectedExit
config=fabric.Config(overrides={'load_ssh_configs':False},lazy=True)
c=fabric.Connection('offline.invalid',user='fixture',connect_kwargs={'password':'not-a-credential'},config=config)
assert c.host=='offline.invalid' and not c.is_connected
assert isinstance(c.client,paramiko.SSHClient)
c.close()
# RFC8032 test vector 1: verify only, never create/generate a private key.
pub=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
sig=bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
nacl.signing.VerifyKey(pub).verify(b'',sig)
Ed25519PublicKey.from_public_bytes(pub).verify(sig,b'')
from nacl.exceptions import BadSignatureError
from cryptography.exceptions import InvalidSignature
for verify, error in (
    (lambda: nacl.signing.VerifyKey(pub).verify(b'changed', sig), BadSignatureError),
    (lambda: Ed25519PublicKey.from_public_bytes(pub).verify(sig, b'changed'), InvalidSignature),
):
    try:
        verify()
    except error:
        pass
    else:
        raise RuntimeError('altered message accepted')
keymsg=paramiko.Message();keymsg.add_string('ssh-ed25519');keymsg.add_string(pub)
k=paramiko.Ed25519Key(data=bytes(keymsg)); sm=paramiko.Message();sm.add_string('ssh-ed25519');sm.add_string(sig)
assert k.verify_ssh_sig(b'',paramiko.Message(bytes(sm)))
assert not k.verify_ssh_sig(b'changed',paramiko.Message(bytes(sm)))
# Exercise actual Paramiko crypto class mapping using fixed nonsecret bytes.
for alg in ['aes128-ctr','aes256-ctr']:
 spec=paramiko.Transport._cipher_info[alg]; enc=Cipher(spec['class'](b'\0'*spec['key-size']),spec['mode'](b'\0'*spec['block-size'])).encryptor(); assert len(enc.update(b'\0'*32)+enc.finalize())==32
h=hmac.HMAC(b'fixed-test-value',hashes.SHA256());h.update(b'payload');assert len(h.finalize())==32
r=requests.Request('GET','https://example.invalid/test',params={'q':'a b'}).prepare();assert r.url.endswith('q=a+b')
print(json.dumps({'python':sys.version,'checks':['fabric import and nonconnecting construction','actual paramiko.config invoke consumer','PyNaCl RFC8032 verify','cryptography RFC8032 verify','Paramiko Ed25519 verify and tamper refusal','Paramiko AES CTR mappings','local HMAC','Requests prepare'],'versions':{x:md.version(x) for x in binding['packages']},'guard':'socket and DNS denied before third-party imports','tamper':'PyNaCl, cryptography and Paramiko reject changed message'},indent=2))
