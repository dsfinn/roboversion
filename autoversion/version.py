import logging
import re
from itertools import zip_longest


logger = logging.getLogger(__name__)

pep440_pattern = (
    r'^'
    r'(?P<release>\d+(\.\d+)*)'
    r'((a(?P<alpha>\d+))|(b(?P<beta>\d+))|(rc(?P<candidate>\d+)))?'
    r'(\.post(?P<post>\d+))?'
    r'(\.dev(?P<dev>\d+))?'
    r'(\+(?P<local>[A-Za-z0-9.]*))?'
    r'$'
)


version_pattern = re.compile(pep440_pattern)


class ReleaseVersion:
    def __init__(self, components):
        if isinstance(components, str):
            components = components.split('.')
        if isinstance(components, int):
            components = (components,)
        self.components = tuple(int(x) for x in components)
        if not self.components:
            raise ValueError('components cannot be empty')

    def __str__(self):
        return '.'.join(str(x) for x in self.components)

    def __repr__(self):
        return f'{__class__.__name__}(components={self.components!r})'

    def __getitem__(self, key):
        return self.components[key]


class Version:
    _COMPONENTS = {
        'release': None,
        'alpha': 'a',
        'beta': 'b',
        'candidate': 'rc',
        'post': 'post',
        'dev': 'dev',
        'local': None,
    }
    _PRERELEASE_KEYS = ('alpha', 'beta', 'candidate')

    def __init__(
            self,
            string=None,
            *,
            release=None,
            alpha=None,
            beta=None,
            candidate=None,
            post=None,
            dev=None,
            local=None,
    ):
        self._components = {}
        for name in self._COMPONENT_MAP:
            self._components[name] = locals()[name]
        _, *integer_components, _ = self._COMPONENT_MAP
        if string:
            if any(x is not None for x in self._components.values()):
                raise ValueError(
                    f'Cannot specify both version string and components')
            match = version_pattern.fullmatch(string)
            if not match:
                raise ValueError(
                    f'{string!r} is not a PEP440-compliant version string')
            self._components['release'] = match['release']
            for name in integer_components:
                if match[name] is not None:
                    self._components[name] = int(match[name])
            self._components['local'] = match['local']
        try:
            self._components['release'] = ReleaseVersion(
                self._components['release'])
        except (ValueError, TypeError) as error:
            message = f'Invalid release value: {self._components["release"]!r}'
            raise ValueError(message) from error
        prerelease = {
            x: self._components[x]
            for x in self._PRERELEASE_KEYS
            if self._components[x] is not None
        }
        if prerelease:
            try:
                _, = prerelease
            except ValueError as error:
                message = (
                    f'Can only specify one of {self._PRERELEASE_KEYS};'
                    f' {", ".join(prerelease)} were specified'
                )
                raise ValueError(message) from error
        for name in integer_components:
            if self._components[name] is None:
                continue
            if self._components[name] < 0:
                raise ValueError(
                    f'{name} must be a non-negative integer'
                    f' (not {self._components[name]})'
                )
        
    def __getattr__(self, key):
        return self._components[key]

    def __str__(self):
        strings = []
        for name, value in self._components.items():
            if value is None:
                continue
            if name == 'local':
                continue
            prefix = self._COMPONENT_MAP[name]
            string = prefix if prefix else ''
            string += str(value)
            strings.append(string)
        string = '.'.join(strings)
        local = self.local
        string = string + f'+{local}' if local else string
        return string

    def __repr__(self):
        arg_strings = [f'{x}={y!r}' for x, y in self._components.items()]
        return f'{__class__.__name__}({", ".join(arg_strings)})'
        
    @property
    def components(self):
        return tuple(self._components.values())

        
