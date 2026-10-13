import json,unittest
from pathlib import Path
from decimal import Decimal
from test_router_reads import Wire
from cloudsigma.account_reads import PricingRead,LedgerRead
from cloudsigma import errors
import requests
class Tests(unittest.TestCase):
 def obj(self,cls,body,status=200):
  o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***');w=Wire(body,status);o.c._session=w;return o,w
 def test_complete_public(self):
  for cls,name in [(PricingRead,'pricing'),(LedgerRead,'ledger')]:
   text=(Path(__file__).parent/'fixtures'/f'{name}_public.json').read_text();o,w=self.obj(cls,text);v=o.get();self.assertEqual(v,json.loads(text,parse_float=Decimal));self.assertIs(type(v),dict);self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/'+name+'/');self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects'])
 def test_precision_presence_ownership(self):
  for cls in (PricingRead,LedgerRead):
   for text in ('{}','{"objects":null}','{"objects":[]}', '{"objects":[{"amount":"0.000000000000000001","numeric":9007199254740993.00001,"future":null}],"meta":{"total_count":9007199254740993}}'):
    o,w=self.obj(cls,text);a=o.get();expected=json.loads(text,parse_float=Decimal);self.assertEqual(a,expected);a['injected']=True
    if a.get('objects'):
     self.assertIs(type(a['objects'][0]['numeric']),Decimal);a['objects'][0]['future']='changed'
    self.assertEqual(o.get(),expected);self.assertEqual(len(w.calls),2)
 def test_limit_shapes_errors(self):
  for limit in (0,5):
   o,w=self.obj(PricingRead,'{}');o.get(limit);self.assertEqual(w.calls[0][1]['params'],{'limit':limit})
  for limit in (-1,True,1.5,'5'):
   o,w=self.obj(PricingRead,'{}')
   with self.assertRaises(ValueError):o.get(limit)
   self.assertEqual(w.calls,[])
  for cls in (PricingRead,LedgerRead):
   for body in ('null','[]','1','{'):
    o,w=self.obj(cls,body)
    with self.assertRaises(ValueError):o.get()
   for code,exc in ((403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)):
    o,w=self.obj(cls,'{}',code)
    with self.assertRaises(exc) as c:o.get()
    self.assertEqual(c.exception.status_code,code);self.assertEqual(len(w.calls),1)
   o,w=self.obj(cls,'{}')
   def fail(*a,**kw):raise requests.Timeout('synthetic')
   w.get=fail
   with self.assertRaises(requests.Timeout):o.get()
 def test_serial_session(self):
  from test_router_session import Wire as LoginWire
  for cls,path in ((PricingRead,'pricing'),(LedgerRead,'ledger')):
   w=LoginWire([]);o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='***',login_method='session',session=w);self.assertEqual(o.get(),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[-1][1],'https://next.cloudsigma.com/api/2.0/'+path+'/');self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
