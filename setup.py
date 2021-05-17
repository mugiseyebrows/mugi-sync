from setuptools import setup, find_packages

with open('README.rst', encoding='utf-8') as f:
    long_description = f.read()

setup(
    packages = find_packages(),
    name = 'mugisync',
    version='0.0.3',
    author="Stanislav Doronin",
    author_email="mugisbrows@gmail.com",
    url='https://github.com/mugiseyebrows/mugi-sync',
    description='File synchronization utility',
    long_description = long_description,
    install_requires = ['eventloop'],
    entry_points={
        'console_scripts': [
            'mugi-sync = mugisync:main'
        ]
    },
)