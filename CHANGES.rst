0.4.2 (2020-01-28)
==================

- Avoid blocking the main thread moar so that SIGINT works better.

0.4.1 (2020-01-28)
==================

- Avoid blocking the main thread so that SIGINT works better.

0.4.0 (2019-03-25)
==================

- Require ``docker >= 3.0``.

0.3.0 (2017-03-10)
==================

- Update to use ``docker`` package instead of the now-defunct ``docker-py``
  package.

0.2.0 (2016-10-11)
==================

- Pin to ``docker-py < 1.10`` until a bug is fixed.
  See https://github.com/docker/docker-py/issues/1211

- [build] The cache volume is now created as a docker volume instead of a
  data container. It can be controlled using ``docker volume`` commands.

- [build] Properly exit with an error if there was an issue reading
  from the container stdout/stderr while attached.

- [build] The ``busybox`` image is no longer required. The archive will
  be pulled directly from the build container.

0.1.1 (2016-10-07)
==================

- [build] Fix an issue when the system does not already have the busybox
  image installed.

0.1.0 (2016-09-14)
==================

- [build] Fix some unicode issues when running on Python 2.

0.0.9 (2016-07-25)
==================

- [build] Add another workaround for docker-py when pulling a new image.
  See https://github.com/docker/docker-py/issues/1134

0.0.8 (2016-07-22)
==================

- Support Python 3.

- [build] Stop using an API that was removed in docker 1.12.

- [build] Allow the BUILD_CONTEXT (cwd in scripts) to be writeable.
  Previously it was mounted readonly.

- [build] Search for the ssh identity file in known paths.

- [build] Add a workaround for a bug in docker-py causing the runner image
  to fail to build. See https://github.com/docker/docker-py/issues/1134

0.0.7 (2016-02-18)
==================

- [build] Flush stdout to keep container messages from pausing.

0.0.6 (2016-01-08)
==================

- [build] Delete any volumes associated with a container.
- [build] Fix usage of ExposedPorts from runner base image.

0.0.5 (2015-08-25)
==================

- [build] Exit with an error code upon failure instead of 0.

0.0.4 (2015-08-24)
==================

- Turn off docker hostname verification to enable connections with
  docker-machine instances over SSL until
  https://github.com/docker/docker-py/issues/731 is resolved.

- [build] Avoid detaching from the archive container before the tarfile
  has been fully written to disk.

- [build] Add ``--skip-cleanup`` option for keeping images/containers/files
  around after the build.

0.0.3 (2014-11-19)
==================

- Support docker 1.3.x and its TLS requirements.

0.0.2 (2014-07-12)
==================

- Support ``--quiet`` for suppressing output.

- [build] Add ``--env`` option for specifying credentials and other
  configurable build-time settings.

- [build] Ensure the ``busybox`` image is around.

0.0.1 (2014-07-03)
==================

- Initial release.

- First cut at "marina build" to generate a working docker container.
