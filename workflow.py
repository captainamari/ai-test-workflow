"""Python 3.10+ standard-library teaching pipeline; no model API dependency."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parent
CAPABILITIES = {'create_item', 'reserve_raw', 'read_stock', 'count_reservations', 'delete_item'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    def invalid_constant(value):
        raise ValueError('non-JSON constant: ' + value)
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid_constant,
                      object_pairs_hook=unique_pairs)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fields(value, expected, where):
    require(isinstance(value, dict) and set(value) == set(expected), where + ': unexpected/missing fields')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def inputs(run):
    directory = run / 'inputs'
    require(directory.is_dir(), 'inputs directory missing')
    files = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'symlinks are unsupported in input snapshots')
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = sha(path)
    require(files, 'empty inputs')
    return files


def snapshot(run):
    current = inputs(run)
    require(current == read(run / 'input-manifest.json'),
            'inputs changed: create a new run or snapshot again and re-review downstream artifacts')
    return current


def spec_check(run):
    snapshot(run)
    spec = read(run / 'spec.json')
    fields(spec, ['rules', 'open_questions'], 'spec')
    require(isinstance(spec['open_questions'], list) and
            all(nonempty(q) for q in spec['open_questions']), 'invalid open_questions')
    require(isinstance(spec['rules'], list) and spec['rules'], 'empty/invalid rules')
    ids = set()
    manifest = inputs(run)
    for rule in spec['rules']:
        fields(rule, ['id', 'statement', 'source'], 'rule')
        require(isinstance(rule['id'], str) and re.fullmatch(r'R[0-9]+', rule['id']), 'invalid rule id')
        require(rule['id'] not in ids, 'duplicate rule: ' + rule['id'])
        ids.add(rule['id'])
        require(nonempty(rule['statement']), 'empty rule statement')
        fields(rule['source'], ['file', 'quote'], 'source')
        source = rule['source']
        require(isinstance(source['file'], str) and source['file'] in manifest, 'unknown source file')
        require(nonempty(source['quote']) and len(source['quote'].strip()) >= 8, 'source quote too short')
        require(source['quote'] in (run / 'inputs' / source['file']).read_text(encoding='utf-8'),
                'source quote does not occur in input: ' + rule['id'])
    return spec


def cases_check(run):
    spec = spec_check(run)
    plan = read(run / 'cases.json')
    fields(plan, ['cases'], 'plan')
    require(isinstance(plan['cases'], list) and 0 < len(plan['cases']) <= 100, 'cases must contain 1..100 items')
    known = {r['id'] for r in spec['rules']}
    used, ids = set(), set()
    codes = read(run / 'inputs/contract.json')['business_codes']
    caps = read(run / 'inputs/capabilities.json')
    for case in plan['cases']:
        fields(case, ['id', 'title', 'rule_ids', 'status', 'blocked_reason', 'initial_stock', 'requests', 'expect'], 'case')
        require(isinstance(case['id'], str) and re.fullmatch(r'C[0-9]+', case['id']), 'invalid case id')
        require(case['id'] not in ids, 'duplicate case id')
        ids.add(case['id'])
        require(nonempty(case['title']), 'case title missing')
        refs = case['rule_ids']
        require(isinstance(refs, list) and refs and all(isinstance(x, str) for x in refs), 'invalid rule_ids')
        require(len(refs) == len(set(refs)) and set(refs) <= known, 'duplicate/unknown rule reference')
        used.update(refs)
        require(case['status'] in ('ready', 'blocked'), 'invalid case status')
        if case['status'] == 'blocked':
            require(nonempty(case['blocked_reason']), 'blocked case needs a reason')
            require(case['initial_stock'] is None and case['requests'] == [] and case['expect'] is None,
                    'blocked case must not contain invented executable values')
            continue
        require(case['blocked_reason'] == '', 'ready case has blocked reason')
        require(all(isinstance(caps.get(c), dict) and caps[c].get('available') is True for c in CAPABILITIES),
                'required capability missing; keep affected case blocked')
        require(type(case['initial_stock']) is int and case['initial_stock'] >= 0, 'invalid initial stock')
        requests = case['requests']
        require(isinstance(requests, list) and 1 <= len(requests) <= 8, 'requests must contain 1..8 items')
        for request in requests:
            fields(request, ['quantity', 'key'], 'request')
            require(request['quantity'] is None or type(request['quantity']) in (int, float, str, bool), 'quantity must be scalar')
            require(isinstance(request['key'], str) and re.fullmatch(r'[a-z0-9-]{1,32}', request['key']), 'invalid request key')
        expect = case['expect']
        fields(expect, ['codes', 'remaining_stock', 'reservation_count', 'same_reservation'], 'expect')
        require(isinstance(expect['codes'], list) and len(expect['codes']) == len(requests) and
                all(c in codes for c in expect['codes']), 'invalid expected response codes')
        for field in ('remaining_stock', 'reservation_count'):
            require(type(expect[field]) is int and expect[field] >= 0, 'invalid expected ' + field)
        require(expect['same_reservation'] is None or expect['same_reservation'] is True, 'same_reservation must be null or true')
        if expect['same_reservation'] is True:
            require(len(requests) >= 2 and set(expect['codes']) == {'OK'}, 'same_reservation requires multiple OK responses')
    require(used == known, 'rules without a planned case: ' + ', '.join(sorted(known - used)))
    return plan


def fingerprint(run, stage):
    result = {'inputs': snapshot(run), 'spec': sha(run / 'spec.json')}
    if stage == 'cases':
        result['cases'] = sha(run / 'cases.json')
    return digest(result)


def approve(run, stage, reviewer, mode='human-recorded'):
    spec = spec_check(run)
    require(not spec['open_questions'], 'resolve open questions before approval')
    if stage == 'cases':
        cases_check(run)
        review_check(run, 'spec')
    require(nonempty(reviewer), 'reviewer name missing')
    record = {'stage': stage, 'fingerprint': fingerprint(run, stage), 'reviewer': reviewer,
              'mode': mode, 'time': datetime.now(timezone.utc).isoformat()}
    write(run / ('review-' + stage + '.json'), record)
    return record


def review_check(run, stage):
    record = read(run / ('review-' + stage + '.json'))
    require(record['fingerprint'] == fingerprint(run, stage), stage + ' changed after review')
    return record


def code_for(case):
    lines = ['from harness import ScenarioCase', '', '', 'class Generated' + case['id'] + '(ScenarioCase):',
             '    def test_' + case['id'] + '(self):',
             '        sku = self.api.create_item(stock=' + repr(case['initial_stock']) + ')',
             '        self.addCleanup(self.api.delete_item, sku)',
             '        self.assertEqual(self.api.stock(sku), ' + repr(case['initial_stock']) + ')',
             '        results = []']
    for request in case['requests']:
        lines.append('        results.append(self.api.reserve(sku, ' + repr(request['quantity']) +
                     ', self.request_id(' + repr(request['key']) + ')))')
    for index, code in enumerate(case['expect']['codes']):
        lines.append("        self.assertEqual(results[{}]['code'], {!r})".format(index, code))
        if code == 'OK':
            lines.append("        self.assertIsInstance(results[{}]['reservation_id'], str)".format(index))
            lines.append("        self.assertTrue(results[{}]['reservation_id'])".format(index))
        else:
            lines.append("        self.assertIsNone(results[{}]['reservation_id'])".format(index))
    lines += ['        self.assertEqual(self.api.stock(sku), ' + repr(case['expect']['remaining_stock']) + ')',
              '        self.assertEqual(self.api.reservation_count(sku), ' + repr(case['expect']['reservation_count']) + ')']
    if case['expect']['same_reservation'] is True:
        lines.append("        self.assertEqual(len({r['reservation_id'] for r in results}), 1)")
    code = '\n'.join(lines) + '\n'
    ast.parse(code)
    return code


def implementation():
    return {name: sha(ROOT / name) for name in ['workflow.py', 'harness.py', 'demo_service.py']}


def render(run):
    plan = cases_check(run)
    review_check(run, 'spec'); review_check(run, 'cases')
    ready = [case for case in plan['cases'] if case['status'] == 'ready']
    require(ready, 'no runnable cases; keep blocked cases and supply capabilities')
    directory = run / 'generated' / uuid.uuid4().hex[:12]
    directory.mkdir(parents=True)
    files = {}
    for case in ready:
        path = directory / ('test_' + case['id'] + '.py')
        path.write_text(code_for(case), encoding='utf-8')
        files[path.relative_to(run).as_posix()] = sha(path)
    manifest = {'fingerprint': fingerprint(run, 'cases'), 'implementation': implementation(), 'files': files}
    write(run / 'render.json', manifest)
    return manifest


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'test': test.id(), 'status': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({'test': test.id(), 'status': 'failed', 'detail': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({'test': test.id(), 'status': 'error', 'detail': self._exc_info_to_string(err, test)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({'test': test.id(), 'status': 'skipped', 'reason': reason})


def run_tests(run, fault='none'):
    from demo_service import serve
    import harness
    plan = cases_check(run)
    review_check(run, 'spec'); review_check(run, 'cases')
    manifest = read(run / 'render.json')
    require(manifest['fingerprint'] == fingerprint(run, 'cases'), 'artifacts changed; render again after review')
    require(manifest['implementation'] == implementation(), 'implementation changed; inspect and render again')
    require(manifest['files'], 'empty generated suite')
    directories = set()
    suite = unittest.TestSuite()
    for name, expected in manifest['files'].items():
        require(re.fullmatch(r'generated/[a-f0-9]{12}/test_C[0-9]+\.py', name), 'invalid generated path')
        path = run / name
        require(path.resolve().is_relative_to(run.resolve()) and not path.is_symlink(), 'generated path escaped run')
        require(sha(path) == expected, 'generated code changed; review plan/template and render again')
        directories.add(path.parent)
        module_spec = importlib.util.spec_from_file_location('generated_' + path.stem, path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    actual = {p.relative_to(run).as_posix() for d in directories for p in d.glob('*.py')}
    require(actual == set(manifest['files']), 'unexpected generated Python file')
    expected_count = sum(c['status'] == 'ready' for c in plan['cases'])
    require(suite.countTestCases() == expected_count, 'test discovery count mismatch')
    stream = io.StringIO()
    with serve(fault) as url:
        harness.BASE_URL = url
        try:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
        finally:
            harness.BASE_URL = None
    blocked = [{'id': c['id'], 'reason': c['blocked_reason']} for c in plan['cases'] if c['status'] == 'blocked']
    successful = result.wasSuccessful() and not result.skipped
    complete = result.testsRun == expected_count and len({r['test'] for r in result.records}) == expected_count and not blocked
    status = 'failed' if not successful else ('passed' if complete else 'blocked')
    report = {'status': status, 'complete': complete, 'fault': fault, 'planned': len(plan['cases']),
              'executed': result.testsRun, 'blocked': blocked, 'records': result.records,
              'fingerprint': fingerprint(run, 'cases'), 'implementation': implementation(),
              'render': manifest, 'reviews': [read(run / 'review-spec.json'), read(run / 'review-cases.json')],
              'time': datetime.now(timezone.utc).isoformat(), 'log': stream.getvalue()}
    name = 'report-' + fault + '-' + uuid.uuid4().hex[:8] + '.json'
    write(run / 'reports' / name, report)
    print(json.dumps({'status': status, 'executed': result.testsRun, 'blocked': len(blocked),
                      'report': str(run / 'reports' / name)}, ensure_ascii=False))
    return report


def initialize(run):
    require(not run.exists(), 'run already exists; choose a new directory')
    shutil.copytree(ROOT / 'examples/inputs', run / 'inputs')
    write(run / 'input-manifest.json', inputs(run))


def demo():
    run = ROOT / 'runs' / ('demo-' + uuid.uuid4().hex[:8])
    initialize(run)
    for name in ('spec.json', 'cases.json'):
        shutil.copyfile(ROOT / 'examples/reference' / name, run / name)
    for stage in ('spec', 'cases'):
        approve(run, stage, 'bundled-reference', mode='reference-example-not-human-review')
    render(run)
    baseline = run_tests(run)
    require(baseline['status'] == 'passed', 'reference baseline failed; seeded defects were not evaluated')
    faults = [run_tests(run, fault) for fault in ('reject-writes', 'double-reserve', 'missing-record')]
    require(all(r['status'] == 'failed' and any(x['status'] == 'failed' for x in r['records'])
                and not any(x['status'] == 'error' for x in r['records']) for r in faults),
            'a seeded defect was not detected by a business assertion, or execution had errors')
    print('Demo verified. This replay used bundled reference artifacts, not a live model.')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('demo')
    for command in ('init', 'snapshot', 'check', 'verify-review', 'approve', 'render', 'run'):
        child = sub.add_parser(command)
        child.add_argument('directory', type=Path)
        if command in ('check', 'verify-review', 'approve'):
            child.add_argument('--stage', choices=['spec', 'cases'], required=True)
        if command == 'approve':
            child.add_argument('--reviewer', required=True)
        if command == 'run':
            child.add_argument('--fault', choices=['none', 'reject-writes', 'double-reserve', 'missing-record'], default='none')
    args = parser.parse_args()
    if args.command == 'demo':
        return demo()
    run = args.directory.resolve()
    if args.command == 'init':
        initialize(run)
    elif args.command == 'snapshot':
        write(run / 'input-manifest.json', inputs(run))
    elif args.command == 'check':
        (spec_check if args.stage == 'spec' else cases_check)(run)
    elif args.command == 'verify-review':
        review_check(run, args.stage)
    elif args.command == 'approve':
        approve(run, args.stage, args.reviewer)
    elif args.command == 'render':
        render(run)
    elif args.command == 'run':
        return 0 if run_tests(run, args.fault)['status'] == 'passed' else 1
    print(args.command + ': OK')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('workflow error: ' + str(error), file=sys.stderr)
        sys.exit(2)
