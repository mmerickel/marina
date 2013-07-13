import os
from setuptools import find_packages
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

requires = [
    'cliff',
    'requests',
]

entry_points = """
    [console_scripts]
    marina = marina:main
"""

setup(name='marina',
      version='0.1',
      description='marina manages docker instances',
      long_description=README,
      packages=find_packages(),
      install_requires=requires,
      test_suite='marina.tests',
      entry_points=entry_points)
