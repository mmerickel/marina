unreleased
==========

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
