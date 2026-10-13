import os,unittest,requests
os.environ['CLOUDSIGMA_CONFIG']='/dev/null'
from cloudsigma.generic import GenericClient
from cloudsigma.errors import ApiClientError
class Tests(unittest.TestCase):
 def test_reject_zero_dispatch(self):
  for url in ['//other.invalid/path','///other.invalid/path','////other.invalid/path','///u:p@other.invalid/path','https://u:p@example.invalid/x','https://example.invalid:bad/x','https://example.invalid:99999/x','https://[bad/x','https://example.invalid:/x','https://other.invalid/x','http://example.invalid/x','https://example.invalid\\@other.invalid/x','/%2f%2fother.invalid/x','/%5cother.invalid/x','https://example.invalid%40other.invalid/x']:
   with self.subTest(url=url):
    calls=[]
    class Fake:
     def get(self,*a,**kw):calls.append(1);raise AssertionError('foreign dispatch')
    c=GenericClient(api_endpoint='https://example.invalid/api/2.0/',username='synthetic',password='synthetic',session=Fake())
    with self.assertRaises(ApiClientError):c.get(url)
    self.assertEqual(calls,[])
 def test_allowed_final_origin(self):
  for endpoint,url in [('https://example.invalid/api/2.0/','tags/'),('https://example.invalid/api/2.0/','/tags/'),('https://example.invalid/api/2.0/','/api/2.0/tags/'),('https://example.invalid/api/2.0/','https://EXAMPLE.invalid:443/api/2.0/tags/'),('http://custom.invalid:8080/api/','item/')]:
   calls=[]
   class Fake:
    def get(self,url,**kw):calls.append(url);r=requests.Response();r.status_code=200;r._content=b'{}';return r
   c=GenericClient(api_endpoint=endpoint,username='synthetic',password='synthetic',session=Fake());self.assertEqual(c.get(url),{});self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main(verbosity=2)
