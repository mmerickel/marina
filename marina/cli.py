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
        '-b', '--build-dir',
        default=os.getcwd(),
        help=(
            'This folder should be accessible from the docker instance.'
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
        'app',
        help=(
            'Path to an application folder with a meta.yml file'
        ),
    )

def generic_options(parser):
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help=(
            'Increase the verbosity from the default level.'
        ),
    )

def context_factory(cli, args):
    app = MarinaApp(args)
    app.setup_logging()
    return app

class MarinaApp(object):
    stdout = sys.stdout

    def __init__(self, args):
        self.args = args

    def setup_logging(self):
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
            format='%(asctime)s %(levelname)s %(message)s',
        )

    def out(self, msg):
        self.stdout.write(msg + '\n')

    def docker_client(self):
        host = os.environ.get('DOCKER_HOST')
        if host is not None:
            log.debug('found DOCKER_HOST environment variable, using')
        return docker.Client(host)

def main(argv=None):
    cli = CLI(
        version=pkg_resources.get_distribution('marina').version,
        context_factory=context_factory,
    )
    cli.add_generic_options(generic_options)
    cli.load_commands(__name__)
    return cli.run(argv)

if __name__ == '__main__':
    import sys
    sys.exit(main() or 0)
