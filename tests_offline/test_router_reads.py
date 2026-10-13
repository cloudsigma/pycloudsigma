import os,sys,json,unittest
from pathlib import Path
from decimal import Decimal
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
def deny(event,args):
 if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.fork','os.exec'):raise PermissionError('offline')
sys.addaudithook(deny)
import requests
from cloudsigma.router_reads import VirtualRouterReads,VirtualRouterPolicyRead
class Wire:
 def __init__(self,body,status=200):self.body=body;self.status=status;self.calls=[]
 def get(self,url,**kw):
  self.calls.append((url,kw));r=requests.Response();r.status_code=self.status;r._content=self.body.encode();return r
class Tests(unittest.TestCase):
 def obj(self,cls,body,status=200):
  o=cls(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic');w=Wire(body,status);o.c._session=w;return o,w
 def test_public_fixtures(self):
  for cls,method,identifier,file,path in [(VirtualRouterReads,'list',None,'router_raw_summary_page.json','virtualrouters/'),(VirtualRouterReads,'list_detail',None,'router_raw_detail_page.json','virtualrouters/detail/'),(VirtualRouterReads,'get','id','router_raw_public.json','virtualrouters/id/'),(VirtualRouterPolicyRead,'get','id','router_policy_raw_public.json','vrfwpolicies/id/')]:
   text=(Path(__file__).parent/'fixtures'/file).read_text();o,w=self.obj(cls,text);got=getattr(o,method)(identifier) if identifier else getattr(o,method)();self.assertEqual(got,json.loads(text,parse_float=Decimal));self.assertEqual(len(w.calls),1);url,kw=w.calls[0];self.assertEqual(url,'https://next.cloudsigma.com/api/2.0/'+path);self.assertFalse(kw.get('params'));self.assertIsNone(kw.get('data'));self.assertFalse(kw['allow_redirects'])
 def test_precision_ownership_pages(self):
  text='{"objects":[{"n":9007199254740993.00000000000001,"unknown":null}],"meta":{"limit":0,"total_count":9007199254740993}}';o,w=self.obj(VirtualRouterReads,text);a=o.list({'limit':0,'offset':1});self.assertEqual(w.calls[0][1]['params'],{'limit':0,'offset':1});self.assertIs(type(a['objects'][0]['n']),Decimal);self.assertEqual(str(a['objects'][0]['n']),'9007199254740993.00000000000001');self.assertIs(type(a['meta']['total_count']),int);a['objects'][0]['unknown']='mutated';self.assertIsNone(o.list()['objects'][0]['unknown'])
 def test_invalid_inputs_shapes(self):
  for cls in (VirtualRouterReads,VirtualRouterPolicyRead):
   for identifier in (None,'','../x','a?b',True):
    o,w=self.obj(cls,'{}')
    with self.assertRaises(ValueError):o.get(identifier)
    self.assertEqual(w.calls,[])
   for body in ('null','[]','1','{'):
    o,w=self.obj(cls,body)
    with self.assertRaises(ValueError):o.get('id')
   o,w=self.obj(cls,'{}');self.assertEqual(o.get('id'),{})
  for q in ({'limit':-1},{'limit':True},{'other':1}):
   o,w=self.obj(VirtualRouterReads,'{}')
   with self.assertRaises(ValueError):o.list(q)
   self.assertEqual(w.calls,[])
  for body in ('{}','{"objects":null}','{"objects":[]}'):
   o,w=self.obj(VirtualRouterReads,body);self.assertEqual(o.list(),json.loads(body))
 def test_errors_transport(self):
  from cloudsigma import errors
  for status,exc in ((403,errors.PermissionError),(404,errors.ClientError),(500,errors.ServerError)):
   o,w=self.obj(VirtualRouterReads,'{}',status)
   with self.assertRaises(exc) as c:o.get('id')
   self.assertEqual(c.exception.status_code,status);self.assertEqual(len(w.calls),1)
  o,w=self.obj(VirtualRouterReads,'{}')
  def fail(*a,**kw):raise requests.Timeout('synthetic')
  w.get=fail
  with self.assertRaises(requests.Timeout):o.get('id')
if __name__=='__main__':unittest.main(verbosity=2)
