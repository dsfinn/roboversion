import logging
from pathlib import Path

from hypothesis import assume, given, example, settings
from hypothesis.strategies import (
    composite, builds, data, deferred, dictionaries, just, lists, none, text)
from pytest import fixture

from autoversion.git import Reference, Repository


logger = logging.getLogger(__name__)


@fixture
def repository(request):
    return Repository()

@fixture
def references(request, repository):
    return list(x for x, _ in repository.refs)

@given(path=text())
def test_repository(path):
    repository = Repository(path=path)
    message = f'Constructed {repository!s}: {repository!r}'
    logger.debug(message)


@settings(deadline=700)
@given(name=text())
def test_reference(repository, name):
    reference = Reference(repository=repository, name=name)
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
            base_count = reference.get_commits_since()
            count = reference.get_commits_since(comparand)
            logger.debug('%s commits in history of %s', base_count, reference)
            logger.debug('%s commits since %s', count, comparand)
            assert base_count >= 1
            assert count >= 0
            assert base_count >= count
