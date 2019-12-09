import logging
import re

import pytest
from hypothesis import assume, given, strategies

from roboversion.version import PEP440_EXPRESSION, Version


logger = logging.getLogger(__name__)


@strategies.composite
def release_strings(draw):
	string = draw(
		strategies.from_regex(
			re.compile(
				f'^{Version.RELEASE_EXPRESSION.pattern}$', flags=re.ASCII),
		),
	)
	return string.strip()

@strategies.composite
def prerelease_strings(draw):
	string = draw(
		strategies.from_regex(
			re.compile(
				f'^{Version.PRERELEASE_EXPRESSION.pattern}$',
				flags=(re.ASCII|re.IGNORECASE),
			)
		)
	)
	return string.strip()

@strategies.composite
def local_version_strings(draw):
	string = draw(
		strategies.from_regex(
			re.compile(
				f'^{Version.LOCAL_VERSION_EXPRESSION.pattern}$', flags=re.ASCII),
		)
	)
	return string.strip()

@strategies.composite
def post_development_strings(draw):
	string = draw(
		strategies.from_regex(
			re.compile(
				(
					r'^((([.\-_]?(post|r(ev)?)(?P<post>\d+)?)'
					r'|-(?P<implicit_post>\d+)))?$'
				),
				flags=(re.ASCII|re.IGNORECASE),
			)
		)
	)
	return string.strip()

@strategies.composite
def version_strings(draw):
	release_str = draw(release_strings())
	epoch = draw(strategies.just(None) | strategies.integers(min_value=0))
	prerelease_str = draw(strategies.just(None) | prerelease_strings())
	post_str = draw(strategies.just(None) | post_development_strings())
	dev = draw(strategies.just(None) | strategies.integers(min_value=0))
	local= draw(strategies.just(None) | local_version_strings())
	if epoch is not None:
		version_str = f'{epoch}!{release_str}'
	else:
		version_str = release_str
	if prerelease_str is not None:
		version_str += prerelease_str
	if post_str is not None:
		version_str += post_str
	if dev is not None:
		version_str += f'.dev{dev}'
	if local is not None:
		version_str += f'+{local}'
	return version_str

@given(
	components=strategies.iterables(
		elements=strategies.integers(min_value=0), min_size=1)
)
def test_release(components):
	version = Version(release=components)
	bumped_version = version.get_bumped()
	reverted_version = bumped_version.get_bumped(increment=-1)
	assert str(version) == str(reverted_version)


@given(
	components=strategies.lists(
		elements=strategies.integers()).filter(lambda x: not x or min(x) < 0)
)
def test_bad_release(components):
	with pytest.raises(ValueError):
		Version(release=components)


@given(release_str=release_strings())
def test_release_str(release_str):
	Version.from_str(string=release_str)


@given(date=strategies.just(None)|strategies.dates())
def test_release_date(date):
	Version.from_date(date)

@given(
	prerelease_str=strategies.text().filter(
		lambda x: Version.PRERELEASE_EXPRESSION.fullmatch(x.strip()) is None),
)
def test_bad_prerelease_str(prerelease_str):
	try:
		version = Version.from_str(f'0{prerelease_str}')
	except (ValueError, TypeError):
		return
	assert version.prerelease is None


@given(
	local_str=strategies.text().filter(
		lambda x: Version.LOCAL_VERSION_EXPRESSION.fullmatch(x) is None,
	),
)
def test_bad_local_str(local_str):
	with pytest.raises(ValueError):
		Version.from_str(f'0+{local_str}')


@given(date=strategies.just(None)|strategies.dates())
def test_version_date(date):
	Version.from_date(date)


@given(version_str=version_strings())
def test_version_str(version_str):
	version = Version.from_str(string=version_str)
	repr(version)
	logger.debug('testing version %s: %r', version, version)
	version.get_bumped(index=0)
	roundtripped = Version.from_str(str(version))
	assert str(roundtripped) == str(version)
	good_parameters = {}
	segment_names = ('release', 'epoch', 'prerelease', 'post', 'dev', 'local')
	for segment in segment_names:
		good_parameters[segment] = getattr(version, segment)
	for segment in segment_names:
		with pytest.raises(TypeError):
			bad_version = Version(**{**good_parameters, segment: object()})
	for segment in ('epoch', 'post', 'dev'):
		with pytest.raises(ValueError):
			bad_version = Version(**{**good_parameters, segment: -1})
	assert PEP440_EXPRESSION.match(str(version))


@given(
	version_str=strategies.text().filter(
		lambda x: Version.EXPRESSION.fullmatch(x.strip()) is None)
)
def test_bad_version_str(version_str):
	logger.debug('expecting to fail with %r', version_str)
	with pytest.raises(ValueError):
		Version.from_str(string=version_str)
