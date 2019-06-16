import logging
import re
from pathlib import Path
from subprocess import CalledProcessError, check_output

from autoversion.version import PEP440_EXPRESSION, Version


logger = logging.getLogger(__name__)


VERSION_TAG_EXPRESSION = re.compile(
    f'v?(?P<version>{PEP440_EXPRESSION.pattern})')


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

        :return Reference:
        """
        result = self._run_command(
            'git', 'rev-parse', '--abbrev-ref', self.name)
        return Reference(repository_path=self.path, name=result.strip())

    @property
    def hash(self):
        """
        The hash of the commit

        :return int:
        """
        result = self._run_command(
            'git', 'rev-list', '--max-count=1', self.name)
        return int(result.strip(), base=16)

    @property
    def hash_abbreviation(self):
        """
        The abbreviated hash string of the commit

        :return str:
        """
        result = self._run_command(
            'git', 'rev-list', '--abbrev-commit', '--max-count=1', self.name)
        return result.strip()

    def get_commits_in_history(self, since=None):
        """
        Get the number of commits in the history of this ref. If since is
        specified, exclude commits in the history of the specified ref.

        :param str since: The ref of which history should be excluded
        :return int:
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

        :return tuple(int, Version, str):
        """
        arguments = ['git', 'describe', '--tags']
        while True:
            result = self._run_command(*arguments, self.name)
            tag, *description  = result.strip().rsplit('-', 2)
            try:
                version = Version.from_str(tag)
                break
            except ValueError:
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
            post=None,
            local=AUTO_LOCAL,
            release_bump_index=None,
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
        """
        try:
            prerelease_version, base_version, release_tag = (
                self.get_commits_since_tagged_version())
        except CalledProcessError as error:
            if error.returncode == self._NO_TAG_RETURN_CODE:
                prerelease_version = self.get_commits_in_history()
                base_version = Version.from_datetime()
                release_tag = None
            else:
                raise error
        if prerelease_version is None:
            return base_version
        components = {
            'release': base_version.release.get_bumped(release_bump_index)
        }
        prerelease_prefixes = {
            'rc': candidate_branch,
            'b': beta_branch,
            'a': alpha_branch,
        }
        prerelease_prefixes = {
            x: y for x, y in prerelease_prefixes.items() if y is not None}
        branch_name = self.branch.name
        for prefix, prerelease_branch in prerelease_prefixes.items():
            if branch_name == str(prerelease_branch):
                components['prerelease'] = f'{prefix}{prerelease_version}'
                return Version(**components)
        if prerelease_prefixes:
            components['dev'] = self.get_commits_in_history(
                since=prerelease_branch)
            if components['dev'] == 0:
                logger.warning(
                    '%s is a development ref in the history of an upstream'
                    ' prerelease branch; output version will be local only',
                    self,
                )
                return Version(
                    release=base_version.release,
                    local=self.hash_abbreviation,
                )
            prerelease_ref = Reference(
                repository_path=self.path, name=prerelease_branch)
            since_upstream = prerelease_ref.get_commits_in_history(
                since=release_tag)
            components['prerelease'] = f'{prefix}{since_upstream + 1}'
        else:
            components['dev'] = prerelease_version
        if post is not None:
            components.pop('dev')
            components['post'] = post
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

        :return str:
        """
        return check_output(
            arguments, cwd=self.path, text=True, **kwargs)

    @classmethod
    def all_from_repository(cls, path=None):
        """
        Iterate through the refs at the specified repository path

        :param Path path: Git repository path
        :yield tuple(reference, upstream):
        """
        if path is None:
            path = Path.cwd()
        result = check_output(
            (
                'git',
                'for-each-ref',
                '--format=%(refname:short),%(upstream:short)',
            ),
            cwd=path,
            text=True,
        )
        for line in result.splitlines():
            line = line.strip()
            if not line:
                continue
            ref_name, *upstreams = line.split(',')
            upstream_name, = upstreams if upstreams else (None,)
            reference = Reference(repository_path=path, name=ref_name)
            upstream = Reference(repository_path=path, name=upstream_name)
            yield reference, upstream
