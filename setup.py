from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext


class build_ext(_build_ext):
    def finalize_options(self):
        _build_ext.finalize_options(self)
        # Prevent numpy from thinking it is still in its setup process:
        __builtins__.__NUMPY_SETUP__ = False
        import numpy
        self.include_dirs.append(numpy.get_include())


setup(
    name='rtAttenPy_v0',
    version='0.0.1',
    setup_requires=[
        'numpy'
    ],
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
        'scikit-learn',
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
    url='https://github.com/brainiak/rtAttenPy_v0',
    description='Brain Imaging Analysis Kit Cloud',
    license='Apache 2',
    keywords='neuroscience, algorithm, fMRI, distributed, scalable',
    cmdclass={'build_ext': build_ext},
    packages=['rtAttenPy_v0'],
    ext_modules=[
        Extension('rtAttenPy_v0.highpass',
                  ['rtAttenPy_v0/highpass.pyx']
                  )
    ],
    python_requires='>=3.4',
    entry_points='''
        [console_scripts]
        watch=rtcloud.watcher:watch
        serve=rtcloud.server:serve
    '''
)
