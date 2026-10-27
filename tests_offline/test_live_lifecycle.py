"""Lifecycle failure/ownership tests without SDK imports or live credentials."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'run_live_lifecycle', Path(__file__).parents[1] / 'ci/run_live_lifecycle.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
IDENTITY = 'a6bc5852-12c1-4873-917e-b520ac15503c'


class ProviderFailure(Exception):
    def __init__(self, status_code=500):
        self.status_code = status_code
        super().__init__('provider body must not escape')


class Resource:
    def __init__(self):
        self.calls = []
        self.value = None
        self.delete_delay = 0
        self.delete_pending = False

    def create(self, data):
        self.calls.append(('create', dict(data)))
        self.value = dict(data, uuid=IDENTITY, resources=[])
        if 'size' in data:
            self.value.update(status='unmounted', mounted_on=[])
        return self.value.copy()

    def get(self, identity):
        self.calls.append(('get', identity))
        if self.delete_pending:
            if self.delete_delay:
                self.delete_delay -= 1
            else:
                self.value = None
        if self.value is None:
            raise ProviderFailure(404)
        return self.value.copy()

    def update(self, identity, data):
        self.calls.append(('update', identity, dict(data)))
        self.value.update(data)
        return self.value.copy()

    def delete(self, identity):
        self.calls.append(('delete', identity))
        self.delete_pending = True


class LiveLifecycleTests(unittest.TestCase):
    def test_successful_tag_lifecycle_confirms_absence_without_listing(self):
        client = Resource()
        client.delete_delay = 1
        report = runner.run_scenario(client, attempts=3, sleep=lambda _: None)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['cleanup']['absence_confirmed'])
        self.assertIsNone(client.value)
        self.assertEqual([c[0] for c in client.calls].count('create'), 1)
        self.assertEqual([c[0] for c in client.calls].count('delete'), 1)
        self.assertIn('read_updated', report['checks'])
        self.assertTrue(all(c[1] == IDENTITY for c in client.calls
                            if c[0] != 'create'))

    def test_drive_is_fixed_size_and_never_attached_or_started(self):
        client = Resource()
        report = runner.run_scenario(client, 'drive', sleep=lambda _: None)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(client.calls[0][1]['size'], 1024 ** 3)
        self.assertEqual(client.calls[0][1]['media'], 'disk')
        self.assertTrue(all(c[0] in ('create', 'get', 'update', 'delete')
                            for c in client.calls))

    def test_update_transport_failure_preserves_failure_and_cleans_owned_id(self):
        client = Resource()
        def update(identity, data):
            client.calls.append(('update', identity, data))
            client.value.update(data)
            raise ProviderFailure()
        client.update = update
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['failure']['status_code'], 500)
        self.assertEqual(report['cleanup']['status'], 'deleted')
        self.assertNotIn('provider body', json.dumps(report))
        self.assertEqual([c[0] for c in client.calls].count('update'), 1)

    def test_ambiguous_create_is_never_replayed_or_adopted(self):
        client = Resource()
        original = client.create
        def ambiguous(data):
            original(data)
            raise ProviderFailure()
        client.create = ambiguous
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['cleanup']['status'], 'manual_review_required')
        self.assertEqual([c[0] for c in client.calls], ['create'])
        self.assertNotIn('resource_id', report)

    def test_wrong_creation_name_never_becomes_owned(self):
        client = Resource()
        original = client.create
        def wrong(data):
            original(data)
            return dict(client.value, name='pre-existing-object')
        client.create = wrong
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual([c[0] for c in client.calls], ['create'])

    def test_ownership_change_prevents_update_and_delete(self):
        client = Resource()
        original = client.get
        def changed(identity):
            current = original(identity)
            return dict(current, name='different-owner')
        client.get = changed
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['cleanup']['status'], 'manual_review_required')
        self.assertFalse(any(c[0] in ('update', 'delete') for c in client.calls))

    def test_mounted_drive_cannot_be_mutated_or_cleaned(self):
        client = Resource()
        original = client.get
        def mounted(identity):
            return dict(original(identity), mounted_on=[{'server': 'existing'}])
        client.get = mounted
        report = runner.run_scenario(client, 'drive', sleep=lambda _: None)
        self.assertEqual(report['cleanup']['status'], 'manual_review_required')
        self.assertFalse(any(c[0] in ('update', 'delete') for c in client.calls))

    def test_delete_timeout_is_reported_without_repeating_delete(self):
        client = Resource()
        client.delete_delay = 100
        report = runner.run_scenario(client, attempts=2, sleep=lambda _: None)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['cleanup']['status'], 'manual_review_required')
        self.assertEqual([c[0] for c in client.calls].count('delete'), 1)
        self.assertLessEqual(len(client.calls), 8)

    def test_cleanup_is_idempotent_when_object_already_absent(self):
        client = Resource()
        report = runner._cleanup(client, IDENTITY, {'run'}, 'tags', 2,
                                 lambda _: None)
        self.assertEqual(report['status'], 'absent')
        self.assertEqual(client.calls, [('get', IDENTITY)])

    def test_configuration_refuses_other_endpoint_without_importing_sdk(self):
        environment = {'CLOUDSIGMA_QA_ALLOW_MUTATIONS': 'true',
                       'CLOUDSIGMA_QA_ENDPOINT': 'https://other.example/api/2.0/',
                       'CLOUDSIGMA_QA_USERNAME': 'synthetic',
                       'CLOUDSIGMA_QA_PASSWORD': 'private-test-value'}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(runner.main(environment), 2)
        self.assertNotIn('private-test-value', out.getvalue())

    def test_mutation_requires_explicit_gate(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(runner.main({}), 2)
        self.assertEqual(json.loads(out.getvalue())['error_type'],
                         'ConfigurationError')

    def test_recovery_receipts_precede_creation_and_cleanup(self):
        client = Resource()
        receipts = []
        def emit(value):
            receipts.append((value, [c[0] for c in client.calls]))
        report = runner.run_scenario(client, sleep=lambda _: None, emit=emit)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(receipts[0][0]['phase'], 'create_attempt')
        self.assertEqual(receipts[0][1], [])
        self.assertEqual(receipts[1][0]['resource_id'], IDENTITY)
        self.assertEqual(receipts[1][1], ['create'])

    def test_signal_requests_cleanup_after_acknowledged_creation(self):
        client = Resource()
        def interrupted(identity, data):
            client.calls.append(('update', identity, data))
            raise runner.AcceptanceInterrupted('termination requested')
        client.update = interrupted
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['cleanup']['status'], 'deleted')

    def test_ambiguous_delete_is_not_retried(self):
        client = Resource()
        def ambiguous(identity):
            client.calls.append(('delete', identity))
            raise ProviderFailure()
        client.delete = ambiguous
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['cleanup']['status'], 'manual_review_required')
        self.assertEqual([c[0] for c in client.calls].count('delete'), 1)
        self.assertEqual(report['resource_id'], IDENTITY)

    def test_associated_tag_is_not_deleted(self):
        client = Resource()
        original = client.get
        def associated(identity):
            return dict(original(identity), resources=['pre-existing-server'])
        client.get = associated
        report = runner.run_scenario(client, sleep=lambda _: None)
        self.assertEqual(report['cleanup']['status'], 'manual_review_required')
        self.assertFalse(any(c[0] in ('update', 'delete') for c in client.calls))

    def test_invalid_attempt_budget_refuses_before_create(self):
        client = Resource()
        for attempts in (0, 100, True):
            with self.assertRaises(ValueError):
                runner.run_scenario(client, attempts=attempts)
        self.assertEqual(client.calls, [])


if __name__ == '__main__':
    unittest.main()
