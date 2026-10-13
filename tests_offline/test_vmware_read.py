import json,unittest
from pathlib import Path
from decimal import Decimal
from test_router_reads import Wire
from cloudsigma.vmware_read import VMwareRead
from cloudsigma import errors
import requests
class Tests(unittest.TestCase):
 def obj(self,cls,body,status=200):
  o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***');w=Wire(body,status);o.c._session=w;return o,w
 def test_complete_public(self):
  for cls,name in [(VMwareRead,'vmware')]:
   text=(Path(__file__).parent/'fixtures'/'vmware_normalized.json').read_text();o,w=self.obj(cls,text);v=o.list();self.assertEqual(v,json.loads(text,parse_float=Decimal));self.assertIs(type(v),dict);self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/'+'vmware_servers/');self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects'])
 def test_precision_presence_ownership(self):
  for cls in (VMwareRead,):
   for text in ('{}','{"objects":null}','{"objects":[]}', '{"objects":[{"amount":"0.000000000000000001","numeric":9007199254740993.00001,"future":null}],"meta":{"total_count":9007199254740993}}'):
    o,w=self.obj(cls,text);a=o.list();expected=json.loads(text,parse_float=Decimal);self.assertEqual(a,expected);a['injected']=True
    if a.get('objects'):
     self.assertIs(type(a['objects'][0]['numeric']),Decimal);a['objects'][0]['future']='changed'
    self.assertEqual(o.list(),expected);self.assertEqual(len(w.calls),2)
 def test_limit_shapes_errors(self):
  for cls in (VMwareRead,):
   for body in ('null','[]','1','{'):
    o,w=self.obj(cls,body)
    with self.assertRaises(ValueError):o.list()
   for code,exc in ((403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)):
    o,w=self.obj(cls,'{}',code)
    with self.assertRaises(exc) as c:o.list()
    self.assertEqual(c.exception.status_code,code);self.assertEqual(len(w.calls),1)
   o,w=self.obj(cls,'{}')
   def fail(*a,**kw):raise requests.Timeout('synthetic')
   w.get=fail
   with self.assertRaises(requests.Timeout):o.list()
 def test_serial_session(self):
  from test_router_session import Wire as LoginWire
  for cls,path in ((VMwareRead,'vmware_servers'),):
   w=LoginWire([]);o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***',login_method='session',session=w);self.assertEqual(o.list(),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/'+path+'/');self.assertEqual(w.headers['X-CSRFToken'],'synthetic')

 def test_list_only_surface(self):
  o,w=self.obj(VMwareRead,'{}')
  for name in ('get','create','update','delete','clone','start','stop','list_detail'):
   self.assertFalse(hasattr(o,name))
