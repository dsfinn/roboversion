"""
Modelling of PEP440-compliant versions and components
"""

import enum
import logging
import re
from collections import namedtuple
from datetime import datetime
from itertools import zip_longest


logger = logging.getLogger(__name__)


# The normalised form of a PEP440 version string:
PEP440_EXPRESSION = re.compile(
	r'(?P<release>(?P<epoch>\d+!)?(?P<components>\d+(\.\d+)*))'
	r'((a(lpha)?(?P<alpha>\d+))|(b(?P<beta>\d+))|(rc(?P<candidate>\d+)))?'
	r'(\.post(?P<post>\d+))?'
	r'(\.dev(?P<dev>\d+))?'
	r'(\+(?P<local>[A-Za-z0-9.]*))?'
)


_VERSION_COMPONENTS = (
	'epoch', 'release', 'prerelease', 'post', 'dev', 'local')

class Version(namedtuple('_Components', _VERSION_COMPONENTS)):
	"""
	A PEP440-compliant version
	"""
	class PrereleaseCategory(enum.IntEnum):
		"""
		Types of prerelease versions
		"""
		ALPHA = 1
		BETA = 2
		RELEASE_CANDIDATE = 3

	RELEASE_EXPRESSION = re.compile(
		r'(?P<components>\d+(\.\d+)*)', flags=re.ASCII)

	PRERELEASE_EXPRESSION = re.compile(
		r'('
			r'(?P<alpha>a(lpha)?)'
			r'|(?P<beta>b(eta)?)'
			r'|(?P<release_candidate>((r?c)|(pre(view)?)))'
		r')([.\-_]?(?P<value>\d+))?',
		flags=re.IGNORECASE,
	)

	LOCAL_VERSION_EXPRESSION = re.compile(
		r'[a-z0-9]+([.\-_][a-z0-9]+)*', flags=re.IGNORECASE)
	_SEPARATOR_EXPRESSION = re.compile(r'[.\-_]')

	EXPRESSION = re.compile(
		r'v?((?P<epoch>\d+)!)?'
		r'(?P<release>' + RELEASE_EXPRESSION.pattern + r')' + r'('
			r'[.\-_]?(?P<prerelease>' + PRERELEASE_EXPRESSION.pattern + r'))?'
			r'((([.\-_]?(post|r(ev)?)(?P<post>\d+)?)|-(?P<implicit_post>\d+)))?'
			r'([.\-_]?dev(?P<dev>\d+))?'
			r'(\+(?P<local>' + LOCAL_VERSION_EXPRESSION.pattern + r'))?',
		flags=re.IGNORECASE,
	)

	_PRERELEASE_PREFIXES = {
		PrereleaseCategory.ALPHA: 'a',
		PrereleaseCategory.BETA: 'b',
		PrereleaseCategory.RELEASE_CANDIDATE: 'rc',
	}

	def __new__(
			cls,
			release,
			*,
			epoch=0,
			prerelease=None,
			post=None,
			dev=None,
			local=None,
	):
		cls._check_nonnegative_integer(epoch)
		release = cls._build_release(release)
		if prerelease is not None:
			prerelease = cls._build_prerelease(prerelease)
		if post is not None:
			cls._check_nonnegative_integer(post)
		if dev is not None:
			cls._check_nonnegative_integer(dev)
		if local is not None:
			local = cls._build_local(local)
		return super().__new__(
			cls, epoch, release, prerelease, post, dev, local)

	def __str__(self):
		strings = []
		if self.epoch:
			strings.append(f'{self.epoch}!')
		strings.append('.'.join(str(x) for x in self.release))
		if self.prerelease:
			category, value = self.prerelease
			strings.append(f'{self._PRERELEASE_PREFIXES[category]}{value}')
		if self.post:
			strings.append(f'.post{self.post}')
		if self.dev:
			strings.append(f'.dev{self.dev}')
		if self.local:
			strings.append(f'+{self.local}')
		return ''.join(strings)

	def get_bumped(self, index=-1, increment=1):
		"""
		Get the Version corresponding to this Version bumped according to the
		specified parameters.

		:param int release_index: The index of the release version to bump
		:param str field: The Version segment to bump
		:param int increment: The amount by which to bump the specified segment
		:returns: Version
		"""
		new_release = [
			x for x, _ in zip_longest(
				self.release[:index], range(index), fillvalue=0)
		]
		new_release.append(self.release[index] + increment)
		new_release.extend(
			0 for _ in range(len(self.release) - len(new_release)))
		return self.__class__(release=new_release)

	@classmethod
	def from_date(cls, date=None, **kwargs):
		"""
		Get the version from the date. If no date is supplied, use the current
		UTC date.

		:param datetime.date date: The date
		:returns: Version
		"""
		if date is None:
			date = datetime.utcnow().date()
		components = date.timetuple()[:3]
		logger.debug('components %r from date %s', components, date)
		return cls(**kwargs, release=components)

	@classmethod
	def from_str(cls, string):
		"""
		Construct a Version from a string

		:param str string: A PEP440-compliant version string
		:returns: Version
		"""
		match = cls.EXPRESSION.fullmatch(string)
		if not match:
			raise ValueError(
				f'{string!r} is not a PEP440-compliant public version string')
		release = (int(x) for x in match['release'].split('.'))
		optionals = {}
		if match['epoch']:
			optionals['epoch'] = int(match['epoch'])
		if match['prerelease']:
			for name in 'alpha', 'beta', 'release_candidate':
				if match[name]:
					category = cls.PrereleaseCategory[name.upper()]
					break
			value_str = match['value']
			value = 0 if value_str is None else int(value_str)
			optionals['prerelease'] = (category, value)
		if match['post']:
			optionals['post'] = int(match['post'])
		elif match['implicit_post']:
			optionals['post'] = int(match['implicit_post'])
		if match['dev']:
			optionals['dev'] = int(match['dev'])
		if match['local']:
			optionals['local'] = match['local']
		return cls(release=release, **optionals)

	@classmethod
	def _check_nonnegative_integer(cls, value):
		if value != int(value):
			raise TypeError(f'{value!r} is not a non-negative integer')
		if value < 0:
			raise ValueError(f'{value!r} is not a non-negative integer')

	@classmethod
	def _build_release(cls, iterable):
		release = tuple(iterable)
		if not release:
			raise ValueError('Release components cannot be empty')
		bad_values = []
		for index, component in enumerate(release):
			try:
				cls._check_nonnegative_integer(component)
			except (TypeError, ValueError):
				bad_values.append(f'{component!r} (index {index})')
		if bad_values:
			raise ValueError(
				'Release components must consist of non-negative integers;'
				f' bad values are {", ".join(bad_values)}')
		return release

	@classmethod
	def _build_prerelease(cls, iterable):
		category, value = iterable
		cls.PrereleaseCategory(category)
		cls._check_nonnegative_integer(value)
		return category, value

	@classmethod
	def _build_local(cls, local):
		if not cls.LOCAL_VERSION_EXPRESSION.fullmatch(local):
			raise ValueError(
				f'{local!r} is not a valid local version specifier')
		return '.'.join(cls._SEPARATOR_EXPRESSION.split(local))
