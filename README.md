# roboversion

Automated project versioning based on Git repository state.

## Author

David Finn: dsfinn@gmail.com

## Requirements

* Python 3.6+
* Git

## Installation

```sh
pip install roboversion
```

## Description

Running this module, or its `get_version` function, will inspect the specified
Git repository state and construct a corresponding PEP440-compliant version.

Base releases are expected to be tagged as PEP440-compliant version strings.
If no version tags exist, the default release will be generated from the date.

If prerelease branches are specified (e.g. alpha, beta, release candidate)
the output version will reflect this information based on the closest ancestor
prerelease branch.

## Use

This module can be used as an imported module or directly from the command
line.

If no ref is specified as the target, 'HEAD' will be the target ref.

If the ref is tagged with a version, the version will correspond to
the tagged version.

If the current branch is a prerelease branch, the version will
will be a corresponding prerelease version of the next release.

If the ref is neither a tagged version nor at a prerelease branch,
the version will be a development version of the next upstream
prerelease branch. If no prerelease branches are specified, the version
will be a development version of the next release.

If the ref is in the history of an upstream prerelease branch, the
version will be a local version of the last release. This is unlikely to be
useful, and probably the result of a misconfiguration.

Detailed descriptions of parameters can be found in the method documentation
and by running the module with `--help`.

## Examples

```python
from roboversion import get_version
...
version = get_version()
```

```python
from roboversion import get_version
...
version = get_version(alpha_branch='develop')
```

```bash
$ python -m roboversion --alpha develop --beta beta --release candidate --no_auto_local --ref HEAD
```
