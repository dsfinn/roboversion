import logging
import subprocess
from hashlib import sha1
from pathlib import Path


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
        result = self.run_command('git', 'for-each-ref')
        for line in result.splitlines():
            line = line.strip()
            if not line:
                continue
            _, _, ref_name = line.split()
            yield Reference(repository=self, name=ref_name)

    def run_command(self, *arguments, **kwargs):
        kwargs = {'cwd': self.path, 'text': True, **kwargs}
        return subprocess.check_output(arguments, **kwargs)


class Reference:
    def __init__(self, repository=None, name='HEAD'):
        if repository is None:
            repository = Repository(path=Path.cwd())
        self.repository = repository
        self.name = name

    def __repr__(self):
        return (
            f'{self.__class__.__name__}'
            f'(repository={self.repository!r}, name={self.name!r})'
        )

    def __str__(self):
        return f'{self.repository}:{self.name}'

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

    def commits_since(self, comparand=None):
        arguments = ['git', 'rev-list', '--count', self.name]
        if comparand is not None:
            arguments.append(f'^{comparand.name}')
        result = self._run_command(*arguments)
        return int(result.strip())

    def _run_command(self, *arguments, **kwargs):
        return self.repository.run_command(*arguments, **kwargs)
