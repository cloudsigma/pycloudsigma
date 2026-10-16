"""Existing get_from_url must preserve GET filters, not encode them as path."""
import unittest
import requests
from cloudsigma.resource import Server


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self):
        self.urls = []

    def send(self, request, **kwargs):
        self.urls.append(request.url)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"objects": []}'
        response.request = request
        return response

    def close(self):
        pass


class QueryURLTests(unittest.TestCase):
    def test_get_from_url_preserves_query(self):
        for prefix in ('/api/2.0/servers/', 'servers/',
                       'https://fixture.invalid/api/2.0/servers/'):
            for query in ('limit=2&offset=3', 'tag__name=one&tag__name=two',
                          'name=a%2Bb%26c', 'name=last/'):
                with self.subTest(prefix=prefix, query=query):
                    with requests.Session() as session:
                        adapter = Adapter()
                        session.mount('https://', adapter)
                        server = Server(api_endpoint='https://fixture.invalid/api/2.0/',
                                        username='fixture', password='synthetic', session=session)
                        self.assertEqual(server.get_from_url(prefix + '?' + query), [])
                        self.assertEqual(adapter.urls, [
                            'https://fixture.invalid/api/2.0/servers/?' + query])

    def test_missing_path_slash_is_normalized_before_query(self):
        with requests.Session() as session:
            adapter = Adapter()
            session.mount('https://', adapter)
            server = Server(api_endpoint='https://fixture.invalid/api/2.0/',
                            username='fixture', password='synthetic', session=session)
            self.assertEqual(server.get_from_url('servers?limit=2'), [])
            self.assertEqual(adapter.urls, ['https://fixture.invalid/api/2.0/servers/?limit=2'])
