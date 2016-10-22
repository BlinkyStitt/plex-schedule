#!/usr/bin/env python
import setuptools


setuptools.setup(
    author='Bryan Stitt',
    author_email='bryan@stitthappens.com',
    description='Mark shows unwatched on a schedule.',
    long_description=__doc__,
    entry_points={
        'console_scripts': [
            'plex-schedule = plex_schedule.cli:cli',
        ],
    },
    install_requires=[
        'click',
        'plexapi',
        'sqlalchemy',
        'PyYAML',
    ],  # keep this in sync with requirements.in
    name='plex_schedule',
    packages=setuptools.find_packages(),
    version='0.0.1.dev0',
)
