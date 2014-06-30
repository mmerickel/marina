marina
======

Marina is a tool for building docker images with a focus on separating
compile-time dependencies from run-time dependencies in order to keep
the shipped images small and secure.

Usage
-----

::

  marina -vvv build examples/shootout

App Config
----------

::

  name: dummy

  compile:
    base_image: ubuntu:14.04
    commands:
      - dd if=/dev/urandom of=/srv/dummy bs=50kB count=1
    files:
      - /srv/dummy

  run:
    base_image: ubuntu:14.04
