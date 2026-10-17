"""Existing websocket object waiters must forward their timeout argument.

No authentication, websocket connection, clock timing, or cloud resources.
"""
import unittest
from unittest.mock import Mock

from cloudsigma.resource import Websocket, WebsocketTimeoutError


class ObjectWaitTimeoutTests(unittest.TestCase):
    def make_waiter(self):
        # Deliberately bypass the effect-capable authentication constructor.
        ws = Websocket.__new__(Websocket)
        ws.timeout = 10
        ws.wait = Mock(return_value=[{'resource_uri': '/servers/example/'}])
        resource = Mock()
        resource.return_value.get_from_url.return_value = {'status': 'running'}
        return ws, resource

    def test_object_waiters_forward_timeout_and_preserve_results(self):
        for method, value, key in (
                ('wait_obj_type', 'servers', 'resource_type'),
                ('wait_obj_uri', '/servers/example/', 'resource_uri')):
            for timeout in (None, 0, 0.25, 25):
                with self.subTest(method=method, timeout=timeout):
                    ws, resource = self.make_waiter()
                    result = getattr(ws, method)(value, resource, timeout=timeout)
                    ws.wait.assert_called_once_with({key: value}, timeout=timeout)
                    resource.return_value.get_from_url.assert_called_once_with('/servers/example/')
                    self.assertEqual(result, {'status': 'running'})

    def test_object_waiters_preserve_timeout_failure_without_resource_read(self):
        for method in ('wait_obj_type', 'wait_obj_uri'):
            with self.subTest(method=method):
                ws, resource = self.make_waiter()
                failure = WebsocketTimeoutError('synthetic timeout')
                ws.wait.side_effect = failure
                with self.assertRaises(WebsocketTimeoutError) as raised:
                    getattr(ws, method)('example', resource, timeout=0.25)
                self.assertIs(raised.exception, failure)
                self.assertEqual(ws.wait.call_args.kwargs, {'timeout': 0.25})
                resource.assert_not_called()

    def test_status_wait_forwards_budget_through_object_waiter(self):
        ws, resource = self.make_waiter()
        result = ws.wait_for_status('/servers/example/', resource, 'running', timeout=0.25)
        ws.wait.assert_called_once_with({'resource_uri': '/servers/example/'}, timeout=0.25)
        self.assertEqual(result, {'status': 'running'})
