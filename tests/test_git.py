import logging
from pathlib import Path

from hypothesis import assume, given, example, settings
from hypothesis.strategies import (
    composite, builds, data, deferred, dictionaries, just, lists, none, text)
from pytest import fixture

from autoversion.git import Reference


logger = logging.getLogger(__name__)


@fixture
def repository_path(request):
    return Path.cwd()


@fixture
def references(request, repository_path):
    return list(
        x for x, _ in Reference.all_from_repository(path=repository_path))


@fixture(params=('master',))
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
        hash_abbreviation = reference.hash_abbreviation
        commit_hash = hex(reference.hash).lstrip('0x')
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
    if version_stream  == 'alpha_branch':
        assert str(version.prerelease.category) == 'Category.ALPHA'
    elif version_stream == 'beta_branch':
        assert str(version.prerelease.category) == 'Category.BETA'
    elif version_stream == 'candidate_branch':
        assert (
            str(version.prerelease.category)
            == 'Category.RELEASE_CANDIDATE'
        )
    else:
        assert version.dev is not None
