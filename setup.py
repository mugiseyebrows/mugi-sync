from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

setup(
    packages = find_packages(),
    name = 'mugisync',
    version='0.0.14',
    author="Stanislav Doronin",
    author_email="mugisbrows@gmail.com",
    url='https://github.com/mugiseyebrows/mugi-sync',
    description="Continously syncronizes local directory with another local or shared directory (poor person's syncthing) or remote directory over ssh (poor person's one-way sshfs)",
    long_description = long_description,
    install_requires = ['eventloop','colorama','paramiko'],
    entry_points={
        'console_scripts': [
            'mugisync = mugisync:main'
        ]
    },
)