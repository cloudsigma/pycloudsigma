"""Read-only authenticated smoke checks for the next CloudSigma QA account.

The runner intentionally performs no create, update, delete, action, upload,
or websocket operations. It emits only check names, result state, response
shape, elapsed time, and typed error metadata; response bodies and credentials
are never printed.
"""
import json
import os
import sys
import time

from cloudsigma import errors, resource


ENDPOINT = os.environ.get(
    'CLOUDSIGMA_QA_ENDPOINT',
    'https://next.cloudsigma.com/api/2.0/',
)
USERNAME = os.environ.get('CLOUDSIGMA_QA_USERNAME')
PASSWORD = os.environ.get('CLOUDSIGMA_QA_PASSWORD')


def _shape(value):
    if isinstance(value, list):
        return {'type': 'list', 'count': len(value)}
    if isinstance(value, dict):
        return {'type': 'dict', 'key_count': len(value)}
    return {'type': type(value).__name__}


def main():
    if not USERNAME or not PASSWORD:
        print(json.dumps({
            'endpoint': ENDPOINT,
            'status': 'failed',
            'error_type': 'ConfigurationError',
            'message': 'CLOUDSIGMA_QA_USERNAME and CLOUDSIGMA_QA_PASSWORD are required',
        }, sort_keys=True))
        return 2

    common = {
        'api_endpoint': ENDPOINT,
        'username': USERNAME,
        'password': PASSWORD,
        'login_method': 'basic',
        'timeout': 15,
    }
    checks = []

    def check(name, operation, allow_404=False):
        started = time.monotonic()
        try:
            value = operation()
        except errors.ClientError as exc:
            if allow_404 and exc.status_code == 404:
                checks.append({
                    'name': name,
                    'status': 'skipped',
                    'reason': 'provider returned HTTP 404',
                    'elapsed_ms': round((time.monotonic() - started) * 1000),
                })
                return
            checks.append({
                'name': name,
                'status': 'failed',
                'error_type': type(exc).__name__,
                'status_code': exc.status_code,
                'elapsed_ms': round((time.monotonic() - started) * 1000),
            })
            return
        except Exception as exc:  # pragma: no cover - provider/transport boundary
            checks.append({
                'name': name,
                'status': 'failed',
                'error_type': type(exc).__name__,
                'elapsed_ms': round((time.monotonic() - started) * 1000),
            })
            return
        checks.append({
            'name': name,
            'status': 'passed',
            'shape': _shape(value),
            'elapsed_ms': round((time.monotonic() - started) * 1000),
        })

    check('profile.get', lambda: resource.Profile(**common).get())
    check('locations.list', lambda: resource.Locations(**common).list({'limit': 1}))
    check('capabilities.list', lambda: resource.Capabilities(**common).list({'limit': 1}))
    check('usage.list', lambda: resource.Usage(**common).list({'limit': 1}))
    check('virtualrouters.list', lambda: resource.VirtualRouters(**common).list({'limit': 1}))
    check(
        'vpn_tunnels.list',
        lambda: resource.VpnTunnels(**common).list({'limit': 1}),
        allow_404=True,
    )

    failed = [item for item in checks if item['status'] == 'failed']
    print(json.dumps({
        'endpoint': ENDPOINT,
        'checks': checks,
        'passed': sum(item['status'] == 'passed' for item in checks),
        'skipped': sum(item['status'] == 'skipped' for item in checks),
        'failed': len(failed),
    }, sort_keys=True))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
