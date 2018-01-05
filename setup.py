from setuptools import setup, Extension
import numpy

setup(
    name='rtAttenPy',
    version='0.0.1',
    install_requires=[
        'click',
        'pathos',
        'tqdm',
        'contexttimer',
        'watchdog',
        'binaryornot',
        'matplotlib',
        'pandas',
        'nilearn',
        'numpy',
        'scipy',
        'pybind11',
        'cython',
        'ipython',
        'pika',
        'ipywidgets',
        'jupyter_contrib_nbextensions',
        'jupyter',
        'sklearn',
    ],
    extras_require={},
    author='Princeton Neuroscience Institute and Intel Corporation',
    author_email='dsuo@princeton.edu',
    url='https://github.com/brainiak/rtAttenPy',
    description='Brain Imaging Analysis Kit Cloud',
    license='Apache 2',
    keywords='neuroscience, algorithm, fMRI, distributed, scalable',
    packages=['rtAttenPy'],
    ext_modules=[
        Extension('rtAttenPy.highpass',
                  ['rtAttenPy/highpass.pyx'],
                  include_dirs=[numpy.get_include()]
                  )
    ],
    python_requires='>=3.4',
    entry_points='''
        [console_scripts]
        watch=rtcloud.watcher:watch
        serve=rtcloud.server:serve
    '''
)
