import os,unittest,json,io,logging
from unittest.mock import patch
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
import requests
from cloudsigma import resource as r,generic as g
class Tests(unittest.TestCase):
 def test_exact_cells(self):
  for cls,path in [(r.Server,'servers'),(r.Drive,'drives'),(r.IP,'ips'),(r.VLAN,'vlans'),(r.Tags,'tags')]:
   for method,verb,tail,payload,query in [('list','GET','/',None,{'limit':1}),('create','POST','/',{'objects':[{'name':'synthetic'}]},None),('update','PUT','/fixture/',{'meta':{}},None),('delete','DELETE','/fixture/',None,None)]:
    with self.subTest(resource=path,method=method):
     calls=[]
     class Wire:
      def request(self,url,**kw):
       calls.append(1);selftest.assertEqual(url,'https://example.invalid/api/2.0/'+path+tail);selftest.assertEqual(kw.get('params'),query);selftest.assertEqual(json.loads(kw['data']) if 'data' in kw else None,payload);selftest.assertFalse(kw['allow_redirects']);res=requests.Response();res.status_code=204 if method=='delete' else 200;res._content=b'{"objects":[]}';return res
      def __getattr__(self,n):
       selftest.assertEqual(n,verb.lower());return self.request
     selftest=self;o=cls(api_endpoint='https://example.invalid/api/2.0/',username='synthetic',password='synthetic');o.c._session=Wire()
     if method=='list':o.list({'limit':1})
     elif method=='create':o.create({'name':'synthetic'})
     elif method=='update':o.update('fixture',{'meta':{}})
     else:o.delete('fixture')
     self.assertEqual(len(calls),1)
 def test_none_debug_actual_hook(self):
  output=io.StringIO();h=logging.StreamHandler(output);old=g.LOG.level;g.LOG.setLevel(logging.DEBUG);g.LOG.addHandler(h)
  try:
   with patch.dict(g.config,{'login_method':'none','request_log_level':'DEBUG'},clear=True):
    c=g.GenericClient(api_endpoint='https://example.invalid/api/2.0/',username='u',password='password-canary');kw=c._get_req_args();self.assertNotIn('auth',kw);res=requests.Response();res.status_code=200;res._content=b'token-canary';res.request=requests.Request('GET','https://example.invalid/?password=query-canary',headers={'Authorization':'Basic auth-canary'}).prepare();kw['hooks']['response'](res)
   self.assertIn('status=200',output.getvalue())
   for canary in ['password-canary','token-canary','query-canary','auth-canary']:self.assertNotIn(canary,output.getvalue())
  finally:g.LOG.removeHandler(h);g.LOG.setLevel(old)
if __name__=='__main__':unittest.main(verbosity=2)
