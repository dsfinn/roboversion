"""
Modelling of Git refs for versioning
"""
import logging
import re
from pathlib import Path
from subprocess import CalledProcessError, run, PIPE

from roboversion.version import Version


logger = logging.getLogger(__name__)


class Reference:
	"""
	A Git ref
	"""
	AUTO_LOCAL = object()

	_NO_TAG_RETURN_CODE = 128
	_NULL_DEFAULT = object()

	def __init__(self, repository_path=None, name='HEAD'):
		"""
		:param Path repository_path: Path to project repository
		:param str name: Git ref string
		"""
		if repository_path is None:
			repository_path = Path.cwd()
		self.path = Path(repository_path).absolute()
		self.name = name

	def __repr__(self):
		return (
			f'{self.__class__.__name__}'
			f'(repository_path={self.path!r}, name={self.name!r})'
		)

	def __str__(self):
		return str(self.name)

	@property
	def branch(self):
		"""
		The current branch

		:returns: Reference
		"""
		result = self._run_command(
			'git', 'rev-parse', '--abbrev-ref', self.name)
		return Reference(repository_path=self.path, name=result.strip())

	@property
	def hash(self):
		"""
		The hash of the commit

		:returns: int
		"""
		return int(self.hash_string, base=16)

	@property
	def hash_string(self):
		"""
		The hash string of the commit

		:returns: str
		"""
		result = self._run_command(
			'git', 'rev-list', '--max-count=1', self.name)
		return result.strip()

	@property
	def hash_abbreviation(self):
		"""
		The abbreviated hash string of the commit

		:returns: str
		"""
		result = self._run_command(
			'git', 'rev-list', '--abbrev-commit', '--max-count=1', self.name)
		return result.strip()

	def get_commits_in_history(self, since=None):
		"""
		Get the number of commits in the history of this ref. If since is
		specified, exclude commits in the history of the specified ref.

		:param str since: The ref of which history should be excluded
		:returns: int
		"""
		arguments = ['git', 'rev-list', '--count', self.name]
		if since is not None:
			arguments.append(f'^{since}')
		result = self._run_command(*arguments)
		return int(result.strip())

	def get_commits_since_tagged_version(self):
		"""
		Get the number of commits since the last tagged version, as well as
		the associated Version and tag string.

		:returns: tuple(int, Version, str)
		"""
		arguments = ['git', 'describe', '--tags']
		while True:
			result = self._run_command(*arguments, self.name)
			tag, *description  = result.strip().rsplit('-', 2)
			try:
				version = Version.from_str(tag)
				break
			except ValueError as error:
				logger.debug('Skipping tag %r: %s', tag, error)
				arguments.extend(('--exclude', tag))
		if description:
			distance, _ = description
			distance = int(distance)
		else:
			distance = None
		return distance, version, tag

	def get_version(
			self,
			candidate_branch=None,
			beta_branch=None,
			alpha_branch=None,
			local=AUTO_LOCAL,
			release_bump_index=-1,
	):
		"""
		Calculate the version of this ref based on the specified prerelease
		branches.

		If the ref is tagged with a version, the version will correspond to
		the tagged version.

		If the current branch is a prerelease branch, the version will
		will be a corresponding prerelease version of the next release.
		
		If the ref is neither a tagged version nor at a prerelease branch,
		the version will be a development version of the next upstream
		prerelease branch. If no prerelease branches are specified, the version
		will be a development version of the next release.

		If the ref is in the history of an upstream prerelease branch, the
		version will be a local version of the last release.

		:param str candidate_branch: Release candidate prerelease branch
		:param str beta_branch: Beta prerelease branch
		:param str alpha_branch: Alpha prerelease branch
		:param str local: Local version string
		:param int release_bump_index: The index of the release component to
			bump
		:returns: Version
		"""
		try:
			since_release, base_version, release_tag = (
				self.get_commits_since_tagged_version())
		except CalledProcessError as error:
			if error.returncode == self._NO_TAG_RETURN_CODE:
				since_release = self.get_commits_in_history()
				base_version = Version.from_str('0.0.0')
				release_tag = None
			else:
				raise error
		if since_release is None:
			return base_version
		components = {
			'epoch': base_version.epoch,
			'release': base_version.get_bumped(release_bump_index).release,
		}
		category_branches = {
			Version.PrereleaseCategory.ALPHA: alpha_branch,
			Version.PrereleaseCategory.BETA: beta_branch,
			Version.PrereleaseCategory.RELEASE_CANDIDATE: candidate_branch,
		}
		branch_name = self.branch.name
		logger.debug('branch name: %r', branch_name)
		prerelease_refs = {}
		for category, branch in category_branches.items():
			if branch is None:
				continue
			category_ref = Reference(
				repository_path=self.path, name=str(branch))
			if self.hash == category_ref.hash:
				components['prerelease'] = (category, since_release)
				return Version(**components)
			prerelease_refs[category] = category_ref

		logger.debug('prerelease_refs: %r', prerelease_refs)
		if prerelease_refs:
			distances = {
				x: self.get_commits_in_history(since=y)
				for x, y in prerelease_refs.items()
			}
			category, since_prerelease = min(
				distances.items(), key=lambda x: x[1])
			if since_prerelease == 0:
				components['dev'] = since_release
				components['local'] = self.hash_abbreviation
				version = Version(**components)
				logger.warning(
					'%r is a development ref in the history of an upstream'
					' prerelease branch; output version %s will not capture'
					' historical prerelease information.',
					self,
					version,
				)
				return version
			if since_prerelease > since_release:
				logger.warning(
					'%r is closer to release %s than any prerelease branch'
					' (%s); omitting prerelease version component. Prerelease'
					' branches may be misconfigured.',
					self, base_version,
					', '.join(repr(x) for x in prerelease_refs.values())
				)
				components['dev'] = since_release
			else:
				prerelease_ref = prerelease_refs[category]
				prerelease_version = prerelease_ref.get_commits_in_history(
					since=release_tag)
				components['prerelease'] = (category, prerelease_version + 1)
				components['dev'] = since_prerelease
		else:
			components['dev'] = since_release
		if local is self.AUTO_LOCAL:
			local = self.hash_abbreviation
		components['local'] = local
		logger.debug('Constructing version from %r', components)
		return Version(**components)

	def _run_command(self, *arguments, **kwargs):
		"""
		Run the specified positional arguments as a shell command in a
		subprocess, using keyword arguments as arguments to the check_output
		function

		:returns: str
		"""
		process = run(
			arguments,
			cwd=self.path,
			stderr=PIPE,
			stdout=PIPE,
			universal_newlines=True,
			**kwargs,
		)
		if process.stderr:
			logger.debug(process.stderr)
		process.check_returncode()
		return process.stdout
