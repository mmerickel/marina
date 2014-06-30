from datetime import datetime
from contextlib import contextmanager
import copy
import io
import os
import os.path
import posixpath
import shutil
import sys
import tempfile
import threading

import docker.errors
import yaml

log = __import__('logging').getLogger(__name__)

def main(cli, args):
    context_path = os.path.normpath(args.app)

    steps = (
        parse_build_steps_from_file(
            os.path.join(context_path, 'meta.yml')))
    steps.root_path = args.build_dir
    steps.context_path = context_path
    steps.identity_file = args.identity_file
    if args.tag:
        log.info('overriding version tag=%s', args.tag)
        steps.version = args.tag

    builder = DockerBuilder(steps, cli.docker_client)
    builder.stdout = cli.out
    builder.archive_only = args.archive_only
    builder.archive_file = args.archive

    if args.use_cache:
        cache_container = '{0}__buildcache'.format(steps.name)
        cache_hostpath = None
        cache_volume = '/tmp/cache'
        if args.cache:
            parts = args.cache.split(':', 1)
            if len(parts) != 2:
                if posixpath.isabs(parts[0]):
                    cache_hostpath = parts[0]
                else:
                    cache_container = parts[0]
            else:
                cache_container, cache_volume = parts
            if not posixpath.isabs(cache_volume):
                cli.err('The cache "path" must be an absolute path.')
                return 1

        builder.cache_container = cache_container
        builder.cache_hostpath = cache_hostpath
        builder.cache_volume = cache_volume
        builder.rebuild_cache = args.rebuild_cache
    else:
        builder.cache_container = None
        builder.cache_hostpath = None
        builder.cache_volume = None
        builder.rebuild_cache = False
    builder.run()

def parse_build_steps(data):
    settings = yaml.load(data)
    return BuildSteps(settings)

def parse_build_steps_from_file(fname):
    with io.open(fname, 'rb') as fp:
        return parse_build_steps(fp.read())

class BuildSteps(object):
    root_path = None
    # the path to the build directory

    context_path = None
    # the path to the build context folder

    identity_file = None
    # the path to a valid ssh identity file

    class CompileStep(object):
        def __init__(self, settings):
            self.base_image = settings['base_image']
            self.commands = settings.get('commands', [])
            self.files = settings['files']

    class RunStep(object):
        def __init__(self, settings):
            self.base_image = settings['base_image']

    def __init__(self, settings):
        tag = settings.get('tag')
        if tag is None:
            tag = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
        self.version = tag
        self.name = settings['name']
        self.compiler = self.CompileStep(settings['compile'])
        self.runner = self.RunStep(settings['run'])

    def write_context(self, dir):
        if self.context_path:
            log.debug('copied the build context from path=%s',
                      self.context_path)
            shutil.copytree(
                self.context_path,
                os.path.join(dir, 'context'),
            )
        else:
            log.warn('could not find a valid build context')

    def write_identity_file(self, dir):
        ssh_identity_path = os.path.join(dir, 'ssh_identity')
        if self.identity_file:
            log.info('found ssh identity=%s', self.identity_file)
            shutil.copyfile(self.identity_file, ssh_identity_path)
        else:
            log.warn('could not find a valid ssh identity file')

    def write_build_script(self, dir, rebuild_cache=False):
        script = BuildScript()
        script.rebuild_cache = rebuild_cache

        script.add_commands(self.compiler.commands)
        script.add_archive_patterns(self.compiler.files)

        script_path = os.path.join(dir, 'build.sh')
        with io.open(script_path, 'wb') as fp:
            script.save(fp)

class BuildScript(object):
    """ The entry point for the build container."""
    rebuild_cache = False

    def __init__(self):
        self.commands = []
        self.archive_patterns = []

    def add_commands(self, commands):
        self.commands += commands

    def add_archive_patterns(self, patterns):
        self.archive_patterns += patterns

    def save(self, fp):
        fp.write(self.setup_script)

        if self.rebuild_cache:
            fp.write('find "$BUILD_CACHE" -mindepth 1 -delete\n')

        fp.write(self.command_prefix_script)

        for command in self.commands:
            fp.write('%s\n' % command)

        if self.archive_patterns:
            fp.write(self.archive_prefix_script)
            fp.write('tar czf "$BUILD_ARCHIVE_PATH" --posix %s\n' % (
                ' '.join(
                    '"%s"' % pattern
                    for pattern in self.archive_patterns
                )
            ))

    setup_script = '''\
#!/bin/bash

set -eo pipefail

mkdir -p /root/.ssh
chmod 700 /root/.ssh

if [ -f ssh_identity ]; then
    cp ssh_identity /root/.ssh/ssh_identity
    chmod 600 /root/.ssh/ssh_identity
fi

cat > /root/.ssh/config << EOF
    StrictHostKeyChecking no
    IdentityFile /root/.ssh/ssh_identity
EOF

if [ ! -d "$BUILD_CACHE" ]; then
    mkdir -p "$BUILD_CACHE"
fi
'''

    command_prefix_script = '''
# be sure to fail if any of the below commands fail,
# in order to assist in proper debugging
set -e

cd context

# user-defined commands below ####################
'''

    archive_prefix_script = '''
# generate a binary archive
'''

class DockerBuilder(object):
    """ Execute a build on a docker client."""
    build = None

    src_volume = '/builder/src'
    dist_volume = '/builder/dist'

    cache_container = None
    cache_hostpath = None
    cache_volume = None
    rebuild_cache = False

    archive_file = None
    archive_only = False

    @staticmethod
    def stdout(msg):
        sys.stdout.write(msg)

    def __init__(self, steps, connector):
        self.steps = steps
        self.connector = connector
        self.source_container = None
        self.runner_container = None

    def run(self):
        self._setup()
        try:
            if not self._create_cache():
                return
            if not self._build_source():
                return
            if self.archive_file and not self._build_archive():
                return
            if self.archive_only:
                return
            if not self._build_runner():
                return
            if not self._tag_runner():
                return
        finally:
            self._teardown()

        return True

    def _setup(self):
        self.build_dir = tempfile.mkdtemp(dir=self.steps.root_path)
        log.debug('build directory=%s', self.build_dir)

        self.steps.write_context(self.build_dir)
        self.steps.write_identity_file(self.build_dir)
        self.steps.write_build_script(
            self.build_dir,
            rebuild_cache=self.rebuild_cache,
        )

        self.client = self.connector()

    def _teardown(self):
        if self.source_container:
            self._remove_container(self.source_container)

        if self.runner_container:
            self._remove_container(self.runner_container)

        try:
            shutil.rmtree(self.build_dir)
        except IOError:
            log.exception('failed to remove build directory')

        self.client = None

    def _remove_container(self, container):
        try:
            self.client.stop(container)
        except:
            log.exception('failed to stop container=%s', container)
        try:
            self.client.remove_container(container)
        except:
            log.exception('failed to remove container=%s', container)

    def _create_cache(self):
        if not self.cache_container:
            log.info('no cache container defined, skipping checks')
            return True

        do_create_cache = False
        try:
            self.client.inspect_container(self.cache_container)
        except docker.errors.APIError as ex:
            if ex.is_client_error():
                do_create_cache = True
                log.debug('could not find cache container=%s',
                          self.cache_container)
            else:
                raise

        if do_create_cache:
            log.debug('creating cache container')
            self.client.create_container(
                'busybox',
                '/bin/true',
                volumes=[
                    self.cache_volume,
                ],
                name=self.cache_container,
            )
            self.client.start(self.cache_container)
        else:
            log.info('found cache container=%s', self.cache_container)
        return True

    def _build_source(self):
        log.info('building source')
        self.archive_name = '%s-%s.tar.gz' % (
            self.steps.name, self.steps.version)
        self.archive_path = posixpath.join(self.dist_volume, self.archive_name)

        container = self.client.create_container(
            self.steps.compiler.base_image,
            command='/bin/bash build.sh',
            working_dir=self.src_volume,
            environment={
                'BUILD_ROOT': self.src_volume,
                'BUILD_CONTEXT': posixpath.join(self.src_volume, 'context'),
                'BUILD_ARCHIVE_PATH': self.archive_path,
                'BUILD_NAME': self.steps.name,
                'BUILD_VERSION': self.steps.version,
                'BUILD_CACHE': self.cache_volume,
            },
            volumes=[
                self.src_volume,
                self.dist_volume,
            ],
            user='root',
        )
        self.source_container = container.get('Id')
        log.info('created source container=%s', self.source_container)

        volumes_from, binds = [], {}
        if self.cache_container:
            volumes_from.append(self.cache_container)

        binds[self.build_dir] = {
            'bind': self.src_volume,
            'ro': True,
        }
        if self.cache_hostpath:
            binds[self.cache_hostpath] = {
                'bind': self.cache_volume,
                'rw': True,
            }

        with self._attach(self.source_container):
            log.debug('starting container=%s', self.source_container)
            self.client.start(
                self.source_container,
                volumes_from=volumes_from,
                binds=binds,
            )
            log.debug('started container=%s', self.source_container)
            ret = self.client.wait(self.source_container)
        if ret != 0:
            log.error('source did not build successfully, status=%s', ret)
        else:
            log.info('source compiled successfully')
        return ret == 0

    def _build_archive(self):
        log.info('archiving build products')

        # "docker cp" as of 0.9.1 does not support copying from volumes
        # so we need to use the workaround of creating a new container
        # that dumps the contents to stdout
#        raw = self.client.copy(self.source_container, self.archive_path)
#        if not raw:
#            log.error('archive did not finish successfully, status=%s', ret)
#            return False
#
#        with io.open(self.archive_file, 'wb') as fp:
#            for line in raw:
#                fp.write(raw)

        container = self.client.create_container(
            'busybox',
            command='cat "%s"' % self.archive_path,
            user='root',
        )
        self.archive_container = container.get('Id')

        try:
            with io.open(self.archive_file, 'wb') as fp:
                with self._attach(self.archive_container, stdout=fp.write):
                    log.debug('starting container=%s', self.archive_container)
                    self.client.start(
                        self.archive_container,
                        volumes_from=self.source_container,
                    )
                    log.debug('started container=%s', self.archive_container)
                    ret = self.client.wait(self.archive_container)
        finally:
            self._remove_container(self.archive_container)

        if ret != 0:
            log.error('failed to write archive to file, status=%s', ret)
            os.unlink(self.archive_file)
        else:
            log.info('archive written to file=%s', self.archive_file)
        return ret == 0

    def _build_runner(self):
        log.info('building runner')

        base_image = self.steps.runner.base_image
        self.runner_conf = self.client.inspect_image(base_image)['config']

        container = self.client.create_container(
            base_image,
            entrypoint='',
            command='tar xzf "%s" -C /' % self.archive_path,
            user='root',
        )
        self.runner_container = container.get('Id')

        with self._attach(self.runner_container):
            log.debug('starting container=%s', self.runner_container)
            self.client.start(
                self.runner_container,
                volumes_from=self.source_container,
            )
            log.debug('started container=%s', self.runner_container)
            ret = self.client.wait(self.runner_container)
        if ret != 0:
            log.error('runner did not build successfully, status=%s', ret)
        else:
            log.info('runner compiled successfully')
        return ret == 0

    def _tag_runner(self):
        image_name, image_tag = self.steps.name, self.steps.version
        self.runner_image = '%s:%s' % (image_name, image_tag)

        conf = copy.deepcopy(self.runner_conf)
        # XXX add ability to override some configuration from the settings

        self.client.commit(
            self.runner_container,
            repository=image_name,
            tag=image_tag,
            conf=conf,
        )
        self.stdout('created image=%s\n' % self.runner_image)

        return True

    @contextmanager
    def _attach(self, container, stdout=None):
        client = self.connector()
        if stdout is None:
            stdout = self.stdout
        should_stop = False

        signal = threading.Condition()

        def watcher():
            log.debug('attaching to container=%s', container)
            try:
                stream = client.attach(container, stream=True,
                                       stdout=True, stderr=True)
            except:
                log.debug('exception caught while attaching to container=%s',
                          container, exc_info=True)
                log.error('failed to attach to container=%s', container)
                raise
            else:
                log.debug('attached to container=%s', container)

            signal.acquire()
            signal.notify_all()
            signal.release()

            try:
                for chunk in stream:
                    stdout(chunk)

                    if should_stop:
                        break
            except:
                log.debug('exception caught while reading from container=%s',
                          container, exc_info=True)
                log.error('failure while reading from attached container=%s',
                          container)
                raise

        signal.acquire()

        th = threading.Thread(target=watcher)
        th.daemon = True
        th.start()

        # wait until attached before continuing
        signal.wait()
        signal.release()
        # it'd be nice to cleanup if there's an exception but currently
        # the stream has no way to specify a timeout so we just daemonize
        # the thread and let it hang until the process dies
        yield
        should_stop = True
        th.join()

def get_default_ssh_searchpaths():
    for searchpath in (
        os.getcwd(),
        os.path.expanduser('~/.ssh'),
    ):
        yield searchpath

def find_default_identity_file(searchpath=None):
    if searchpath is None:
        for searchpath in get_default_ssh_searchpaths():
            path = find_default_identity_file(searchpath)
            if path:
                return path
    else:
        for fname in ('id_rsa', 'id_dsa'):
            path = os.path.join(searchpath, fname)
            if os.path.exists(path):
                return path
