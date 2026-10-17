import json,unittest
from pathlib import Path
from decimal import Decimal
from test_router_reads import Wire
from cloudsigma.scheduler_reads import BackupSchedulerReads
from cloudsigma import errors
import requests
class Tests(unittest.TestCase):
 def obj(self,body,status=200,session=False):
  if session:
   from test_router_session import Wire as LoginWire
   w=LoginWire([]);o=BackupSchedulerReads(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***',login_method='session',session=w);return o,w
  o=BackupSchedulerReads(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***');w=Wire(body,status);o.c._session=w;return o,w
 def test_public(self):
  for method,arg,file,path in [('list',None,'scheduler_summary.json','backupschedulers/'),('list_detail',None,'scheduler_detail.json','backupschedulers/detail/'),('get','id','scheduler_singleton.json','backupschedulers/id/')]:
   text=(Path(__file__).parent/'fixtures'/file).read_text();o,w=self.obj(text);got=getattr(o,method)(arg) if arg else getattr(o,method)();self.assertEqual(got,json.loads(text,parse_float=Decimal));self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/'+path);self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'))
 def test_options_precision_copy(self):
  body='{"objects":[{"unknown":{"n":9007199254740993.00001,"v":null}}],"meta":{"total_count":9007199254740993}}';o,w=self.obj(body);q={'type':'backup','fields':'uuid,name','limit':0,'offset':2};a=o.list(q);self.assertEqual(w.calls[0][1]['params'],q);self.assertEqual(a['objects'][0]['unknown']['n'],Decimal('9007199254740993.00001'));a['objects'][0]['unknown']['v']='changed';self.assertIsNone(o.list()['objects'][0]['unknown']['v']);o.list_detail({'type':'snapshot'});self.assertEqual(w.calls[-1][1]['params'],{'type':'snapshot'})
 def test_invalid(self):
  for method,arg in [('get','../x'),('get',None),('list',{'limit':True}),('list',{'offset':-1}),('list',{'type':'unknown'}),('list_detail',{'fields':'uuid'})]:
   o,w=self.obj('{}')
   with self.assertRaises(ValueError):getattr(o,method)(arg)
   self.assertEqual(w.calls,[])
  for body in ('null','[]','{','{"objects":[null]}'):
   o,w=self.obj(body)
   with self.assertRaises(ValueError):o.list()
  for body in ('{}','{"objects":null}','{"objects":[]}'):
   o,w=self.obj(body);self.assertEqual(o.list(),json.loads(body))
 def test_error_and_login(self):
  for code,exc in [(403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)]:
   o,w=self.obj('{}',code)
   with self.assertRaises(exc):o.get('id')
  o,w=self.obj('{}')
  def fail(*a,**kw):raise requests.Timeout('synthetic')
  w.get=fail
  with self.assertRaises(requests.Timeout):o.get('id')
  o,w=self.obj('{}',session=True);self.assertEqual(o.get('id'),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/backupschedulers/id/');self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
