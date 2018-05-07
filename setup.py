from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext as _build_ext


class build_ext(_build_ext):
    def finalize_options(self):
        super().finalize_options()
        # Prevent numpy from thinking it is still in its setup process:
        __builtins__.__NUMPY_SETUP__ = False
        import numpy
        self.include_dirs.append(numpy.get_include())


setup(
    name='rtfMRI',
    version='0.0.1',
    setup_requires=[
        'cython',
        'numpy',
        'pytest'
    ],
    install_requires=[
        'cython',
        'pybind11',
        'numpy',
        'scipy',
        'sklearn',
        'pydicom',
        'toml',
        'watchdog',
        'ipython',
        'jupyter',
        'pytest',
        'flake8',
        'mypy',
        'click',
        'brainiak'
    ],
    extras_require={},
    author='Princeton Neuroscience Institute and Intel Corporation',
    author_email='dsuo@princeton.edu',
    url='https://github.com/brainiak/rtAttenPenn',
    description='Brain Imaging Analysis Kit Cloud',
    license='Apache 2',
    keywords='neuroscience, algorithm, fMRI, distributed, scalable',
    cmdclass={'build_ext': build_ext},
    packages=find_packages(),
    ext_modules=[
        Extension('rtAttenPy_v0.highpass', [
                  'rtAttenPy_v0/highpass.pyx'], include_dirs=['.']),
        Extension('rtAtten.highpass', [
                  'rtAtten/highpass.pyx'], include_dirs=['.'])
    ],
    python_requires='>=3.4',
    options={'build_ext': {'inplace': True, 'force': True}},
    entry_points='''
        [console_scripts]
        client=rtfMRI.scripts.ClientMain:ClientMain
        server=rtfMRI.scripts.ServerMain:ServerMain
    '''
)
