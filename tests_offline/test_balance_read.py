import json,unittest
from pathlib import Path
from test_router_reads import Wire
from cloudsigma.resource import Balance
from cloudsigma import errors
import requests
class Tests(unittest.TestCase):
 def obj(self,body,status=200):
  o=Balance(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***');w=Wire(body,status);o.c._session=w;return o,w
 def test_public_string_precision(self):
  text=(Path(__file__).parent/'fixtures/balance_public.json').read_text();o,w=self.obj(text);v=o.get();self.assertEqual(v,json.loads(text));self.assertIs(type(v['balance']),str);self.assertEqual(v['balance'],'155367.99237092264288897986');self.assertIsNone(v['credit_limit']);self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/balance/');self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects'])
 def test_presence_unknown_copy(self):
  for text in ('{}','{"balance":null}','{"balance":"-0.000000000000000001","currency":"synthetic","future":{"n":9007199254740993,"items":[null]}}'):
   o,w=self.obj(text);a=o.get();self.assertEqual(a,json.loads(text));a['injected']=True
   if 'future' in a:a['future']['items'][0]='changed'
   self.assertEqual(o.get(),json.loads(text));self.assertEqual(len(w.calls),2)
 def test_errors_and_legacy_shapes(self):
  for status,exc in ((403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)):
   o,w=self.obj('{}',status)
   with self.assertRaises(exc) as c:o.get()
   self.assertEqual(c.exception.status_code,status);self.assertEqual(len(w.calls),1)
  o,w=self.obj('{')
  with self.assertRaises(ValueError):o.get()
  o,w=self.obj('null')
  with self.assertRaises(TypeError):o.get()
  o,w=self.obj('[]');self.assertEqual(o.get(),[]) # inherited permissiveness, not public contract
  def fail(*a,**kw):raise requests.Timeout('synthetic')
  w.get=fail
  with self.assertRaises(requests.Timeout):o.get()
 def test_session_login_read(self):
  from test_router_session import Wire as LoginWire
  w=LoginWire([])
  def get(url,**kw):w.calls.append(('GET',url,kw));return w.response({'balance':'0.000000000000000001','credit_limit':None,'currency':'EUR'})
  w.get=get;o=Balance(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***',login_method='session',session=w);self.assertEqual(o.get()['balance'],'0.000000000000000001');self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/balance/');self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
