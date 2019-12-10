import logging
from pathlib import Path
from subprocess import PIPE, STDOUT, run
from unittest import mock

from hypothesis import assume, given, example, settings
from hypothesis.strategies import (
	composite, builds, data, deferred, dictionaries, just, lists, none, text)
from pytest import fixture, raises

from roboversion.git import Reference, CalledProcessError
from roboversion.version import Version


logger = logging.getLogger(__name__)


@fixture(params=range(2))
def repository_path(request):
	if request.param < 1:
		return None
	return Path.cwd()


@fixture
def references(request, repository_path):
	path = repository_path
	if path is None:
		path = Path.cwd()
	process = run(
		(
			'git',
			'for-each-ref',
			'--format=%(refname:short)',
		),
		cwd=path,
		stderr=STDOUT,
		stdout=PIPE,
		universal_newlines=True,
	)
	refs = []
	for line in process.stdout.splitlines():
		ref_name = line.strip()
		if not ref_name:
			continue
		refs.append(Reference(repository_path=path, name=ref_name))
	return refs


@fixture(params=('HEAD',))
def reference(request, repository_path):
	return Reference(repository_path=repository_path, name=request.param)


@fixture(params=('alpha_branch', 'beta_branch', 'candidate_branch', None))
def version_stream(request):
	return request.param


@settings(deadline=700)
@given(name=text())
def test_reference(repository_path, name):
	reference = Reference(repository_path=repository_path, name=name)
	message = f'Constructed {reference!s}: {reference!r}'
	logger.debug(message)


def test_hashes(references):
	for reference in references:
		hex(reference.hash)
		hash_abbreviation = reference.hash_abbreviation
		commit_hash = reference.hash_string
		logger.debug('%s points at %s', reference, commit_hash)
		logger.debug('hash abbreviated to %s', hash_abbreviation)
		assert commit_hash.startswith(hash_abbreviation)
		assert hash_abbreviation < commit_hash


def test_distance(references):
	for reference in references:
		for comparand in references:
			base_count = reference.get_commits_in_history()
			count = reference.get_commits_in_history(since=comparand)
			logger.debug('%s commits in history of %s', base_count, reference)
			logger.debug('%s commits since %s', count, comparand)
			assert base_count >= 1
			assert count >= 0
			assert base_count >= count


def test_version(reference, version_stream):
	kwargs = {version_stream: reference} if version_stream else {}
	version = reference.get_version(**kwargs)
	logger.debug('The version of %s is %s', reference, version)
	if version.prerelease is None:
		count, tag_version, tag = reference.get_commits_since_tagged_version()
		if count is None:
			assert str(tag_version) == str(version)
		else:
			assert count == reference.get_commits_in_history(since=tag)
	elif version_stream  == 'alpha_branch':
		assert version.prerelease[0] == Version.PrereleaseCategory.ALPHA
	elif version_stream == 'beta_branch':
		assert version.prerelease[0] == Version.PrereleaseCategory.BETA
	elif version_stream == 'candidate_branch':
		assert (
			version.prerelease[0]
			== Version.PrereleaseCategory.RELEASE_CANDIDATE
		)
	else:
		assert version.dev is not None


def test_failure(reference):
	def raise_error(*args, **kwargs):
		raise CalledProcessError(128, str((args, kwargs)))
	def raise_bad_error(*args, **kwargs):
		raise CalledProcessError(-1, str((args, kwargs)))
	with mock.patch('roboversion.git.Reference.get_commits_since_tagged_version') as commits:
		commits.side_effect = raise_error
		reference.get_version()
	with mock.patch('roboversion.git.Reference.get_commits_since_tagged_version') as commits:
		commits.side_effect = raise_bad_error
		with raises(CalledProcessError):
			reference.get_version()
	with mock.patch('roboversion.git.Reference._run_command') as run:
		run.side_effect = raise_error
		with raises(CalledProcessError):
			reference.get_version()
