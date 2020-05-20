from setuptools import setup
import ast
import sys

setup_requires = ['setuptools >= 30.3.0', 'setuptools-git-version']

if {'pytest', 'test', 'ptr'}.intersection(sys.argv):
    setup_requires.append('pytest-runner')


setup(description="literature-to-facts",
      long_description=open('README.md').read(),
      version='0.1.0',
      include_package_data=True,
      setup_requires=setup_requires)
