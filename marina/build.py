from datetime import datetime
import collections
from contextlib import contextmanager
import io
import json
import os
import os.path
import posixpath
import re
import shutil
import sys
import tempfile
import threading

import docker.errors
import yaml

from .compat import reraise

log = __import__('logging').getLogger(__name__)

def main(cli, args):
    context_path = os.path.normpath(args.app)

    steps = (
        parse_build_steps_from_file(
            os.path.join(context_path, 'meta.yml')))
    steps.root_path = args.build_dir
    steps.context_path = context_path
    steps.identity_file = args.identity_file
    if not steps.identity_file:
        log.info('searching for ssh identity in default locations')
        steps.identity_file = find_default_identity_file()
    if args.tag:
        log.info('overriding version tag=%s', args.tag)
        steps.version = args.tag

    builder = DockerBuilder(steps, lambda: cli.docker_client().api)
    builder.stdout = cli.out
    builder.archive_only = args.archive_only
    builder.archive_file = args.archive
    builder.skip_cleanup = args.skip_cleanup

    if args.env:
        env = {}
        for entry in args.env:
            parts = entry.split('=', 1)
            if len(parts) != 2:
                cli.abort(
                    'Environment variables must follow the KEY=VALUE '
                    'format. Invalid entry: "{0}".'.format(entry))
            k, v = parts
            env[k] = v
        builder.extra_env = env

    if args.use_cache:
        cache_volume = '{0}__buildcache'.format(steps.name)
        cache_hostpath = None
        cache_path = '/tmp/cache'
        if args.cache:
            parts = args.cache.split(':', 1)
            if posixpath.isabs(parts[0]):
                cache_hostpath = parts[0]
                cache_volume = None
            else:
                cache_volume = parts[0]
            if len(parts) == 2:
                cache_path = parts[1]
            if not posixpath.isabs(cache_path):
                cli.abort('The cache "path" must be an absolute path.')

        builder.cache_volume = cache_volume
        builder.cache_hostpath = cache_hostpath
        builder.cache_path = cache_path
        builder.rebuild_cache = args.rebuild_cache
    else:
        builder.cache_volume = None
        builder.cache_hostpath = None
        builder.cache_path = None
        builder.rebuild_cache = False

    try:
        builder.run()
    except Exception as ex:
        log.debug('caught build exception', exc_info=1)
        log.error(ex.args[0])
        return -1
    return 0

def parse_build_steps(data):
    settings = yaml.safe_load(data)
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
            self.override_config = settings.get('config', {})

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
        with io.open(script_path, 'w') as fp:
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
            fp.write(u'find "$BUILD_CACHE" -mindepth 1 -delete\n')

        fp.write(self.command_prefix_script)

        for command in self.commands:
            fp.write(u'%s\n' % command)

        if self.archive_patterns:
            fp.write(self.archive_prefix_script)
            fp.write(u'tar czf "$BUILD_ARCHIVE_PATH" --posix %s\n' % (
                ' '.join(
                    u'"%s"' % pattern
                    for pattern in self.archive_patterns
                )
            ))

    setup_script = u'''\
set -eo pipefail

SSH_CONFIG_DIR="$HOME/.ssh"

mkdir -p "$SSH_CONFIG_DIR"
chmod 700 "$SSH_CONFIG_DIR"

if [ -f ssh_identity ]; then
    # copy instead of symlink so that we can chmod without issue
    cp ssh_identity "$SSH_CONFIG_DIR/ssh_identity"
    chmod 600 "$SSH_CONFIG_DIR/ssh_identity"
fi

cat > "$SSH_CONFIG_DIR/config" << EOF
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    IdentityFile "$SSH_CONFIG_DIR/ssh_identity"
EOF

# ensure we have a cache directory
if [ ! -d "$BUILD_CACHE" ]; then
    mkdir -p "$BUILD_CACHE"
fi
'''

    command_prefix_script = u'''
# be sure to fail if any of the below commands fail,
# in order to assist in proper debugging
set -e

cd "$BUILD_CONTEXT"

# user-defined commands below ####################
'''

    archive_prefix_script = u'''
# generate a binary archive
'''

class DockerBuilder(object):
    """ Execute a build on a docker client."""
    build = None

    src_volume = '/marina/src'
    dist_volume = '/marina/dist'

    cache_volume = None
    cache_hostpath = None
    cache_path = None
    rebuild_cache = False

    archive_file = None
    archive_only = False

    extra_env = None

    skip_cleanup = False

    @staticmethod
    def stdout(msg):
        sys.stdout.write(msg)

    def __init__(self, steps, connector):
        self.steps = steps
        self.connector = connector
        self.source_container = None
        self.runner_container = None
        self.runner_base_image = None

    def run(self):
        self._setup()
        try:
            if not self._create_cache():
                raise RuntimeError('failed to construct data cache')
            if not self._build_source_container():
                raise RuntimeError('failed to build source container')
            if self.archive_file and not self._build_archive():
                raise RuntimeError('failed to build archive')
            if self.archive_only:
                return
            if not self._build_runner_image():
                raise RuntimeError('failed to build runner image')
        finally:
            self._teardown()

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
        if self.source_container and not self.skip_cleanup:
            self._remove_container(self.source_container)

        if self.runner_container and not self.skip_cleanup:
            self._remove_container(self.runner_container)

        if self.runner_base_image and not self.skip_cleanup:
            self._remove_image(self.runner_base_image)

        if not self.skip_cleanup:
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
            self.client.remove_container(container, v=True)
        except:
            log.exception('failed to remove container=%s', container)

    def _remove_image(self, image):
        try:
            self.client.remove_image(image)
        except:
            log.exception('failed to remove image=%s', image)

    def _create_cache(self):
        if not self.cache_volume:
            log.info('no cache volume defined, skipping checks')
            return True

        do_create_cache = False
        try:
            self.client.inspect_volume(self.cache_volume)
        except docker.errors.NotFound:
            do_create_cache = True
            log.debug('could not find cache volume=%s', self.cache_volume)

        if do_create_cache:
            log.debug('creating cache volume=%s', self.cache_volume)
            self.client.create_volume(self.cache_volume)
        else:
            log.info('found cache volume=%s', self.cache_volume)
        return True

    def _build_source_container(self):
        log.info('building source')
        self.archive_name = '%s-%s.tar.gz' % (
            self.steps.name, self.steps.version)
        self.archive_path = posixpath.join(self.dist_volume, self.archive_name)

        env = {
            'BUILD_ROOT': self.src_volume,
            'BUILD_CONTEXT': posixpath.join(self.src_volume, 'context'),
            'BUILD_ARCHIVE_PATH': self.archive_path,
            'BUILD_NAME': self.steps.name,
            'BUILD_VERSION': self.steps.version,
            'BUILD_CACHE': self.cache_path,
        }
        if self.extra_env:
            env.update(self.extra_env)
        for k in sorted(env.keys()):
            log.debug('builder env %s = %s', k, env[k])

        binds = {}
        binds[self.build_dir] = {
            'bind': self.src_volume,
            'rw': True,
        }
        cache_volume = self.cache_volume or self.cache_hostpath
        if cache_volume:
            binds[cache_volume] = {
                'bind': self.cache_path,
                'rw': True,
            }

        host_config = self.client.create_host_config(
            binds=binds,
        )

        container = self.client.create_container(
            self.steps.compiler.base_image,
            command='/bin/bash build.sh',
            working_dir=self.src_volume,
            environment=env,
            volumes=[
                self.src_volume,
                self.dist_volume,
            ],
            user='root',
            host_config=host_config,
        )
        self.source_container = container.get('Id')
        log.info('created source container=%s', self.source_container)

        with self._attach(self.source_container):
            log.debug('starting container=%s', self.source_container)
            self.client.start(self.source_container)
            log.debug('started container=%s', self.source_container)
            ret = self.client.wait(self.source_container)['StatusCode']
        if ret != 0:
            log.error('source did not build successfully, status=%s', ret)
        else:
            log.info('source compiled successfully')
        return ret == 0

    def _build_archive(self):
        log.info('archiving build products')

        # docker api 1.20 introduces the archive concept but it returns a
        # tarball containing a single file. This requires a double copy to
        # get the data from the container. The below method only requires a
        # single copy.
        host_config = self.client.create_host_config(
            volumes_from=self.source_container,
        )

        container = self.client.create_container(
            self.steps.compiler.base_image,
            command='cat "%s"' % self.archive_path,
            user='root',
            host_config=host_config,
        )
        self.archive_container = container.get('Id')

        try:
            with io.open(self.archive_file, 'wb') as fp:
                with self._attach(
                    self.archive_container,
                    stdout=fp.write,
                    encoding=None,
                ):
                    log.debug('starting container=%s', self.archive_container)
                    self.client.start(self.archive_container)
                    log.debug('started container=%s', self.archive_container)
                    ret = self.client.wait(self.archive_container)['StatusCode']
        finally:
            self._remove_container(self.archive_container)

        if ret:
            log.error('failed to write archive to file, status=%s', ret)
            os.unlink(self.archive_file)
        else:
            log.info('archive written to file=%s', self.archive_file)
        return ret == 0

    def _build_runner_image(self):
        log.info('building runner image')

        # we cannot mount the slug into the new image using something like:
        #     docker build --volumes-from <builder_container>
        # so instead we inject the slug via:
        #     docker run --volumes-from <builder_container> \
        #     <runner_base_image> tar xzf <archive_file> -C /"
        if not self._build_runner_container():
            return False

        # commit the runner container as the new base image
        image = self.client.commit(self.runner_container)
        self.runner_base_image = image.get('Id')
        log.debug('committed runner to image=%s', self.runner_base_image)

        # configure the desired image metadata for the runner
        base_image_info = self.client.inspect_image(
            self.steps.runner.base_image,
        )
        runner_conf = self._get_runner_config(
            base_image_info,
            self.steps.runner.override_config,
        )

        buildfile = self._render_buildfile(self.runner_base_image, runner_conf)
        log.debug('buildfile: %r', buildfile)

        runner_tag = '{0}:{1}'.format(self.steps.name, self.steps.version)
        self.runner_image, _ = self._build_image(
            fileobj=io.BytesIO(buildfile.encode('utf-8')),
            tag=runner_tag,
        )

        if not self.runner_image:
            log.error('failed to build runner image')
            return False

        # we do not want to delete the base image, it's part of a chain
        self.runner_base_image = None

        log.info('runner compiled successfully to image=%s', self.runner_image)
        self.stdout('created image=%s\n' % runner_tag)
        return True

    def _build_runner_container(self):
        base_image = self.steps.runner.base_image

        host_config = self.client.create_host_config(
            volumes_from=self.source_container,
        )

        container = self.client.create_container(
            base_image,
            entrypoint='tar',
            command='xzf "%s" -C /' % self.archive_path,
            user='root',
            host_config=host_config,
        )
        self.runner_container = container.get('Id')

        with self._attach(self.runner_container):
            log.debug('starting container=%s', self.runner_container)
            self.client.start(self.runner_container)
            log.debug('started container=%s', self.runner_container)
            ret = self.client.wait(self.runner_container)['StatusCode']
        if ret:
            log.error('failed to install slug into runner, status=%s', ret)
            return False
        log.debug('slug installed into runner container')
        return True

    def _get_runner_config(self, base_image_info, overrides):
        conf = overrides.copy()
        base_image_conf = base_image_info['Config']

        conf.setdefault('Author', base_image_info['Author'])
        conf.setdefault('Cmd', base_image_conf['Cmd'] or [])
        conf.setdefault('Entrypoint', base_image_conf['Entrypoint'] or [])
        conf.setdefault('User', base_image_conf['User'] or 0)
        conf.setdefault('WorkingDir', base_image_conf['WorkingDir'] or '/')

        env = conf.setdefault('Env', {})
        for entry in base_image_conf['Env'] or []:
            key, value = entry.split('=', 1)
            env.setdefault(key, value)

        conf['Volumes'] = (
            conf.get('Volumes', []) +
            # base_image_conf['Volumes'] is normally a dict
            # and we only want the keys
            [v for v in base_image_conf['Volumes'] or {}]
        )

        ports = conf.get('ExposedPorts', {})
        ports.update(base_image_conf.get('ExposedPorts') or {})
        conf['ExposedPorts'] = ports

        return conf

    def _render_buildfile(self, base_image, conf):
        """ Convert an image metadata into a file-like object that can be used
        as a Dockerfile in a build context.

        """
        opts = ['FROM {0}'.format(self.runner_base_image)]

        author = conf.get('Author')
        if author:  # avoid an invalid maintainer
            opts.append('MAINTAINER {0}'.format(author))

        command = conf.get('Cmd')
        if command is not None:
            if isinstance(command, collections.abc.Sequence):
                command = json.dumps(command)
            opts.append('CMD {0}'.format(command))

        entrypoint = conf.get('Entrypoint')
        if entrypoint is not None:
            if isinstance(entrypoint, collections.abc.Sequence):
                entrypoint = json.dumps(entrypoint)
            opts.append('ENTRYPOINT {0}'.format(entrypoint))

        ports = conf.get('ExposedPorts')
        if ports:  # there is no way to delete ports so ignore None
            for port in ports:
                opts.append('EXPOSE {0}'.format(port))

        volumes = conf.get('Volumes')
        if volumes:  # there is no way to delete volumes so ignore None
            for volume in volumes:
                opts.append('VOLUME {0}'.format(volume))

        working_dir = conf.get('WorkingDir')
        if working_dir is not None:
            opts.append('WORKDIR {0}'.format(working_dir))

        user = conf.get('User')
        if user is not None:
            opts.append('USER {0}'.format(user))

        env = conf.get('Env')
        if env:  # there is no way to delete env keys so ignore None
            for key, value in env.items():
                opts.append('ENV {0} {1}'.format(key, value))

        return '\n'.join(opts)

    def _build_image(self, **kw):
        """ Thin wrapper around :meth:`docker.Client.build` that can stream
        the build output.

        """
        stream = io.StringIO()
        for chunk in self.client.build(rm=True, decode=True, **kw):
            if 'error' in chunk:
                raise Exception(
                    'error while building image: {0}'.format(chunk['error']),
                    chunk, stream.getvalue(),
                )
            elif 'stream' in chunk:
                msg = chunk['stream']
                self.stdout(msg)
                stream.write(msg)

        output = stream.getvalue()

        srch = r'Successfully built ([0-9a-f]+)'
        match = re.search(srch, output)
        if not match:
            return None, output
        return match.group(1), output

    @contextmanager
    def _attach(self, container, stdout=None, encoding='utf8'):
        client = self.connector()
        if stdout is None:
            stdout = self.stdout
        should_stop = False

        signal = threading.Condition()
        exc_info = []

        def watcher():
            log.debug('attaching to container=%s', container)
            try:
                stream = client.attach(container, stream=True,
                                       stdout=True, stderr=True)
            except:
                log.debug('exception caught while attaching to container=%s',
                          container, exc_info=True)
                log.error('failed to attach to container=%s', container)
                exc_info.append(sys.exc_info())
                return
            else:
                log.debug('attached to container=%s', container)

            signal.acquire()
            signal.notify_all()
            signal.release()

            try:
                num_bytes = 0
                for chunk in stream:
                    num_bytes += len(chunk)
                    if encoding:
                        chunk = chunk.decode(encoding)
                    stdout(chunk)

                    if should_stop:
                        break
                log.debug('read %d bytes from container=%s',
                          num_bytes, container)
            except:
                log.debug('exception caught while reading from container=%s',
                          container, exc_info=True)
                log.error('failure while reading from attached container=%s',
                          container)
                exc_info.append(sys.exc_info())
                return

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
        try:
            yield
            th.join()
            if exc_info:
                reraise(*exc_info[0])
        except:
            should_stop = True
            log.debug('detaching early from container=%s', container)
            raise

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
        for fname in ('ssh_identity', 'id_rsa', 'id_dsa'):
            path = os.path.join(searchpath, fname)
            if os.path.exists(path):
                return path
