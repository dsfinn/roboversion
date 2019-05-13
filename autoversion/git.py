import logging
import re
from pathlib import Path
from subprocess import CalledProcessError, check_output

from autoversion.version import PEP440_EXPRESSION, Version


VERSION_TAG_EXPRESSION = re.compile(
    f'v?(?P<version>{PEP440_EXPRESSION.pattern})')


logger = logging.getLogger(__name__)


class Repository:
    def __init__(self, path=None):
        if path is None:
            path = Path.cwd()
        self.path = Path(path).absolute()

    def __repr__(self):
        return f'{self.__class__.__name__}(path={self.path!r})'

    def __str__(self):
        return self.path.name

    @property
    def head(self):
        return Reference(repository=self, name='HEAD')

    @property
    def refs(self):
        result = self.run_command(
            'git',
            'for-each-ref',
            '--format=%(refname:short),%(upstream:short)',
        )
        for line in result.splitlines():
            line = line.strip()
            if not line:
                continue
            ref_name, *upstreams = line.split(',')
            upstream_name, = upstreams if upstreams else (None,)
            reference = Reference(repository=self, name=ref_name)
            upstream = Reference(repository=self, name=upstream_name)
            yield reference, upstream

    def run_command(self, *arguments, **kwargs):
        kwargs = {'cwd': self.path, 'text': True, **kwargs}
        return check_output(arguments, **kwargs)


class Reference:
    _NO_TAG_RETURN_CODE = 128
    _NULL_DEFAULT = object()

    def __init__(self, repository=None, name='HEAD'):
        if repository is None:
            repository = Repository(path=Path.cwd())
        elif isinstance(repository, (str, Path)):
            repository = Repository(path=repository)
        self.repository = repository
        self.name = name

    def __repr__(self):
        return (
            f'{self.__class__.__name__}'
            f'(repository={self.repository!r}, name={self.name!r})'
        )

    def __str__(self):
        return str(self.name)

    @property
    def branch(self):
        result = self._run_command(
            'git', 'rev-parse', '--abbrev-ref', self.name)
        return Reference(repository=self.repository, name=result.strip())

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

    @property
    def upstream(self):
        for ref, upstream in self.repository.refs:
            if self.name == ref.name:
                return upstream
        return None

    def get_commits_since(self, comparand=None):
        arguments = ['git', 'rev-list', '--count', self.name]
        if comparand is not None:
            arguments.append(f'^{comparand}')
        result = self._run_command(*arguments)
        return int(result.strip())

    def get_commits_since_tagged_version(
            self, tag_expression=VERSION_TAG_EXPRESSION):
        arguments = ['git', 'describe', '--tags']
        while True:
            result = self._run_command(*arguments, self.name)
            tag, *description  = result.strip().rsplit('-', 2)
            match = tag_expression.fullmatch(tag)
            if match:
                version = Version(string=match['version'])
                break
            arguments.extend(('--exclude', tag))
        if description:
            distance, _ = description
            distance = int(distance)
        else:
            distance = None
        return distance, version

    def get_version(
            self,
            candidate_branch=None,
            beta_branch=None,
            alpha_branch=None,
            post=None,
            local=_NULL_DEFAULT,
            release_bump_index=1,
    ):
        try:
            prerelease_version, base_version = (
                self.get_commits_since_tagged_version())
        except CalledProcessError as error:
            if error.returncode == self._NO_TAG_RETURN_CODE:
                prerelease_version = self.get_commits_since()
                base_version = Version(release=0)
            else:
                raise error
        if prerelease_version is None:
            return base_version
        components = {
            'release': base_version.release.get_bumped(release_bump_index)
        }
        branch = self.branch
        prereleases = {
            'candidate': candidate_branch,
            'beta': beta_branch,
            'alpha': alpha_branch,
        }
        for component, prerelease_branch in prereleases.items():
            if prerelease_branch is None:
                continue
            if branch.name == prerelease_branch:
                components[component] = prerelease_version
                return Version(**components)
        if alpha_branch is not None:
            components['alpha'] = prerelease_version + 1
            components['dev'] = self.get_commits_since(alpha_branch)
        else:
            components['dev'] = prerelease_version
        if local is self._NULL_DEFAULT:
            local = self.hash_abbreviation
        components['local'] = local
        return Version(**components)

    def _run_command(self, *arguments, **kwargs):
        return self.repository.run_command(*arguments, **kwargs)
