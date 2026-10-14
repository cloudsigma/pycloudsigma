import io
import unittest
from unittest.mock import patch
import requests
from requests.structures import CaseInsensitiveDict
from cloudsigma.drive_download import DriveDownload, DownloadError, _DownloadSession

class Raw:
    def __init__(self,data,cancel=None):self.data=io.BytesIO(data);self.consumed=0;self.closed=0;self.released=0;self.cancel=cancel
    def read(self,n=-1,decode_content=False):
        assert decode_content is False
        b=self.data.read(n);self.consumed+=len(b)
        if self.cancel:self.cancel[0]=True
        return b
    def close(self):self.closed+=1
    def release_conn(self):self.released+=1
class TestRealDownloadAdapter(unittest.TestCase):
    def test_actual_requests(self):
        for mode in ('deny','allowed','control','space','userinfo','http','size','truncated','cancel','writer','policy-error','read-error','transport'):
            with self.subTest(mode=mode):
                raws=[];calls=[];closed=[];cancel=[False]
                originalclose=requests.Session.close
                def close(s):closed.append(s);originalclose(s)
                def send(adapter,q,**kw):
                    calls.append(q);self.assertTrue(kw['stream']);self.assertTrue(kw['verify']);self.assertEqual(kw['proxies'],{})
                    if mode=='transport':raise requests.Timeout('synthetic')
                    redirect=len(calls)==1 and mode in ('deny','allowed','control','space','userinfo','http','policy-error')
                    raw=Raw(b'x'*10000 if redirect else b'12345',cancel if mode=='cancel' else None);raws.append(raw)
                    r=requests.Response();r.status_code=302 if redirect else 200;r.url=q.url;r.request=q;r.raw=raw;r.headers=CaseInsensitiveDict({'Content-Type':'application/octet-stream','Content-Length':'5'})
                    if redirect:
                        r.headers['Location']={'control':'https://blob.example/\tx','space':' https://blob.example/x','userinfo':'https://u:***@blob.example/x','http':'http://blob.example/x'}.get(mode,'https://blob.example/x')
                    if mode=='size':raw.data=io.BytesIO(b'123456');r.headers.pop('Content-Length')
                    if mode=='truncated':raw.data=io.BytesIO(b'1')
                    if mode=='read-error':
                        def read(*a,**k):raise OSError('synthetic read')
                        raw.read=read
                    if len(calls)>1:self.assertNotIn('Authorization',q.headers)
                    return r
                def policy(a,b):
                    if mode=='policy-error':raise ValueError('synthetic policy')
                    return True
                class Writer:
                    def write(self,b):raise OSError('synthetic writer')
                options=dict(max_bytes=5,timeout=1,cancelled=lambda:cancel[0])
                if mode!='deny':options.update(max_redirects=1,allow_redirect=policy)
                with patch.object(requests.adapters.HTTPAdapter,'send',send),patch.object(_DownloadSession,'close',close):
                    api=DriveDownload(location='zrh',username='synthetic',password='***');out=io.BytesIO()
                    if mode=='allowed':self.assertEqual(api.download('11111111-1111-1111-1111-111111111111',out,**options),5)
                    else:
                        with self.assertRaises((DownloadError,OSError,ValueError)):api.download('11111111-1111-1111-1111-111111111111',Writer() if mode=='writer' else out,**options)
                self.assertEqual(len(closed),1)
                for raw in raws:self.assertEqual(raw.closed,1);self.assertEqual(raw.released,1)
                if mode in ('deny','allowed','control','space','userinfo','http','policy-error'):self.assertEqual(raws[0].consumed,0)
                if mode=='allowed':self.assertEqual(len(calls),2);self.assertEqual(out.getvalue(),b'12345')
                elif mode!='transport':self.assertEqual(len(calls),1)
                if mode=='size':self.assertLessEqual(raws[0].consumed,6)
