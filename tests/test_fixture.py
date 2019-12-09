import logging
import shutil
from pathlib import Path
from subprocess import run, PIPE
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from roboversion import get_version, main
from roboversion.git import logger as git_logger
from roboversion.git import Reference
from roboversion.version import Version


logger = logging.getLogger(__name__)


REF_ORDER = (
	('release_0', 'beta_0', 'alpha_0'),
	('feature_0',),
	('feature_1',),
	('alpha_1',),
	('beta_1', 'alpha_2'),
	('release_1',),
	('HEAD',)
)


@pytest.fixture(scope='module')
def repository():
	cleanup = False
	try:
		with TemporaryDirectory() as temp:
			path = Path(temp).joinpath('test_repo')
			path.mkdir()
			def git_command(*args):
				return run(
					('git', *args),
					cwd=str(path),
					check=True,
					stdout=PIPE,
					stderr=PIPE,
				)
			git_command('init',)
			test_filename = 'test_file'
			for index, refs in enumerate(REF_ORDER):
				message = f'Test commit {index}'
				with open(path.joinpath(test_filename), 'w') as test_file:
					test_file.write(f'Test commit {index}')
				git_command('add', test_filename)
				git_command('commit', '-m', f'"{message}"')
				for ref in refs:
					if ref == 'HEAD':
						continue
					git_command('branch', ref)
				if index == 0:
					git_command('tag', 'v1337.420.68')
			git_command('tag', 'v1337.420.69')
			git_command('tag', 'random_tag')
			yield path
			cleanup = True
	except PermissionError:
		if not cleanup:
			raise
		logger.debug('Windows is failing to cleanup files again...')

@pytest.fixture(
	scope='module', params=('HEAD', 'feature_0', 'feature_1', 'release_1'))
def ref(request, repository):
	return Reference(repository_path=repository, name=request.param)

@pytest.fixture(params=range(4))
def alpha_branch(request):
	if request.param == 3:
		return None
	return f'alpha_{request.param}'

@pytest.fixture(params=range(3))
def beta_branch(request):
	if request.param == 2:
		return None
	return f'beta_{request.param}'

@pytest.fixture(params=range(3))
def candidate_branch(request):
	if request.param == 2:
		return None
	return f'release_{request.param}'

@pytest.fixture
def known_version(ref, alpha_branch, beta_branch, candidate_branch):
	ref_name = str(ref)
	if ref_name == 'HEAD':
		return Version.from_str('1337.420.69')
	ref_order = (
		('release_0', 'beta_0', 'alpha_0'),
		('feature_0',),
		('feature_1',),
		('alpha_1',),
		('beta_1', 'alpha_2'),
		('release_1',),
		('HEAD',)
	)
	components = {'release': Version.from_str('1337.420.69').release}
	positions = {}
	for index, refs in enumerate(ref_order):
		if ref_name in refs:
			ref_position = index
		if alpha_branch in refs:
			positions[Version.PrereleaseCategory.ALPHA] = index
		if beta_branch in refs:
			positions[Version.PrereleaseCategory.BETA] = index
		if candidate_branch in refs:
			positions[Version.PrereleaseCategory.RELEASE_CANDIDATE] = index
	if positions:
		distances = {x: ref_position - y for x, y in positions.items()}
		category, distance = min(distances.items(), key=lambda x: x[1])
		if distance < 0:
			components['dev'] = ref_position
			components['local'] = ref.hash_abbreviation
			return Version(**components)
		if distance == 0:
			components['prerelease'] = (category, positions[category])
			return Version(**components)
		components['prerelease'] = (category, positions[category] + 1)
		components['dev'] = distance
	else:
		components['dev'] = ref_position
	components['local'] = ref.hash_abbreviation
	return Version(**components)


def test_version(
		ref, alpha_branch, beta_branch, candidate_branch, known_version):
	with mock.patch('roboversion.git.logger.warning', autospec=True) as warn:
		version = get_version(
			project_path=ref.path,
			target_ref=str(ref),
			release_branch=candidate_branch,
			beta_branch=beta_branch,
			alpha_branch=alpha_branch,
		)
		version_string = str(version)
		known_version_string = str(known_version)
		if version_string != known_version_string:
			warn.assert_called_once()
			assert known_version_string.startswith('1337.420.69.dev')
			if candidate_branch == 'release_1':
				assert beta_branch is not None or alpha_branch is not None
			else:
				assert beta_branch == 'beta_1'
				assert alpha_branch in ('alpha_0', 'alpha_1')
		args = ['--ref', str(ref)]
		if candidate_branch:
			args.extend(('--release', candidate_branch))
		if beta_branch:
			args.extend(('--beta', beta_branch))
		if alpha_branch:
			args.extend(('--alpha', alpha_branch))
		args.append(str(ref.path))
		main(*args)