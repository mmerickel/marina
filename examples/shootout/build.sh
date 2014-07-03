#!/bin/bash

set -eo pipefail
set -x

apt-get -y -q install python-dev python-setuptools python-virtualenv git-core

APP_ROOT=/app

if [[ -d "$BUILD_CACHE/app" ]]; then
    cp -a "$BUILD_CACHE/app" "$APP_ROOT"
    cd "$APP_ROOT"
    git pull
else
    git clone https://github.com/Pylons/shootout.git "$APP_ROOT"
    cd "$APP_ROOT"
    virtualenv .
fi

bin/python setup.py develop

rsync -az "$APP_ROOT/" "$BUILD_CACHE/app"
