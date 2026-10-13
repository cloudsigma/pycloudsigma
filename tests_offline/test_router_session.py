import os,sys,json,unittest
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
def deny(e,a):
 if e.startswith('socket.') or e in ('subprocess.Popen','os.system','os.fork','os.exec'):raise PermissionError('offline')
sys.addaudithook(deny)
import requests
from cloudsigma.generic import GenericClient
from cloudsigma.router_reads import VirtualRouterReads
class Wire:
 def __init__(self,body):self.body=body;self.headers={};self.calls=[]
 def response(self,body):
  r=requests.Response();r.status_code=200;r._content=json.dumps(body).encode();r.cookies['csrftoken']='synthetic';return r
 def post(self,url,**kw):self.calls.append(('POST',url,kw));return self.response(self.body)
 def get(self,url,**kw):self.calls.append(('GET',url,kw));return self.response({'uuid':'synthetic'})
class Tests(unittest.TestCase):
 def test_existing_login_compatibility(self):
  for body in ({}, {'objects':[]}, []):
   w=Wire(body);GenericClient(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic',login_method='session',session=w)
   w=Wire(body);o=VirtualRouterReads(api_endpoint='https://next.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic',login_method='session',session=w);self.assertEqual(o.get('safe-id'),{'uuid':'synthetic'});self.assertEqual([x[0] for x in w.calls],['POST','GET']);self.assertEqual(w.calls[0][1],'https://next.cloudsigma.com/api/2.0/accounts/action/');self.assertEqual(w.calls[0][2]['params'],{'do':'login'});self.assertEqual(w.headers['X-CSRFToken'],'synthetic')
if __name__=='__main__':unittest.main(verbosity=2)
