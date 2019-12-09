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
	__slots__ = (
		'_epoch', '_release', '_prerelease', '_post', '_dev', '_local')

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
		self._set_epoch(epoch)
		self._set_release(release)
		self._set_prerelease(prerelease)
		self._set_post(post)
		self._set_dev(dev)
		self._set_local(local)

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

	@property
	def release(self):
		return self._release

	@property
	def prerelease(self):
		return self._prerelease

	@property
	def post(self):
		return self._post

	@property
	def dev(self):
		return self._dev

	@property
	def local(self):
		return self._local

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
		release = tuple(int(x) for x in match['release'].split('.'))
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

	def _set_epoch(self, epoch):
		if epoch < 0:
			raise ValueError('epoch must be a non-negative integer')
		self._epoch = int(epoch)

	def _set_release(self, release):
		release = tuple(release)
		if not release:
			raise ValueError('Release components cannot be empty')
		bad_values = []
		for index, component in enumerate(release):
			if component < 0:
				bad_values.append(f'{component!r} (index {index})')
		if bad_values:
			raise ValueError(
				'Release components must consist of non-negative integers;'
				f' bad values are {", ".join(bad_values)}')
		self._release = tuple(int(x) for x in release)

	def _set_prerelease(self, prerelease):
		if prerelease is None:
			self._prerelease = None
			return
		category, value = prerelease
		category = self.PrereleaseCategory(category)
		if value < 0:
			raise ValueError('Prerelease value must be a non-negative integer')
		self._prerelease = (category, int(value))

	def _set_post(self, post):
		if post is None:
			self._post = None
			return
		if post < 0:
			raise ValueError('post must be a non-negative integer')
		self._post = int(post)

	def _set_dev(self, dev):
		if dev is None:
			self._dev = None
			return
		if dev < 0:
			raise ValueError('dev must be a non-negative integer')
		self._dev = int(dev)

	def _set_local(self, local):
		if local is None:
			self._local = None
			return
		if not self.LOCAL_VERSION_EXPRESSION.fullmatch(local):
			raise ValueError(
				f'{local!r} is not a valid local version specifier')
		self._local = '.'.join(self._SEPARATOR_EXPRESSION.split(local))
