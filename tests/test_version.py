import logging
import re

import pytest
from hypothesis import assume, given, strategies

from roboversion.version import Release, Version, Prerelease, LocalVersion


logger = logging.getLogger(__name__)


@strategies.composite
def release_strings(draw):
	return draw(
		strategies.from_regex(
			re.compile(f'^{Release.EXPRESSION.pattern}$', flags=re.ASCII)),
	)

@strategies.composite
def prerelease_strings(draw):
	return draw(
		strategies.from_regex(
			re.compile(
				f'^{Prerelease.EXPRESSION.pattern}$',
				flags=(re.ASCII|re.IGNORECASE),
			)
		)
	)

@strategies.composite
def local_version_strings(draw):
	return draw(
		strategies.from_regex(
			re.compile(
				f'^{LocalVersion.EXPRESSION.pattern}$', flags=re.ASCII),
		)
	)

@strategies.composite
def post_development_strings(draw):
	return draw(
		strategies.from_regex(
			re.compile(
				(
					r'^((([.-_]?(post|r(ev)?)(?P<post>\d+)?)'
					r'|-(?P<implicit_post>\d+)))?$'
				),
				flags=(re.ASCII|re.IGNORECASE),
			)
		)
	)


@given(
	components=strategies.iterables(
		elements=strategies.integers(min_value=0), min_size=1)
)
def test_release(components):
	release = Release(components=components)
	bumped_release = release.get_bumped()
	reverted_release = bumped_release.get_bumped(increment=-1)
	assert str(release) == str(reverted_release)


@given(
	components=strategies.lists(
		elements=strategies.integers()).filter(lambda x: not x or min(x) < 0)
)
def test_bad_release(components):
	with pytest.raises(ValueError):
		Release(components=components)


@given(release_str=release_strings())
def test_release_str(release_str):
	Release.from_str(string=release_str)

@given(
	release_str=strategies.text().filter(
		lambda x: Release.EXPRESSION.fullmatch(x.strip()) is None)
)
def test_bad_release_str(release_str):
	with pytest.raises((ValueError, TypeError)):
		Release.from_str(string=release_str)


@given(datetime=strategies.just(None)|strategies.datetimes())
def test_release_datetime(datetime):
	Release.from_datetime(datetime)


@given(date=strategies.just(None)|strategies.dates())
def test_release_date(date):
	Release.from_date(date)

@given(
	prerelease_str=strategies.text().filter(
		lambda x: Prerelease.EXPRESSION.fullmatch(x.strip()) is None),
)
def test_bad_prerelease_str(prerelease_str):
	with pytest.raises(ValueError):
		Prerelease.from_str(prerelease_str)


@given(
	local_str=strategies.text().filter(
		lambda x: LocalVersion.EXPRESSION.fullmatch(x.strip()) is None),
)
def test_bad_local_str(local_str):
	with pytest.raises(ValueError):
		LocalVersion.from_str(local_str)


@given(datetime=strategies.just(None)|strategies.datetimes())
def test_version_datetime(datetime):
	Version.from_datetime(datetime)


@given(date=strategies.just(None)|strategies.dates())
def test_version_date(date):
	Version.from_date(date)


@given(
	release_str=release_strings(),
	epoch=(strategies.just(None) | strategies.integers(min_value=0)),
	prerelease_str=(strategies.just(None) | prerelease_strings()),
	post_str=(strategies.just(None)|post_development_strings()),
	dev=(strategies.just(None)|strategies.integers(min_value=0)),
	local=(strategies.just(None) | local_version_strings()),
)
def test_version_str(release_str, epoch, prerelease_str, post_str, dev, local):
	version_str = release_str.strip()
	if epoch is not None:
		version_str = f'{epoch}!{version_str}'
	if prerelease_str is not None:
		version_str += prerelease_str.strip()
	if post_str is not None:
		version_str += post_str.strip()
	if dev is not None:
		version_str += f'.dev{dev}'
	if local is not None:
		version_str += f'+{local.strip()}'
	version = Version.from_str(string=version_str)
	repr(version)
	logger.debug('testing version %s: %r', version, version)
	if version.prerelease is None:
		with pytest.raises(AttributeError):
			version.get_bumped(field='prerelease')
	else:
		version.get_bumped(field='prerelease')
	for segment in ('release', 'post', 'dev'):
		version.get_bumped(field=segment, increment=69)
	with pytest.raises(ValueError):
		version.get_bumped(field='local')
	with pytest.raises(ValueError):
		version.get_bumped(field='NOT_A_SEGMENT')
	with pytest.raises(TypeError):
		version.get_bumped(field='dev', release_index=0)
	version.get_bumped(release_index=0)
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




@given(
	version_str=strategies.text().filter(
		lambda x: Version.EXPRESSION.fullmatch(x.strip()) is None)
)
def test_bad_version_str(version_str):
	logger.debug('expecting to fail with %r', version_str)
	with pytest.raises((ValueError, TypeError)):
		Version.from_str(string=version_str)