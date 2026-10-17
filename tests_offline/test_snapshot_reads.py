import json, unittest
from pathlib import Path
from decimal import Decimal
from test_router_reads import Wire
from cloudsigma.snapshot_reads import SnapshotReads
from cloudsigma import errors
import requests

class Tests(unittest.TestCase):
 def obj(self,body,status=200):
  o=SnapshotReads(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');w=Wire(body,status);o.c._session=w;return o,w
 def call(self,o,method):return o.get('synthetic-id') if method=='get' else getattr(o,method)()
 def test_public(self):
  for method,file,path in [('list','snapshots_summary_public.json','snapshots/'),('list_detail','snapshots_detail_public.json','snapshots/detail/'),('get','snapshot_public.json','snapshots/synthetic-id/')]:
   text=(Path(__file__).parent/'fixtures'/file).read_text();o,w=self.obj(text);self.assertEqual(self.call(o,method),json.loads(text,parse_float=Decimal));self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/'+path);self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects'])
 def test_presence_precision_copy(self):
  for method in ('list','list_detail','get'):
   for text in ('{}','{"allocated_size":null}','{"objects":[]}', '{"objects":null}', '{"allocated_size":9007199254740993.00001,"unknown":{"value":null},"objects":[{"allocated_size":null}],"meta":{"future":true}}'):
    o,w=self.obj(text);expected=json.loads(text,parse_float=Decimal);a=self.call(o,method);self.assertEqual(a,expected);a['injected']=True
    if 'unknown' in a:a['unknown']['value']='changed';a['objects'][0]['allocated_size']=12
    self.assertEqual(self.call(o,method),expected);self.assertEqual(len(w.calls),2)
 def test_errors_inputs(self):
  for method in ('list','list_detail','get'):
   for text in ('null','[]','1','{',''):
    o,w=self.obj(text)
    with self.assertRaises(ValueError):self.call(o,method)
   for code,exc in ((403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)):
    o,w=self.obj('{}',code)
    with self.assertRaises(exc) as c:self.call(o,method)
    self.assertEqual(c.exception.status_code,code);self.assertEqual(len(w.calls),1)
   o,w=self.obj('{}');sentinel=requests.Timeout('synthetic')
   def fail(*a,**kw):raise sentinel
   w.get=fail
   with self.assertRaises(requests.Timeout) as c:self.call(o,method)
   self.assertIs(c.exception,sentinel)
  for identifier in (None,'','../x','a/b','a?b','a#b','a%2fb'):
   o,w=self.obj('{}')
   with self.assertRaises(ValueError):o.get(identifier)
   self.assertEqual(w.calls,[])
 def test_serial_session(self):
  from test_router_session import Wire as LoginWire
  for method,path in [('list','snapshots/'),('list_detail','snapshots/detail/'),('get','snapshots/synthetic-id/')]:
   w=LoginWire([]);o=SnapshotReads(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic',login_method='session',session=w);self.assertEqual(self.call(o,method),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/'+path);self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
