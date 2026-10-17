import json,unittest
from pathlib import Path
from test_router_reads import Wire
from cloudsigma.public_key_read import PublicKeyRead
from cloudsigma import errors
import requests
class Tests(unittest.TestCase):
 def obj(self,text,status=200):
  o=PublicKeyRead(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***');w=Wire(text,status);o.c._session=w;return o,w
 def test_complete_public(self):
  for i,flag in ((0,True),(1,False)):
   text=(Path(__file__).parent/'fixtures'/('pubkey_public_%d.json'%i)).read_text();o,w=self.obj(text);expected=json.loads(text);a=o.get('synthetic-id');self.assertEqual(a,expected);self.assertIs(a['has_private_key'],flag);self.assertNotIn('private_key',a);self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/pubkeys/synthetic-id/');self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects']);a['meta']['injected']={'changed':True};a['grantees'].append('synthetic');a['public_key']='changed';self.assertEqual(o.get('synthetic-id'),expected);self.assertEqual(len(w.calls),2)
 def test_presence_decoded_strings(self):
  for text in ('{}','{"public_key":null}','{"public_key":""}','{"public_key":"SYNTHETIC\\u005fCANARY\\n\\t\\\"quoted\\\"\\\\tail","future":{"value":null}}'):
   o,w=self.obj(text);a=o.get('synthetic-id');expected=json.loads(text);self.assertEqual(a,expected);a['public_key']='changed'
   if 'future' in a:a['future']['value']='changed'
   self.assertEqual(o.get('synthetic-id'),expected);self.assertEqual(len(w.calls),2)
 def test_errors_and_routing_characterization(self):
  for code,exc in ((403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)):
   o,w=self.obj('{}',code)
   with self.assertRaises(exc) as c:o.get('synthetic-id')
   self.assertEqual(c.exception.status_code,code);self.assertEqual(len(w.calls),1)
  o,w=self.obj('{')
  with self.assertRaises(ValueError):o.get('synthetic-id')
  o,w=self.obj('{}');sentinel=requests.Timeout('synthetic')
  def fail(*a,**kw):raise sentinel
  w.get=fail
  with self.assertRaises(requests.Timeout) as c:o.get('synthetic-id')
  self.assertIs(c.exception,sentinel)
  for identifier in (None,True,1,b'id','', '../x','a/b','a?b','a#b','a%2fb','a b','é'):
   o,w=self.obj('{}')
   with self.assertRaises(ValueError):o.get(identifier)
   self.assertEqual(w.calls,[])
  o,w=self.obj('{}')
  for name in ('list','list_detail','create','update','delete','clone'):
   self.assertFalse(hasattr(o,name))
 def test_serial_login(self):
  from test_router_session import Wire as LoginWire
  w=LoginWire([]);o=PublicKeyRead(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***',login_method='session',session=w);self.assertEqual(o.get('synthetic-id'),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/pubkeys/synthetic-id/');self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
