from datetime import datetime
from contextlib import contextmanager
import copy
import io
import os
import os.path
import shutil
import sys
import tempfile
import threading

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
        steps.version = args.tag

    builder = DockerBuilder(steps, cli.docker_client)
    builder.stdout = cli.out
    builder.archive_only = args.archive_only
    builder.archive_file = args.archive
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

    def write_build_script(self, dir):
        script = BuildScript()

        script.add_commands(self.compiler.commands)
        script.add_archive_patterns(self.compiler.files)

        script_path = os.path.join(dir, 'build.sh')
        with io.open(script_path, 'wb') as fp:
            script.save(fp)

class BuildScript(object):
    """ The entry point for the build container."""

    def __init__(self):
        self.commands = []
        self.archive_patterns = []

    def add_commands(self, commands):
        self.commands += commands

    def add_archive_patterns(self, patterns):
        self.archive_patterns += patterns

    def save(self, fp):
        fp.write(self.setup_script)
        fp.write(self.command_prefix_script)

        for command in self.commands:
            fp.write('%s\n' % command)

        if self.archive_patterns:
            fp.write(self.archive_prefix_script)
            fp.write('tar czf "$BUILD_ARCHIVE_PATH" --posix %s' % (
                ' '.join(
                    '"%s"' % pattern
                    for pattern in self.archive_patterns
                )
            ))

    setup_script = '''\
#!/bin/bash

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
        self.steps.write_build_script(self.build_dir)

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

    def _build_source(self):
        log.info('building source')
        self.archive_name = '%s-%s.tar.gz' % (
            self.steps.name, self.steps.version)
        self.archive_path = os.path.join(self.dist_volume, self.archive_name)

        container = self.client.create_container(
            self.steps.compiler.base_image,
            command='/bin/bash build.sh',
            working_dir=self.src_volume,
            environment={
                'BUILD_ROOT': self.src_volume,
                'BUILD_CONTEXT': os.path.join(self.src_volume, 'context'),
                'BUILD_ARCHIVE_PATH': self.archive_path,
                'BUILD_NAME': self.steps.name,
                'BUILD_VERSION': self.steps.version,
            },
            volumes=[
                self.src_volume,
                self.dist_volume,
            ],
            user='root',
        )
        self.source_container = container.get('Id')
        log.info('created source container=%s', self.source_container)

        with self._attach(self.source_container):
            self.client.start(
                self.source_container,
                binds={
                    self.build_dir: self.src_volume,
                },
            )
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
            'ubuntu:12.04',
            command='cat "%s"' % self.archive_path,
            volumes_from=self.source_container,
            user='root',
        )

        try:
            with io.open(self.archive_file, 'wb') as fp:
                with self._attach(container, stdout=fp.write):
                    self.client.start(container)
                    ret = self.client.wait(container)
        finally:
            self._remove_container(container)

        if ret != 0:
            log.error('failed to write archive to file, status=%s', ret)
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
            volumes_from=self.source_container,
            user='root',
        )
        self.runner_container = container.get('Id')

        with self._attach(self.runner_container):
            self.client.start(self.runner_container)
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

        def watcher():
            try:
                for chunk in client.attach(container, stream=True):
                    stdout(chunk)

                    if should_stop:
                        break
            except:
                log.error('failed to attach to container=%s', container)

        th = threading.Thread(target=watcher)
        th.start()
        try:
            yield
        finally:
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
