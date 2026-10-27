"""Run the release workflow's real gates against synthetic GitHub responses."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReleaseStageTests(unittest.TestCase):
    def test_formats_require_matching_successful_acceptance_and_exact_assets(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/release-stage.yml').read_text(encoding='utf-8'))
        script = workflow['jobs']['stage']['steps'][0]['run']
        for offline in (False, True):
            for case in ('success', 'failed_ci', 'wrong_head', 'wrong_job', 'changed_asset', 'wrong_digest'):
                with self.subTest(offline=offline, case=case):
                    fixtures, uploads, assets = {}, [], []
                    for backend in ('cpu', 'cuda'):
                        stem = (f'Ghostkiller-Sound-Toolbox-{backend.upper()}-V2.1.0' if offline
                                else f'Ghostkiller_V2_Setup_{backend}_2.1.0')
                        name = stem + ('.zip' if offline else '.exe')
                        data = ('synthetic-' + backend).encode()
                        receipt = {'backend': backend, 'application_version': '2.1.0',
                                   'release_eligible': True, 'purpose': 'release',
                                   'application_source_sha256': 'shared-source',
                                   'format': 'offline-zip' if offline else 'single-exe',
                                   'installer': {'filename': name, 'size': len(data),
                                                 'sha256': hashlib.sha256(data).hexdigest()}}
                        fixtures[name] = data
                        fixtures[stem + '.build.json'] = json.dumps(receipt).encode()
                    for name, data in fixtures.items():
                        assets.append({'name': name, 'size': len(data), 'state': 'uploaded',
                                       'digest': 'sha256:' + hashlib.sha256(data).hexdigest(),
                                       'updated_at': '2026-10-27T01:00:00Z'})

                    def output(args, **kwargs):
                        path = args[-1]
                        if '/commits/' in path:
                            result = {'sha': 'commit'}
                        elif path.endswith('/jobs'):
                            backend = 'cpu' if '/1/' in path else 'cuda'
                            if case == 'wrong_job':
                                backend = 'other'
                            result = {'jobs': [{'name': f'install-upgrade-uninstall ({backend})', 'conclusion': 'success'}]}
                        elif '/actions/runs/' in path:
                            workflow = 'native-validation.yml' if path.endswith('/3') else 'installer-acceptance.yml'
                            result = {'head_sha': 'wrong' if case == 'wrong_head' else 'commit',
                                      'conclusion': 'failure' if case == 'failed_ci' else 'success',
                                      'created_at': '2026-10-27T02:00:00Z', 'path': '.github/workflows/' + workflow}
                        else:
                            candidate = 'candidate' in path
                            result = {'prerelease': candidate, 'draft': False, 'assets': assets if candidate else []}
                        return json.dumps(result)

                    def command(args, **kwargs):
                        if 'download' in args:
                            folder = Path(args[args.index('--dir') + 1])
                            for index, value in enumerate(args):
                                if value == '--pattern':
                                    name = args[index + 1]
                                    (folder / name).write_bytes(fixtures[name])
                        else:
                            uploads.append(args)

                    if case == 'changed_asset':
                        assets[0]['updated_at'] = '2026-10-27T03:00:00Z'
                    if case == 'wrong_digest':
                        assets[0]['digest'] = 'sha256:incorrect'
                    environment = {'GITHUB_REPOSITORY': 'test/repo', 'CPU_RUN': '1', 'CUDA_RUN': '2', 'SOURCE_RUN': '3',
                                   'CANDIDATE_TAG': 'v2.1.0-candidate-20261027' + ('-startup' if offline else ''),
                                   'DISTRIBUTION': 'offline-zip' if offline else 'single-exe'}
                    with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
                        previous = Path.cwd()
                        os.chdir(directory)
                        try:
                            with patch.dict(os.environ, environment), patch.object(subprocess, 'check_output', side_effect=output), \
                                 patch.object(subprocess, 'run', side_effect=command), patch('builtins.print'):
                                if case == 'success':
                                    exec(compile(script, 'release-stage.yml', 'exec'), {})
                                    self.assertEqual(len(uploads), 4)
                                    self.assertTrue(all('.pending-20261027' in call[4] for call in uploads))
                                else:
                                    with self.assertRaises(AssertionError):
                                        exec(compile(script, 'release-stage.yml', 'exec'), {})
                                    self.assertEqual(uploads, [])
                        finally:
                            os.chdir(previous)
