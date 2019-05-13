import logging
import sys
from argparse import ArgumentParser
from pathlib import Path

from autoversion.git import Reference


logger = logging.getLogger(__name__)


def get_version(
        project_path,
        target_ref,
        alpha_branch,
        beta_branch,
        release_branch,
        post,
        local,
):
    ref = Reference(repository=project_path, name=target_ref)
    return ref.get_version(
        candidate_branch=release_branch,
        beta_branch=beta_branch,
        alpha_branch=alpha_branch,
        post=post,
        local=local,
    )

def main():
    parser = ArgumentParser()
    parser.add_argument(
        '--path', default=Path.cwd(), help='Path to Git projet')
    parser.add_argument(
        '--ref', default='HEAD',
        help='The Git ref of which to report the version',
    )
    parser.add_argument(
        '--alpha_branch', help='The alpha release branch (if any)')
    parser.add_argument(
        '--beta_branch', help='The beta release branch (if any)')
    parser.add_argument(
        '--release_branch',
        help='The release candidate branch (if any)'
    )
    parser.add_argument('--post', help='A post development version')
    parser.add_argument('--local', help='A local version tag')
    parser.add_argument(
        '--log_level', default='DEBUG', help='The logging level')
    arguments = parser.parse_args(sys.argv[1:])
    logger.setLevel(arguments.log_level)
    version = get_version(
        project_path=arguments.path,
        target_ref=arguments.ref,
        alpha_branch=arguments.alpha_branch,
        beta_branch=arguments.beta_branch,
        release_branch=arguments.release_branch,
        post=arguments.post,
        local=arguments.local,
    )
    print(version)
