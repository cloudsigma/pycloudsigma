"""Bounded QA lifecycles using the installed SDK and exclusively owned objects.

This runner deliberately does not discover the legacy acceptance suite. In
particular its tag setup removes account-wide resources. Only the fresh IDs
acknowledged by this process are eligible for mutation or cleanup here.
"""
import json
import os
import signal
import sys
import time
import uuid

ENDPOINT = 'https://next.cloudsigma.com/api/2.0/'
DRIVE_SIZE = 1024 ** 3
POLL_ATTEMPTS = 8
POLL_INTERVAL = 2


class AcceptanceError(Exception):
    """A bounded acceptance assertion failed."""


class OwnershipError(AcceptanceError):
    """An object cannot be safely identified as this invocation's object."""


class AcceptanceInterrupted(AcceptanceError):
    """A termination signal requested cleanup of the active lifecycle."""


def _safe_error(exc):
    result = {'error_type': type(exc).__name__}
    status = getattr(exc, 'status_code', None)
    if type(status) is int:
        result['status_code'] = status
    return result


def _valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _owned(value, identity, names, scenario):
    if not isinstance(value, dict):
        raise OwnershipError('non-object response')
    if value.get('uuid') != identity or value.get('name') not in names:
        raise OwnershipError('identity or run name mismatch')
    if scenario == 'drive':
        if value.get('mounted_on') != []:
            raise OwnershipError('drive is mounted or mount state is unknown')
    elif value.get('resources') != []:
        raise OwnershipError('tag associations are present or unknown')
    return value


def _read_until(resource, identity, names, scenario, expected_name,
                attempts, sleep):
    for attempt in range(attempts):
        try:
            value = resource.get(identity)
        except Exception as exc:
            # Creation visibility may lag; every other provider error fails.
            if getattr(exc, 'status_code', None) != 404:
                raise
        else:
            value = _owned(value, identity, names, scenario)
            ready = scenario != 'drive' or value.get('status') == 'unmounted'
            if value['name'] == expected_name and ready:
                if scenario == 'drive' and value.get('size') != DRIVE_SIZE:
                    raise AcceptanceError('drive size does not match request')
                return value
        if attempt + 1 < attempts:
            sleep(POLL_INTERVAL)
    raise AcceptanceError('object did not converge within read budget')


def _cleanup(resource, identity, names, scenario, attempts, sleep):
    try:
        current = resource.get(identity)
    except Exception as exc:
        if getattr(exc, 'status_code', None) == 404:
            return {'status': 'absent'}
        raise
    _owned(current, identity, names, scenario)
    # Never repeat DELETE, including after a transport failure with an unknown
    # provider outcome. Subsequent polling only checks absence.
    resource.delete(identity)
    for attempt in range(attempts):
        try:
            remaining = resource.get(identity)
        except Exception as exc:
            if getattr(exc, 'status_code', None) == 404:
                return {'status': 'deleted', 'absence_confirmed': True}
            raise
        _owned(remaining, identity, names, scenario)
        if attempt + 1 < attempts:
            sleep(POLL_INTERVAL)
    raise AcceptanceError('deletion did not converge within read budget')


def run_scenario(resource, scenario='tags', *, attempts=POLL_ATTEMPTS,
                 sleep=time.sleep, emit=None):
    """Run one isolated CRUD cycle; failures and cleanup failures both survive.

    ``resource`` is a real SDK Tags/Drive instance in production and a strict
    in-memory resource in offline tests. It is never allowed to list objects or
    adopt an existing one, even if an earlier run used a similar name.
    """
    if scenario not in ('tags', 'drive'):
        raise ValueError('unsupported scenario')
    if type(attempts) is not int or not 1 <= attempts <= POLL_ATTEMPTS:
        raise ValueError('invalid read attempt budget')
    name = 'pycloudsigma-qa-' + uuid.uuid4().hex
    updated_name = name + '-updated'
    result = {'scenario': scenario, 'run_name': name, 'status': 'failed',
              'checks': [], 'cleanup': {'status': 'not_created'}}
    identity = None
    names = {name}
    creation_started = False
    try:
        definition = {'name': name}
        if scenario == 'drive':
            definition.update({'media': 'disk', 'size': DRIVE_SIZE})
        if emit is not None:
            emit({'scenario': scenario, 'run_name': name,
                  'phase': 'create_attempt'})
        creation_started = True
        created = resource.create(definition)
        candidate = created.get('uuid') if isinstance(created, dict) else None
        if not _valid_uuid(candidate) or created.get('name') != name:
            raise OwnershipError('creation acknowledgement is ambiguous')
        # A matching name and canonical provider-assigned ID establish custody.
        identity = candidate
        result['resource_id'] = identity
        if emit is not None:
            emit({'scenario': scenario, 'run_name': name,
                  'resource_id': identity, 'phase': 'create_acknowledged'})
        result['checks'].append('create')
        _read_until(resource, identity, names, scenario, name, attempts, sleep)
        result['checks'].append('read_created')
        names.add(updated_name)
        update = {'name': updated_name}
        if scenario == 'tags':
            update['resources'] = []
        else:
            # The documented drive edit request carries the mutable drive
            # definition, rather than a name-only patch.  The next provider
            # rejects the latter with HTTP 400 even though the API prose says
            # that name is independently editable.
            update.update({'media': 'disk', 'size': DRIVE_SIZE})
        updated = resource.update(identity, update)
        _owned(updated, identity, names, scenario)
        if updated.get('name') != updated_name:
            raise AcceptanceError('update acknowledgement has the wrong name')
        result['checks'].append('update')
        _read_until(resource, identity, names, scenario, updated_name,
                    attempts, sleep)
        result['checks'].append('read_updated')
        result['status'] = 'passed'
    except Exception as exc:
        result['failure'] = _safe_error(exc)
        if creation_started and identity is None:
            result['cleanup'] = {
                'status': 'manual_review_required',
                'reason': 'create outcome or ownership is not established',
            }
    finally:
        if identity is not None:
            try:
                result['cleanup'] = _cleanup(
                    resource, identity, names, scenario, attempts, sleep)
                result['checks'].append('delete_and_confirm_absence')
            except Exception as exc:
                result['status'] = 'failed'
                result['cleanup'] = {
                    'status': 'manual_review_required', **_safe_error(exc)}
    return result


def _interrupted(signum, frame):
    raise AcceptanceInterrupted('termination requested')


def main(environ=None):
    environ = os.environ if environ is None else environ
    if (environ.get('CLOUDSIGMA_QA_ALLOW_MUTATIONS') != 'true'
            or environ.get('CLOUDSIGMA_QA_ENDPOINT', ENDPOINT) != ENDPOINT
            or not environ.get('CLOUDSIGMA_QA_USERNAME')
            or not environ.get('CLOUDSIGMA_QA_PASSWORD')):
        print(json.dumps({'status': 'failed', 'error_type': 'ConfigurationError'}))
        return 2
    scenarios = environ.get('CLOUDSIGMA_QA_SCENARIOS', 'tags').split(',')
    if (not scenarios or len(scenarios) != len(set(scenarios))
            or any(item not in ('tags', 'drive') for item in scenarios)):
        print(json.dumps({'status': 'failed', 'error_type': 'ConfigurationError'}))
        return 2
    # Configuration is validated before importing any SDK config or networking.
    from cloudsigma import resource
    common = dict(api_endpoint=ENDPOINT,
                  username=environ['CLOUDSIGMA_QA_USERNAME'],
                  password=environ['CLOUDSIGMA_QA_PASSWORD'],
                  login_method='basic', timeout=(5, 10), trust_env=False)
    previous = signal.signal(signal.SIGTERM, _interrupted)
    results = []
    try:
        for scenario in scenarios:
            factory = resource.Tags if scenario == 'tags' else resource.Drive
            result = run_scenario(
                factory(**common), scenario,
                emit=lambda value: print(json.dumps(value, sort_keys=True),
                                         flush=True))
            results.append(result)
            # Persist each completed scenario in logs, including manual recovery
            # identity, before running another scenario. No response is emitted.
            print(json.dumps(result, sort_keys=True), flush=True)
            if result['status'] != 'passed':
                break
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 0 if all(item['status'] == 'passed' for item in results) else 1


if __name__ == '__main__':
    sys.exit(main())
