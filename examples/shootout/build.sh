#!/bin/bash

set -e
set -x

sed -i'' -e's@http://archive.@http://us.archive.@g' /etc/apt/sources.list
apt-get update
apt-get -y -q install build-essential python python-dev python-setuptools python-virtualenv git-core

cd /srv
VENV=$(pwd)/venv
virtualenv $VENV
git clone https://github.com/Pylons/shootout.git
cd shootout
$VENV/bin/python setup.py develop
