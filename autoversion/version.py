import logging
import re
from itertools import zip_longest


logger = logging.getLogger(__name__)


PEP440_EXPRESSION = re.compile(
    r'(?P<release>\d+(\.\d+)*)'
    r'((a(?P<alpha>\d+))|(b(?P<beta>\d+))|(rc(?P<candidate>\d+)))?'
    r'(\.post(?P<post>\d+))?'
    r'(\.dev(?P<dev>\d+))?'
    r'(\+(?P<local>[A-Za-z0-9.]*))?'
)


class ReleaseVersion:
    def __init__(self, components):
        if isinstance(components, str):
            components = components.split('.')
        else:
            try:
                iter(components)
            except TypeError:
                components = (components,)
        if not components:
            raise ValueError('components cannot be empty')
        integers = tuple(int(x) for x in components) 
        bad_values = []
        for index, component in enumerate(integers):
            if component < 0:
                bad_values.append(f'{component!r} (index {index})')
        if bad_values:
            raise ValueError(
                'components must consist of non-negative integers;'
                f' bad values are {", ".join(bad_values)}')
        self._components = integers

    def __str__(self):
        return '.'.join(str(x) for x in self._components)

    def __repr__(self):
        return f'{__class__.__name__}(components={self._components!r})'

    def __getitem__(self, key):
        return self._components[key]

    @property
    def components(self):
        return self._components

    def get_bumped(self, index=None, increment=1):
        if index is None:
            index = len(self._components) - 1
        new_components = [
            x for x, _ in zip_longest(
                self._components[:index + 1], range(index + 1), fillvalue=0)
        ]
        new_components[index] += increment
        new_components.extend(
            0 for _ in range(len(self._components) - len(new_components)))
        return ReleaseVersion(components=new_components)


class Version:
    _COMPONENT_MAP = {
        'release': None,
        'candidate': 'rc',
        'beta': 'b',
        'alpha': 'a',
        'post': '.post',
        'dev': '.dev',
        'local': '+',
    }
    _PRERELEASE_KEYS = ('alpha', 'beta', 'candidate')
    _INTEGER_COMPONENTS = _PRERELEASE_KEYS + ('post', 'dev')

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
        if string:
            if any(x is not None for x in self._components.values()):
                raise ValueError(
                    f'Cannot specify both version string and components')
            match = PEP440_EXPRESSION.fullmatch(string)
            if not match:
                raise ValueError(
                    f'{string!r} is not a PEP440-compliant version string')
            self._components['release'] = match['release']
            for name in self._INTEGER_COMPONENTS:
                if match[name] is not None:
                    value = int(match[name])
                    if value < 0:
                        raise ValueError(
                            f'{name} must be a non-negative integer')
                    self._components[name] = value
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
        for name in self._INTEGER_COMPONENTS:
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
            prefix = self._COMPONENT_MAP[name]
            string = prefix if prefix else ''
            string += str(value)
            strings.append(string)
        return ''.join(strings)

    def __repr__(self):
        arg_strings = [f'{x}={y!r}' for x, y in self._components.items()]
        return f'{__class__.__name__}({", ".join(arg_strings)})'
        
    @property
    def components(self):
        return tuple(self._components.values())

    def get_bumped(self, release_index=None, field='release', increment=1):
        if release_index is not None or field == 'release':
            new_value = self.release.get_bumped(release_index, increment)
        else:
            old_value = self._components[field]
            old_value = 0 if old_value is None else old_value
            new_value = old_value + increment
        components = {}
        for name, value in self._components.items():
            components[name] = value
            if name == field:
                components[name] = new_value
                break
        return Version(**components)
