import os,io,logging,requests,sys
from unittest import TestCase
from unittest.mock import patch
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
from cloudsigma import generic as g,errors
class Tests(TestCase):
 def client(self,**kw):return g.GenericClient(api_endpoint='https://example.invalid/api/2.0/',username='user',password='password-canary',**kw)
 def test_finite_native_options(self):
  c=self.client();a=c._get_req_args();self.assertEqual(a['timeout'],15);self.assertIs(a['allow_redirects'],False);self.assertFalse(c.http.trust_env)
 def test_redirect_rejected(self):
  r=requests.Response();r.status_code=302;r._content=b'{}';r.headers['Location']='https://evil.invalid/?token=canary'
  with self.assertRaises(errors.ApiClientError):self.client()._process_response(r)
 def test_logging_redaction(self):
  out=io.StringIO();h=logging.StreamHandler(out);g.LOG.addHandler(h);old=g.LOG.level;g.LOG.setLevel(logging.DEBUG)
  try:
   r=requests.Response();r.status_code=200;r._content=b'password-response';r.headers['Set-Cookie']='cookie-canary';r.request=requests.Request('POST','https://example.invalid/private-canary?token=query-canary',headers={'Authorization':'Bearer token-canary'},data='password-body').prepare();g.wrap_with_log_hook('DEBUG')(r)
   for secret in ['private-canary','query-canary','token-canary','password-body','password-response','cookie-canary']:self.assertNotIn(secret,out.getvalue())
  finally:g.LOG.removeHandler(h);g.LOG.setLevel(old)
 def test_explicit_auth_precedence(self):
  with patch.dict(g.config,{'login_method':'none'},clear=True):self.assertEqual(self.client(login_method='basic').login_method,'basic')
 def test_crossorigin_auth_refusal(self):
  c=self.client();called=[]
  class Fake:
   def get(self,*a,**kw):called.append(1);raise AssertionError('dispatch')
  c._session=Fake()
  with self.assertRaises(errors.ApiClientError):c.get('https://evil.invalid/path')
  self.assertEqual(called,[])
 def test_options_and_external_session(self):
  session=requests.Session();c=self.client(session=session,timeout=(2,3),proxies={'https':'http://synthetic.invalid'},trust_env=False)
  self.assertIs(c.http,session);self.assertFalse(session.trust_env);self.assertEqual(c._get_req_args()['timeout'],(2,3));self.assertEqual(c._get_req_args()['proxies'],{'https':'http://synthetic.invalid'})
  for t in [None,0,-1,float('inf'),True]:
   with self.assertRaises(ValueError):self.client(timeout=t)
 def test_transport_exception(self):
  c=self.client()
  with patch.object(c.http,'get',side_effect=requests.Timeout('synthetic')):
   with self.assertRaises(requests.Timeout):c.get('/tags/')
if __name__=='__main__':unittest.main(verbosity=2)
