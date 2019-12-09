"""
Modelling of PEP440-compliant versions and components
"""

import enum
import logging
import re
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


class Version:
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

	def __init__(
			self,
			release,
			*,
			epoch=0,
			prerelease=None,
			post=None,
			dev=None,
			local=None,
	):
		"""
		:param Release release: The release version
		:param int epoch: The epoch
		:param Prerelease prerelease: The prerelease version
		:param int post: The postrelease version
		:param int dev: The development version
		:param str local: The local version string
		"""
		self.epoch = epoch
		self.release = release
		self.prerelease = prerelease
		self.post = post
		self.dev = dev
		self.local = local

	def __repr__(self):
		return (
			f'{self.__class__.__name__}'
			f'(release={self.release!r},'
			f' epoch={self.epoch!r},'
			f' prerelease={self.prerelease!r},'
			f' post={self.post!r},'
			f' dev={self.dev!r},'
			f' local={self.local!r}'
			f')'
		)

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

	@property
	def epoch(self):
		return self._epoch

	@epoch.setter
	def epoch(self, value):
		if value is None:
			self._epoch = None
			return
		if value < 0:
			raise ValueError('epoch must be a non-negative integer')
		self._epoch = int(value)

	@property
	def release(self):
		return self._release

	@release.setter
	def release(self, value):
		if not value:
			raise ValueError('Release components cannot be empty')
		components = tuple(int(x) for x in value)
		bad_values = []
		for index, component in enumerate(components):
			if component < 0:
				bad_values.append(f'{component!r} (index {index})')
		if bad_values:
			raise ValueError(
				'Release components must consist of non-negative integers;'
				f' bad values are {", ".join(bad_values)}')
		self._release = components

	@property
	def prerelease(self):
		return self._prerelease

	@prerelease.setter
	def prerelease(self, value):
		if value is None:
			self._prerelease = None
			return
		category, value = value
		category = self.PrereleaseCategory(category)
		if value < 0:
			raise ValueError('Prerelease value must be a non-negative integer')
		self._prerelease = (category, int(value))

	@property
	def post(self):
		return self._post

	@post.setter
	def post(self, value):
		if value is None:
			self._post = None
			return
		if value < 0:
			raise ValueError('post must be a non-negative integer')
		self._post = int(value)

	@property
	def dev(self):
		return self._dev

	@dev.setter
	def dev(self, value):
		if value is None:
			self._dev = None
			return
		if value < 0:
			raise ValueError('dev must be a non-negative integer')
		self._dev = int(value)

	@property
	def local(self):
		return self._local

	@local.setter
	def local(self, value):
		if value is None:
			self._local = None
			return
		if not self.LOCAL_VERSION_EXPRESSION.fullmatch(value):
			raise ValueError(
				f'{value!r} is not a valid local version specifier')
		self._local = '.'.join(self._SEPARATOR_EXPRESSION.split(value))

	def get_bumped(self, index=None, increment=1):
		"""
		Get the Version corresponding to this Version bumped according to the
		specified parameters.

		:param int release_index: The index of the release version to bump
		:param str field: The Version segment to bump
		:param int increment: The amount by which to bump the specified segment
		:returns: Version
		"""
		if index is None:
			index = len(self.release) - 1
		new_release = [
			x for x, _ in zip_longest(
				self.release[:index+1], range(index + 1), fillvalue=0)
		]
		new_release[-1] += increment
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
	def from_datetime(cls, time=None, **kwargs):
		"""
		Deprecated; use from_date
		"""
		logger.warning(
			'%s.%s is deprecated; use %s.%s instead',
			cls.__name__,
			cls.from_datetime.__name__,
			cls.__name__,
			cls.from_date.__name__,
		)
		date = None if time is None else time.date()
		return cls.from_date(date)

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
		release = match['release'].split('.')
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
