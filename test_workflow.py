"""Checks of delivery invariants, independent of model wording."""
import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest

import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # Keep temporary test artifacts under the project, also on restricted hosts.
        self.temp = tempfile.TemporaryDirectory(prefix='.gate-test-', dir=w.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / 'run'
        w.initialize(self.run)
        for name in ('spec.json', 'cases.json'):
            shutil.copyfile(w.ROOT / 'examples/reference' / name, self.run / name)

    def approved(self):
        for stage in ('spec', 'cases'):
            w.approve(self.run, stage, 'test-fixture', mode='automated-test')

    def edit(self, name, change):
        value = w.read(self.run / name)
        change(value)
        w.write(self.run / name, value)

    def test_fabricated_source_rejected(self):
        self.edit('spec.json', lambda x: x['rules'][0]['source'].update(quote='This text is absent from the input'))
        with self.assertRaisesRegex(ValueError, 'source quote'):
            w.spec_check(self.run)

    def test_unresolved_rule_cannot_be_approved(self):
        self.edit('spec.json', lambda x: x['open_questions'].append('What happens on timeout?'))
        with self.assertRaisesRegex(ValueError, 'open questions'):
            w.approve(self.run, 'spec', 'test')

    def test_unknown_rule_reference_rejected(self):
        self.edit('cases.json', lambda x: x['cases'][0].update(rule_ids=['R999']))
        with self.assertRaisesRegex(ValueError, 'rule reference'):
            w.cases_check(self.run)

    def test_no_cases_is_not_success(self):
        w.write(self.run / 'cases.json', {'cases': []})
        with self.assertRaisesRegex(ValueError, '1..100'):
            w.cases_check(self.run)

    def test_missing_capability_rejected(self):
        self.edit('inputs/capabilities.json', lambda x: x['read_stock'].update(available=False))
        w.write(self.run / 'input-manifest.json', w.inputs(self.run))
        with self.assertRaisesRegex(ValueError, 'capability missing'):
            w.cases_check(self.run)

    def test_changed_input_invalidates_review_even_after_snapshot(self):
        self.approved()
        source = self.run / 'inputs/domain.md'
        source.write_text(source.read_text(encoding='utf-8') + '\nNew scope.\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            w.review_check(self.run, 'spec')
        w.write(self.run / 'input-manifest.json', w.inputs(self.run))
        with self.assertRaisesRegex(ValueError, 'changed after review'):
            w.review_check(self.run, 'spec')

    def test_changed_case_invalidates_review(self):
        self.approved()
        self.edit('cases.json', lambda x: x['cases'][0]['expect'].update(remaining_stock=4))
        with self.assertRaisesRegex(ValueError, 'changed after review'):
            w.render(self.run)

    def test_changed_generated_code_not_executed(self):
        self.approved()
        manifest = w.render(self.run)
        path = self.run / next(iter(manifest['files']))
        path.write_text(path.read_text(encoding='utf-8') + '\nraise RuntimeError("must not execute")\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'generated code changed'):
            w.run_tests(self.run)

    def test_duplicate_json_key_rejected(self):
        (self.run / 'spec.json').write_text('{"rules":[], "rules":[]}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            w.spec_check(self.run)

    def test_blocked_case_cannot_turn_partial_pass_into_delivery(self):
        def block(plan):
            plan['cases'][0].update(status='blocked', blocked_reason='Awaiting review of an extra scenario',
                                    initial_stock=None, requests=[], expect=None)
        self.edit('cases.json', block)
        self.approved()
        w.render(self.run)
        with contextlib.redirect_stdout(io.StringIO()):
            report = w.run_tests(self.run)
        self.assertEqual(report['status'], 'blocked')
        self.assertFalse(report['complete'])
        self.assertEqual(report['executed'], 9)
        self.assertEqual(len(report['blocked']), 1)
        self.assertTrue(all(r['status'] == 'passed' for r in report['records']))


if __name__ == '__main__':
    unittest.main()
