import os,sys,json,unittest,hashlib,logging,io
from pathlib import Path
from unittest.mock import patch
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
def deny(event,args):
 if event.startswith('socket.') or event in ['subprocess.Popen','os.system','os.fork','os.exec']:raise PermissionError('offline')
sys.addaudithook(deny)
import requests,cloudsigma
from cloudsigma import resource as r,generic as g,errors
class Wire:
 def __init__(self,body=None,status=200):self.body=body if body is not None else {'objects':[],'meta':{'limit':1}};self.status=status;self.calls=[]
 def request(self,method,url,**kw):
  self.calls.append((method,url,kw));res=requests.Response();res.status_code=self.status;res._content=json.dumps(self.body).encode();res.headers['X-REQUEST-ID']='fixture';res.request=requests.Request(method,url).prepare();return res
 def __getattr__(self,n):return lambda url,**kw:self.request(n.upper(),url,**kw)
class Tests(unittest.TestCase):
 def obj(self,cls,wire):
  o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');o.c._session=wire;return o
 def test_collection_routes_pagination(self):
  for cls,path in [(r.Server,'servers'),(r.Drive,'drives'),(r.IP,'ips'),(r.VLAN,'vlans'),(r.Tags,'tags')]:
   w=Wire();o=self.obj(cls,w);self.assertEqual(o.list({'limit':1}),[]);self.assertEqual(w.calls[0][1],'https://next.cloudsigma.com/api/2.0/'+path+'/');self.assertEqual(w.calls[0][2]['params'],{'limit':1});o.list();self.assertEqual(w.calls[1][2]['params']['limit'],0)
 def test_crud_serialization(self):
  for cls in [r.Server,r.Drive,r.IP,r.VLAN,r.Tags]:
   w=Wire({'objects':[{'uuid':'fixture'}]},201);o=self.obj(cls,w);self.assertEqual(o.create({'name':'n'}),{'uuid':'fixture'});self.assertEqual(json.loads(w.calls[-1][2]['data']),{'objects':[{'name':'n'}]});o.update('fixture',{'meta':{}});self.assertEqual(json.loads(w.calls[-1][2]['data']),{'meta':{}});self.assertEqual(w.calls[-1][0],'PUT');w.status=204;self.assertIsNone(o.delete('fixture'));self.assertEqual(w.calls[-1][0],'DELETE')
 def test_get_and_metadata(self):
  w=Wire({'objects':[{'uuid':'fixture'}],'meta':{'limit':1,'unknown':7}});o=self.obj(r.Drive,w);self.assertEqual(o.get('fixture'),{'uuid':'fixture'});self.assertEqual(o.c.resp.json()['meta']['unknown'],7);self.assertTrue(w.calls[0][1].endswith('/drives/fixture/'))
 def test_error_decoding(self):
  for status,cls in [(401,errors.AuthError),(403,errors.PermissionError),(404,errors.ClientError),(429,errors.ClientError),(500,errors.ServerError)]:
   w=Wire({'error':'synthetic'},status);o=self.obj(r.Tags,w)
   with self.assertRaises(cls) as c:o.list({'limit':1})
   self.assertEqual(c.exception.status_code,status)
 def test_malformed_json(self):
  c=g.GenericClient(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');resp=requests.Response();resp.status_code=200;resp._content=b'{'
  with self.assertRaises(ValueError):c._process_response(resp)
 def test_native_boundary_characterization(self):
  w=Wire();o=self.obj(r.Tags,w);o.list({'limit':1});kw=w.calls[0][2];self.assertEqual(kw['auth'],('synthetic','synthetic'));self.assertEqual(kw['timeout'],15);self.assertFalse(kw['allow_redirects']);self.assertNotIn('proxies',kw)
 def test_config_selection_characterization(self):
  with patch.dict(g.config,{'login_method':'none','request_log_level':'DEBUG'},clear=True):
   c=g.GenericClient(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');self.assertEqual(c.login_method,'none');self.assertEqual(c.request_log_level,'DEBUG');self.assertNotIn('auth',c._get_req_args())
 def test_redirect_decoder_characterization(self):
  resp=requests.Response();resp.status_code=302;resp._content=b'{}';c=g.GenericClient(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');self.assertRaises(errors.ApiClientError,c._process_response,resp)
if __name__=='__main__':unittest.main(verbosity=2)
