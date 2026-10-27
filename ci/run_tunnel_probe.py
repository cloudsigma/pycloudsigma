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
USERNAME = os.environ.get('CLOUDSIGMA_QA_USERNAME')
PASSWORD = os.environ.get('CLOUDSIGMA_QA_PASSWORD')

ROUTES = (
    ('api_root', ''),
    ('capabilities', 'capabilities/'),
    ('cloud_status', 'cloud_status/'),
    ('tunnels_canonical', 'tunnels/'),
    ('tunnels_without_slash', 'tunnels'),
    ('tunnels_schema', 'tunnels/schema/'),
    ('virtualrouters_legacy', 'virtualrouters/'),
    ('virtualrouters_underscored', 'virtual_routers/'),
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
    if not USERNAME or not PASSWORD:
        return {
            'status': 'failed',
            'error_type': 'ConfigurationError',
            'message': 'CLOUDSIGMA_QA_USERNAME and CLOUDSIGMA_QA_PASSWORD are required',
            'checks': [],
        }
    client = session or requests.Session()
    client.auth = (USERNAME, PASSWORD)
    client.trust_env = False
    checks = []
    for name, path in ROUTES:
        url = _url(path)
        started = time.monotonic()
        try:
            response = client.get(
                url,
                headers={'Accept': 'application/json'},
                timeout=15,
                allow_redirects=False,
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
        status = 'passed' if response.status_code < 400 else 'provider_unavailable'
        if response.status_code >= 500:
            status = 'unexpected_provider_error'
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
        if item['status'] in ('transport_error', 'unexpected_provider_error')
    ]
    return {
        'endpoint': ENDPOINT,
        'status': 'failed' if failures else 'passed',
        'checks': checks,
        'failed': len(failures),
    }


def main():
    result = probe()
    print(json.dumps(result, sort_keys=True))
    return 1 if result['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
