import logging

from hypothesis import given, strategies

from autoversion.version import ReleaseVersion


logger = logging.getLogger(__name__)


@strategies.composite
def release_component_tuples(draw):
    length = draw(strategies.integers(min_value=1, max_value=20))
    return draw(
        strategies.tuples(
            *tuple(strategies.integers(min_value=0) for _ in range(length)))
    )

@strategies.composite
def release_component_strings(draw):
    components = draw(release_component_tuples())
    return '.'.join(str(x) for x in components)

@strategies.composite
def release_components(draw):
    return draw(
        strategies.one_of(
            release_component_tuples(),
            release_component_strings(),
            strategies.integers(min_value=0),
        )
    )


@given(release_components=release_components())
def test_release_version(release_components):
    release_version = ReleaseVersion(components=release_components)
    message = (
        f'constructed {release_version}: {release_version!r}'
        f' from components {release_components!r}'
    )
    logger.debug(message)