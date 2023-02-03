from setuptools import setup, find_packages

setup(
    name='sqlalchemy-django-admin',
    description='Django Admin for SQLAlchemy',
    author='kartashov',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        'django>=4.0',
    ],
)
