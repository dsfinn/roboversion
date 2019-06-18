from pathlib import Path
from unittest import mock

import pytest

from roboversion.git import logger as git_logger
from roboversion.git import Reference
from roboversion.version import Version

@pytest.fixture
def repository():
	return Path(__file__).parent.joinpath('fixtures', 'test_repo')

@pytest.fixture(params=('HEAD', 'feature_0', 'feature_1', 'release_1'))
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
			positions['a'] = index
		if beta_branch in refs:
			positions['b'] = index
		if candidate_branch in refs:
			positions['rc'] = index
	if positions:
		distances = {x: ref_position - y for x, y in positions.items()}
		prefix, distance = min(distances.items(), key=lambda x: x[1])
		if distance < 0:
			components['dev'] = ref_position
			components['local'] = ref.hash_abbreviation
			return Version(**components)
		if distance == 0:
			components['prerelease'] = f'{prefix}{positions[prefix]}'
			return Version(**components)
		components['prerelease'] = f'{prefix}{positions[prefix] + 1}'
		components['dev'] = distance
	else:
		components['dev'] = ref_position
	components['local'] = ref.hash_abbreviation
	return Version(**components)


def test_version(
		ref, alpha_branch, beta_branch, candidate_branch, known_version):
	with mock.patch('roboversion.git.logger.warning', autospec=True) as warn:
		version = ref.get_version(
			candidate_branch=candidate_branch,
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