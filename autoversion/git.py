import logging
import re
from pathlib import Path
from subprocess import CalledProcessError, check_output

from autoversion.version import PEP440_EXPRESSION, Version


VERSION_TAG_EXPRESSION = re.compile(
    f'v?(?P<version>{PEP440_EXPRESSION.pattern})')


logger = logging.getLogger(__name__)


class Reference:
    """
    A Git ref
    """
    AUTO_LOCAL = object()

    _NO_TAG_RETURN_CODE = 128
    _NULL_DEFAULT = object()

    def __init__(self, repository_path=None, name='HEAD'):
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
        result = self._run_command(
            'git', 'rev-parse', '--abbrev-ref', self.name)
        return Reference(repository_path=self.path, name=result.strip())

    @property
    def hash(self):
        result = self._run_command(
            'git', 'rev-list', '--max-count=1', self.name)
        return int(result.strip(), base=16)

    @property
    def hash_abbreviation(self):
        result = self._run_command(
            'git', 'rev-list', '--abbrev-commit', '--max-count=1', self.name)
        return result.strip()

    def get_commits_in_history(self, since=None):
        arguments = ['git', 'rev-list', '--count', self.name]
        if since is not None:
            arguments.append(f'^{since}')
        result = self._run_command(*arguments)
        return int(result.strip())

    def get_commits_since_tagged_version(self):
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
        Total commits in history...
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
        return check_output(
            arguments, cwd=self.path, text=True, **kwargs)

    @classmethod
    def all_from_repository(cls, path=None):
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
