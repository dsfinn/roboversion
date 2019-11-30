"""
A module for autonomous project versioning based on Git repository state.

Release versions are taken from Git tags, which are expected to be compliant
with the PEP440 versioning scheme.

Prerelease Gitflow branches can be specified for the assignment of prerelease
versions to commits relative to those branches.

Postdevelopment and local version component specification are also supported.
"""
import logging
import sys
from argparse import Action, ArgumentParser, SUPPRESS
from pathlib import Path
from subprocess import CalledProcessError

from roboversion.git import Reference


logger = logging.getLogger(__name__)


def get_version(
		project_path=None,
		target_ref='HEAD',
		alpha_branch=None,
		beta_branch=None,
		release_branch=None,
		post=None,
		local=Reference.AUTO_LOCAL,
):
	"""
	Get the Version corresponding to the specified Git ref at the specified
	repository path. Gitflow prerelease branches, postdevelopment components,
	and local version strings can also be specified.
	
	If a local version string is not specified, development versions will
	be locally versioned to the abbreviated hash of the ref commit by default.
	The local version can be specified as `None` to override this behaviour.

	:param str project_path: The path to the project Git repository
	:param str target_ref: The Git ref string of the target
	:param str alpha_branch: The alpha prerelease branch
	:param str beta_branch: The beta prerelease branch
	:param str release_branch: The release candidate branch
	:param int post: The postdevelopment version
	:param str local: The local version string
	:returns: Version
	"""
	ref = Reference(repository_path=project_path, name=target_ref)
	return ref.get_version(
		candidate_branch=release_branch,
		beta_branch=beta_branch,
		alpha_branch=alpha_branch,
		post=post,
		local=local,
	)

def main(*args):
	"""
	Entrypoint for running the module directly
	"""
	parser = ArgumentParser()
	path_group = parser.add_mutually_exclusive_group()
	path_group.add_argument(
		'repository_path',
		metavar='repository-path',
		nargs='?',
		help='Path to Git repository',
		default=Path.cwd(),
	)
	path_group.add_argument('--path', help=SUPPRESS, type=_deprecated_path)
	parser.add_argument(
		'--ref', default='HEAD',
		help='The Git ref of which to report the version',
	)
	parser.add_argument(
		'--alpha', help='The alpha release branch (if any)')
	parser.add_argument(
		'--beta', help='The beta release branch (if any)')
	parser.add_argument(
		'--release', help='The release candidate branch (if any)')
	parser.add_argument('--post', type=int, help='A post development version')
	parser.add_argument(
		'--local', default=Reference.AUTO_LOCAL, help='A local version tag')
	no_auto_local_group = parser.add_mutually_exclusive_group()
	no_auto_local_group.add_argument(
		'--no-auto-local',
		action='store_true',
		help=(
			'Suppress automatic local version insertion on development'
			' versions. By default, this will be the short hash of the commit.'
		),
	)
	no_auto_local_group.add_argument(
		'--no_auto_local',
		action=_DeprecatedNoLocalUnderscores,
		help=SUPPRESS,
		nargs=0,
	)
	log_level_group = parser.add_mutually_exclusive_group()
	log_level_group.add_argument(
		'--log-level',
		choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
		help='The logging level',
	)
	log_level_group.add_argument(
		'--log_level', help=SUPPRESS, type=_deprecated_log_level_underscores)
	if not args:
		args = sys.argv[1:]
	arguments = parser.parse_args(args)
	logging.basicConfig(level=arguments.log_level)
	local = arguments.local
	if arguments.no_auto_local and local is Reference.AUTO_LOCAL:
		local = None
	repository_path = arguments.repository_path or arguments.path
	try:
		version = get_version(
			project_path=repository_path,
			target_ref=arguments.ref,
			alpha_branch=arguments.alpha,
			beta_branch=arguments.beta,
			release_branch=arguments.release,
			post=arguments.post,
			local=local,
		)
	except CalledProcessError as error:
		logger.error('A call to Git encountered an error')
		logger.debug(error, exc_info=error)
		print(
			(
				'Is the specified path a Git repository?'
				' If so, does it contain any commits?'
			),
			file=sys.stderr,
		)
		return
	print(version)


def _deprecated_path(path):
	logger.warning(
		'The `--path` option is deprecated; use the positional'
		' `repository-path`'
	)
	return path


def _deprecated_log_level_underscores(log_level):
	logger.warning(
		'`--log_level` is deprecated; use `--log-level` instead')
	return log_level


class _DeprecatedNoLocalUnderscores(Action):
	def __call__(self, parser, namespace, values, option_string):
		logger.warning(
			'`--no_auto_local` is deprecated; use `--no-auto-local` instead')
		setattr(namespace, 'no_auto_local', True)
