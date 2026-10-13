import json,os,sys,unittest
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
def deny(event,args):
 if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.fork','os.exec'):raise PermissionError('offline')
sys.addaudithook(deny)
import requests
from cloudsigma.resource import ServersAvailabilityGroups,DrivesAvailabilityGroups
class Wire:
 def __init__(self,body):self.body=body;self.calls=[]
 def get(self,url,**kw):
  self.calls.append((url,kw));r=requests.Response();r.status_code=200;r._content=json.dumps(self.body).encode();return r
class Tests(unittest.TestCase):
 def obj(self,cls,body):
  o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');w=Wire(body);o.c._session=w;return o,w
 def test_routes_shapes(self):
  for cls,kind in [(ServersAvailabilityGroups,'servers'),(DrivesAvailabilityGroups,'drives')]:
   for method,identifier,body in [('list',None,[['id-a','id-b'],[]]),('get',None,[['id-a']]),('get','id-a',['id-a','id-b']),('get',b'id-a',[])]:
    o,w=self.obj(cls,body);got=getattr(o,method)(identifier) if identifier is not None else getattr(o,method)();self.assertEqual(got,body);self.assertIs(type(got),list);self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/'+kind+'/availability_groups/'+('id-a/' if identifier is not None else ''));self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects'])
 def test_invalid_shapes(self):
  for cls in (ServersAvailabilityGroups,DrivesAvailabilityGroups):
   for body in (None,{},1,'text',[None],[1],[['id',None]]):
    for singleton in (False,True):
     o,w=self.obj(cls,body)
     with self.assertRaises((ValueError,TypeError)):o.get('id' if singleton else None)
     self.assertEqual(len(w.calls),1)
 def test_identifiers_no_dispatch(self):
  for cls in (ServersAvailabilityGroups,DrivesAvailabilityGroups):
   for identifier in ('','../x','a/b','a?x',1,True,b'\xff'):
    o,w=self.obj(cls,[])
    with self.assertRaises((ValueError,UnicodeError)):o.get(identifier)
    self.assertEqual(w.calls,[])
 def test_empty_and_copy(self):
  for cls in (ServersAvailabilityGroups,DrivesAvailabilityGroups):
   o,w=self.obj(cls,[]);self.assertEqual(o.list(),[])
   o,w=self.obj(cls,[['id']]);a=o.list();a[0][0]='changed';self.assertEqual(o.list(),[['id']])
if __name__=='__main__':unittest.main(verbosity=2)
