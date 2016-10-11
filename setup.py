import os

from setuptools import find_packages
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as fp:
    README = fp.read()
with open(os.path.join(here, 'CHANGES.rst')) as fp:
    CHANGES = fp.read()

requires = [
    'docker-py >= 0.3.2,<1.10', # https://github.com/docker/docker-py/issues/1211
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

setup(
    name='marina',
    version='0.2.0',
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
    entry_points=entry_points,
)
