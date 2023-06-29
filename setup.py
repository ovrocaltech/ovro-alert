from setuptools import setup
from setuptools_scm import get_version

setup(name='ovro-alert',
      version=get_version(),
      url='http://github.com/ovrocaltech/ovro-alert',
      install_requires=['requests',
                        'setuptools_scm'],
      packages=['ovro_alert'],
      zip_safe=False)
