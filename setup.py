from setuptools import find_packages
from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

requires = [
    'cliff',
    'docker-py',
    'requests',
    'pyyaml',
    'path.py'
]

entry_points = """
    [console_scripts]
    marina = marina.cli.main:main
"""

setup(
    name='marina',
    version='0.1',
    description='marina manages docker instances',
    long_description=README,
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
    ],
    packages=find_packages(),
    install_requires=requires,
    test_suite='marina.tests',
    entry_points=entry_points,
)
