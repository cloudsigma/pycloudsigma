import json,unittest
from pathlib import Path
from test_router_reads import Wire
from cloudsigma.resource import LibDrive
from cloudsigma import errors
import requests
class Tests(unittest.TestCase):
 def obj(self,text,status=200):
  o=LibDrive(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***');w=Wire(text,status);o.c._session=w;return o,w
 def test_sanitized_complete(self):
  text=(Path(__file__).parent/'fixtures/library_drive_sanitized.json').read_text();o,w=self.obj(text);expected=json.loads(text);a=o.get('synthetic-id');self.assertEqual(a,expected);self.assertEqual(len(a),26);self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/libdrives/synthetic-id/');self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects']);a['licenses'][0]['license']['name']='changed';a['install_notes']='changed';a['injected']=True;self.assertEqual(o.get('synthetic-id'),expected);self.assertEqual(len(w.calls),2)
 def test_notes_presence_decoded_strings(self):
  for text in ('{}','{"install_notes":null}','{"install_notes":""}','{"install_notes":"SYNTHETIC\\u005fCANARY\\n\\t\\\"quoted\\\"\\\\tail","future":{"value":null}}'):
   o,w=self.obj(text);a=o.get('synthetic-id');expected=json.loads(text);self.assertEqual(a,expected);a['install_notes']='changed'
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
  # Existing generic API does not provide identifier validation; do not invent it.
  o,w=self.obj('{}');o.get('a/b');self.assertEqual(w.calls[0][0],'https://next.cloudsigma.com/api/2.0/libdrives/a/b/')
 def test_serial_login(self):
  from test_router_session import Wire as LoginWire
  w=LoginWire([]);o=LibDrive(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***',login_method='session',session=w);self.assertEqual(o.get('synthetic-id'),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/libdrives/synthetic-id/');self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
