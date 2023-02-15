from pathlib import Path
from setuptools import setup, find_packages

this_directory = Path(__file__).parent
long_description = (this_directory / 'README.md').read_text()

setup(
    name='sqlalchemy-django-admin',
    description='Django Admin for SQLAlchemy',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='kartashov',
    version='0.0.5',
    packages=find_packages(),
    install_requires=[
        'django>=4.0',
        'sqlalchemy>=1.4',
    ],
)
