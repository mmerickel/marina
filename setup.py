import os
import sys

from setuptools import find_packages
from setuptools import setup
from setuptools.command.test import test as TestCommand

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as fp:
    README = fp.read()
with open(os.path.join(here, 'CHANGES.rst')) as fp:
    CHANGES = fp.read()

requires = [
    'docker-py >= 0.3.2',
    'PyYAML',
    'setuptools',
    'subparse',
]

tests_require = [
    'pytest',
]

entry_points = """
    [console_scripts]
    marina = marina.cli:main
"""

class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args or ['tests'])
        sys.exit(errno)

setup(
    name='marina',
    version='0.0.3',
    description='marina manages docker instances',
    long_description=README + '\n\n' + CHANGES,
    url='https://github.com/mmerickel/marina',
    author='Michael Merickel',
    author_email='michael@merickel.org',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
    ],
    keywords='docker devops deploy build orchestration',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=requires,
    tests_require=tests_require,
    extras_require={
        'testing': tests_require,
    },
    cmdclass={'test': PyTest},
    entry_points=entry_points,
)
