import sys,os,unittest,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
# Restrict Python networking before SDK/test imports; subprocesses permitted only for inventory fixtures.
def deny(event,args):
 if event.startswith('socket.'):raise PermissionError('offline network denied')
sys.addaudithook(deny)
import socket
try:socket.socket()
except PermissionError:pass
else:raise RuntimeError('network guard failed')
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
import cloudsigma
assert 'site-packages' in cloudsigma.__file__, 'must test installed artifact'
print(json.dumps({'python':sys.version,'SDK':cloudsigma.__file__,'SDK_SHA':hashlib.sha256(Path(cloudsigma.__file__).read_bytes()).hexdigest()}))
os.environ['PATH']=str(Path(sys.executable).parent)+':/usr/bin:/bin'
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
sys.path.insert(0,str(ROOT))
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests_offline'))
r=unittest.TextTestRunner(verbosity=2).run(suite)
assert r.testsRun==294, 'unexpected test count'
sys.exit(not r.wasSuccessful())
