import logging
import os
import sys

import docker
import pkg_resources
from subparse import CLI
from subparse import command

log = __import__('logging').getLogger(__name__)

@command('.build')
def build(parser):
    """
    Build an application into a docker image.

    The build will be.
    """
    parser.add_argument(
        '-i', '--identity-file',
        help=(
            'A SSH private key file which may be used to pull down '
            'repositories when building.'
        ),
    )
    parser.add_argument(
        '-e', '--env',
        action='append',
        default=[],
        help=(
            'Add environ variables to the build. These may be accessed in '
            'the build scripts. Each variable should be of the format '
            'KEY=VALUE. This may be used to pass in credentials required '
            'to access private repositories. May be specified more than once.'
        ),
    )
    parser.add_argument(
        '-b', '--build-dir',
        default=os.getcwd(),
        help=(
            'This folder should be accessible from the docker instance.'
        ),
    )
    parser.add_argument(
        '--archive',
        help=(
            'Archive the build files into a local tarball.'
        ),
    )
    parser.add_argument(
        '--archive-only',
        action='store_true',
        default=False,
        help=(
            'Skip tagging and building the runner image.'
        ),
    )
    parser.add_argument(
        '-t', '--tag',
        help=(
            'Tag to apply to the built image. '
            'This will default to the current date/time.'
        ),
    )
    parser.add_argument(
        '--no-cache',
        dest='use_cache',
        action='store_false',
        default=True,
        help=(
            'Do not mount a cache volume when compiling the app.'
        ),
    )
    parser.add_argument(
        '--cache',
        metavar='CONTAINER:PATH',
        help=(
            'An optional volume or location for the cache. The format is '
            '"<volume_id>:<path>" where the "volume_id" must be the '
            'name or hash of an existing volume. The "path" is an absolute '
            'path to the cache folder/volume within the build container.'
            '\n\n'
            'By default a container will be created by mangling the name of '
            'the app by appending "__buildcache" (e.g. "myapp__buildcache").'
            '\n\n'
            'This option is ignored if --no-cache is specified.'
            '\n\n'
            'The "volume_id" may be an absolute path on the host filesystem.'
            '\n\n'
            'The "path" may be dropped, in which case it will default to '
            '/tmp/cache inside the build container.'
            '\n\n'
            'Examples:'
            '\n\n'
            '  # custom volume with default path\n'
            '  --cache my_cache'
            '\n\n'
            '  # custom path inside of volume\n'
            '  --cache my_cache:/tmp/cache'
            '\n\n'
            '  # host filesystem\n'
            '  --cache /tmp/cache'
        ),
    )
    parser.add_argument(
        '--rebuild-cache',
        action='store_true',
        default=False,
        help=(
            'Delete any cached artifacts prior to building.'
        ),
    )
    parser.add_argument(
        '--skip-cleanup',
        action='store_true',
        default=False,
        help=(
            'Skip removal of images and containers.'
        ),
    )
    parser.add_argument(
        'app',
        help=(
            'Path to an application folder with a meta.yml file'
        ),
    )

def generic_options(parser):
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help=(
            'Increase the verbosity from the default level. May be specified '
            'more than once to increase the verbosity.'
        ),
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        default=False,
        help=(
            'Override any verbosity settings and suppress all output.'
        ),
    )

class AbortCLI(Exception):
    def __init__(self, msg, status):
        Exception.__init__(msg)
        self.status = status

def context_factory(cli, args):
    app = MarinaApp(args)
    app.setup_logging()
    return app

class MarinaApp(object):
    stdout = sys.stdout
    stderr = sys.stderr

    def __init__(self, args):
        self.args = args

    def setup_logging(self):
        if self.args.quiet:
            logging.disable(logging.CRITICAL)
        if self.args.verbose >= 3:
            level = logging.DEBUG
        elif self.args.verbose == 2:
            level = logging.INFO
        elif self.args.verbose == 1:
            level = logging.WARNING
        else:
            level = logging.ERROR
        logging.basicConfig(
            level=level,
            format='%(asctime)s %(levelname)s %(name)s %(message)s',
        )

    def abort(self, msg, status=1):
        self.err(msg)
        raise AbortCLI(msg, status)

    def error(self, msg):
        self.stderr.write(msg)
        if not msg.endswith('\n'):
            self.stderr.write('\n')

    def out(self, msg):
        if not self.args.quiet:
            self.stdout.write(msg)
            self.stdout.flush()

    def docker_client(self):
        client = docker.from_env()
        return client

def main(argv=None):
    cli = CLI(
        version=pkg_resources.get_distribution('marina').version,
        context_factory=context_factory,
    )
    cli.add_generic_options(generic_options)
    cli.load_commands(__name__)
    try:
        return cli.run(argv)
    except AbortCLI as ex:
        return ex.status

if __name__ == '__main__':
    import sys
    sys.exit(main() or 0)
