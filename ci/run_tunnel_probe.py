"""Probe read-only tunnel route variants without exposing response bodies.

This diagnostic distinguishes an SDK route defect from a provider or location
that has not enabled the documented tunnel resource. It makes only GET
requests, refuses redirects, and emits status/header metadata plus a bounded
JSON response shape. Credentials and response values are never printed.
"""

import json
import os
import sys
import time
from urllib.parse import urljoin

import requests


ENDPOINT = os.environ.get(
    'CLOUDSIGMA_QA_ENDPOINT',
    'https://next.cloudsigma.com/api/2.0/',
)
ALLOWED_ENDPOINT = 'https://next.cloudsigma.com/api/2.0/'
USERNAME = os.environ.get('CLOUDSIGMA_QA_USERNAME')
PASSWORD = os.environ.get('CLOUDSIGMA_QA_PASSWORD')

ROUTES = (
    ('api_root', '', frozenset((200,))),
    ('capabilities', 'capabilities/', frozenset((200,))),
    ('cloud_status', 'cloud_status/', frozenset((200,))),
    # The current provider deliberately returns 404 for collection GET; retain
    # that as evidence while allowing a future 200 when the endpoint is enabled.
    ('tunnels_canonical', 'tunnels/', frozenset((200, 404))),
    # Tastypie redirects the slashless spelling to the canonical route.
    ('tunnels_without_slash', 'tunnels', frozenset((200, 301))),
    # The provider currently exposes a broken/unavailable schema endpoint.
    ('tunnels_schema', 'tunnels/schema/', frozenset((200, 404, 500))),
    ('virtualrouters_legacy', 'virtualrouters/', frozenset((200,))),
    ('virtualrouters_underscored', 'virtual_routers/', frozenset((200,))),
)


def _shape(response):
    """Return a non-sensitive shape summary for a JSON response."""
    content_type = response.headers.get('Content-Type', '')
    if 'json' not in content_type.lower():
        return {'content_type': content_type or None}
    try:
        value = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return {'content_type': content_type, 'json': 'invalid'}
    if isinstance(value, dict):
        return {'content_type': content_type, 'type': 'dict', 'key_count': len(value)}
    if isinstance(value, list):
        return {'content_type': content_type, 'type': 'list', 'count': len(value)}
    return {'content_type': content_type, 'type': type(value).__name__}


def _url(path):
    endpoint = ENDPOINT if ENDPOINT.endswith('/') else ENDPOINT + '/'
    return urljoin(endpoint, path)


def probe(session=None):
    """Probe all documented and diagnostic route variants."""
    if not USERNAME or not PASSWORD or ENDPOINT != ALLOWED_ENDPOINT:
        return {
            'status': 'failed',
            'error_type': 'ConfigurationError',
            'message': 'QA credentials and the fixed Next QA endpoint are required',
            'checks': [],
        }
    client = session or requests.Session()
    client.auth = (USERNAME, PASSWORD)
    client.trust_env = False
    checks = []
    for name, path, expected_statuses in ROUTES:
        url = _url(path)
        started = time.monotonic()
        try:
            # Limit collection reads to one object. No pagination is followed.
            params = {'limit': 1} if name.startswith('virtualrouters_') else None
            response = client.get(
                url,
                headers={'Accept': 'application/json'},
                timeout=15,
                allow_redirects=False,
                params=params,
            )
        except requests.RequestException as exc:
            checks.append({
                'name': name,
                'path': path,
                'status': 'transport_error',
                'error_type': type(exc).__name__,
                'elapsed_ms': round((time.monotonic() - started) * 1000),
            })
            continue
        if response.status_code in (401, 403):
            status = 'authentication_or_permission_failure'
        elif response.status_code not in expected_statuses:
            status = 'unexpected_redirect' if 300 <= response.status_code < 400 else (
                'unexpected_provider_error' if response.status_code >= 500 else
                'unexpected_http_status')
        elif response.status_code == 404:
            status = 'provider_unavailable'
        elif response.status_code == 500:
            status = 'schema_unavailable'
        elif 300 <= response.status_code < 400:
            target = urljoin(url, response.headers.get('Location', ''))
            status = ('redirect_observed' if target == _url('tunnels/')
                      else 'unexpected_redirect')
        else:
            status = 'passed'
        checks.append({
            'name': name,
            'path': path,
            'status': status,
            'status_code': response.status_code,
            'allow': response.headers.get('Allow'),
            'content_type': response.headers.get('Content-Type'),
            'request_id': response.headers.get('X-REQUEST-ID'),
            'location_present': bool(response.headers.get('Location')),
            'shape': _shape(response),
            'elapsed_ms': round((time.monotonic() - started) * 1000),
        })
    failures = [
        item for item in checks
        if item['status'] in (
                'transport_error', 'authentication_or_permission_failure',
                'unexpected_provider_error', 'unexpected_http_status',
                'unexpected_redirect')
    ]
    gaps = sum(item['status'] in ('provider_unavailable', 'schema_unavailable')
               for item in checks)
    if session is None:
        client.close()
    return {
        'endpoint': ENDPOINT,
        'status': 'failed' if failures else ('passed_with_known_gaps' if gaps else 'passed'),
        'checks': checks,
        'failed': len(failures),
        'known_provider_gaps': gaps,
    }


def main():
    result = probe()
    print(json.dumps(result, sort_keys=True))
    return 1 if result['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
