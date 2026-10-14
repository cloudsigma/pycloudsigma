import io
import unittest
from unittest.mock import patch
import requests
from cloudsigma.drive_download import DriveDownload, DownloadError

UUID='11111111-1111-1111-1111-111111111111'
ORIGIN='https://direct.zrh.cloudsigma.com'
class Raw(io.BytesIO):
    def read(self,n=-1,decode_content=False):
        assert decode_content is False
        return super().read(n)
class Reply:
    def __init__(self,q):
        self.url=q.url;self.status_code=200
        self.headers={'Content-Type':'application/octet-stream','Content-Length':'5'}
        self.raw=Raw(b'\x00\xffabc');self.closed=0
    def close(self):self.closed+=1;self.raw.close()
class TestDriveDownload(unittest.TestCase):
    def test_wire(self):
        for mode in ('binary','cross','return','deny','http','userinfo','loop','hops','policy','status','type','encoding','truncated','size','writer','timeout','cancel','midcancel','finalurl'):
            with self.subTest(mode=mode):
                calls=[];replies=[];cancel=[mode=='cancel'];out=io.BytesIO()
                class Fail:
                    def write(self,b):raise OSError('synthetic writer')
                def send(session,q,**kw):
                    calls.append(q);self.assertFalse(session.trust_env);self.assertEqual(kw['proxies'],{});self.assertTrue(kw['verify']);self.assertFalse(kw['allow_redirects']);self.assertTrue(kw['stream']);self.assertEqual(q.method,'GET');self.assertIsNone(q.body);self.assertNotIn('Cookie',q.headers)
                    self.assertEqual(q.headers['Accept-Encoding'],'identity')
                    if q.url.startswith(ORIGIN+'/'):self.assertEqual(q.headers['Authorization'],'Basic c3ludGhldGljOnN5bnRoZXRpYw==')
                    else:self.assertNotIn('Authorization',q.headers)
                    if len(calls)==1:self.assertEqual(q.url,ORIGIN+'/api/2.0/drives/'+UUID+'/download/')
                    if mode=='timeout':raise requests.Timeout('synthetic')
                    r=Reply(q);replies.append(r)
                    if mode in ('cross','return','deny','http','userinfo','loop','hops','policy') and (len(calls)==1 or mode=='hops' or mode=='return' and len(calls)==2):
                        r.status_code=302;r.headers['Location']='https://blob.example/image'
                        if mode=='http':r.headers['Location']='http://blob.example/x'
                        if mode=='userinfo':r.headers['Location']='https://u:p@blob.example/x'
                        if mode=='loop':r.headers['Location']=q.url
                        if mode=='hops':r.headers['Location']=q.url+'x'
                        if mode=='return' and len(calls)==2:r.headers['Location']=ORIGIN+'/returned'
                    if mode=='status':r.status_code=206
                    if mode=='type':r.headers['Content-Type']='text/html'
                    if mode=='encoding':r.headers['Content-Encoding']='gzip'
                    if mode=='truncated':r.raw=Raw(b'a')
                    if mode=='size':r.headers.pop('Content-Length');r.raw=Raw(b'123456')
                    if mode=='finalurl':r.url='https://foreign.example/'
                    if mode=='midcancel':
                        original=r.raw.read
                        def read(*a,**k):cancel[0]=True;return original(*a,**k)
                        r.raw.read=read
                    return r
                options=dict(max_bytes=5,timeout=1,cancelled=lambda:cancel[0])
                if mode!='deny':options.update(max_redirects=2,allow_redirect=lambda a,b:mode!='policy')
                with patch.object(requests.Session,'send',send):
                    api=DriveDownload(location='zrh',username='synthetic',password='synthetic')
                    if mode in ('binary','cross','return'):
                        self.assertEqual(api.download(UUID,out,**options),5);self.assertEqual(out.getvalue(),b'\x00\xffabc');self.assertEqual(len(calls),{'binary':1,'cross':2,'return':3}[mode])
                    else:
                        with self.assertRaises((DownloadError,OSError)):api.download(UUID,Fail() if mode=='writer' else out,**options)
                for r in replies:self.assertEqual(r.closed,1)
                self.assertFalse(out.closed)
                if mode=='cancel':self.assertEqual(calls,[])
                if mode=='midcancel':self.assertEqual(out.getvalue(),b'')
    def test_invalid(self):
        api=DriveDownload(location='zrh',username='synthetic',password='synthetic')
        with patch.object(requests.Session,'send',side_effect=AssertionError('dispatch')):
            for changes in ({'max_bytes':0},{'timeout':float('nan')},{'timeout':True},{'max_redirects':1},{'allow_redirect':True},{'cancelled':True}):
                o=dict(max_bytes=5,timeout=1);o.update(changes)
                with self.assertRaises(ValueError):api.download(UUID,io.BytesIO(),**o)
            with self.assertRaises(ValueError):api.download('../x',io.BytesIO(),max_bytes=5,timeout=1)
            for loc in ('https://evil','x.cloudsigma.com','../x','ZRH'):
                with self.assertRaises(ValueError):DriveDownload(location=loc,username='synthetic',password='synthetic')
    def test_isolation_and_baseline(self):
        from cloudsigma.generic import GenericClient
        c=GenericClient(api_endpoint='https://zrh.cloudsigma.com/api/2.0/',username='synthetic',password='synthetic')
        r=requests.Response();r.status_code=200;r._content=b'\x00\xff';r.url=c.api_endpoint
        with self.assertRaises(ValueError):c._process_response(r)
        # Generic JSON path mismatch, NOT requests' general streaming inability.
        borrowed=requests.Session();before=(borrowed.trust_env,dict(borrowed.headers),dict(borrowed.proxies))
        with patch.object(requests.Session,'send',lambda session,q,**kw:Reply(q)):
            DriveDownload(location='zrh',username='synthetic',password='synthetic').download(UUID,io.BytesIO(),max_bytes=5,timeout=1)
        self.assertEqual(before,(borrowed.trust_env,dict(borrowed.headers),dict(borrowed.proxies)));borrowed.close()
