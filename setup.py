from setuptools import setup

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
    ],
    extras_require={},
    author='Princeton Neuroscience Institute and Intel Corporation',
    author_email='dsuo@princeton.edu',
    url='https://github.com/brainiak/rtAttenPy',
    description='Brain Imaging Analysis Kit Cloud',
    license='Apache 2',
    keywords='neuroscience, algorithm, fMRI, distributed, scalable',
    packages=['rtAttenPy'],
    python_requires='>=3.4',
    entry_points='''
        [console_scripts]
        watch=rtcloud.watcher:watch
        serve=rtcloud.server:serve
    '''
)
