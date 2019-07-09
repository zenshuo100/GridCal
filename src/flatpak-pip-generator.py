#!/usr/bin/env python3
# https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/master/pip/flatpak-pip-generator
__license__ = 'MIT'

import argparse
import json
import hashlib
import os
import subprocess
import tempfile
import urllib.request
import shlex
from collections import OrderedDict


parser = argparse.ArgumentParser()
parser.add_argument('packages', nargs='*')
parser.add_argument('--python2', action='store_true',
                    help='Look for a Python 2 package')
parser.add_argument('--cleanup', choices=['scripts', 'all'],
                    help='Select what to clean up after build')
parser.add_argument('--requirements-file',
                    help='Specify requirements.txt file')
parser.add_argument('--build-only', action='store_const',
                    dest='cleanup', const='all',
                    help='Clean up all files after build')
parser.add_argument('--output',
                    help='Specify output file name')
opts = parser.parse_args()


def get_pypi_url(name: str, filename: str) -> str:
    url = 'https://pypi.python.org/pypi/{}/json'.format(name)
    print('Extracting download url for', name)
    with urllib.request.urlopen(url) as response:
        body = json.loads(response.read().decode('utf-8'))
        for release in body['releases'].values():
            for source in release:
                if source['filename'] == filename:
                    return source['url']
        else:
            raise Exception('Failed to extract url from {}'.format(url))


def get_package_name(filename: str) -> str:
    segments = filename.split("-")
    if len(segments) == 2:
        return segments[0]
    return "-".join(segments[:len(segments) - 1])


def get_file_hash(filename: str) -> str:
    sha = hashlib.sha256()
    print('Generating hash for', filename)
    with open(filename, 'rb') as f:
        while True:
            data = f.read(1024 * 1024 * 32)
            if not data:
                break
            sha.update(data)
        return sha.hexdigest()


if not opts.packages and not opts.requirements_file:
    exit("Please specifiy either packages or requirements file argument")

packages = []
if opts.requirements_file and os.path.exists(opts.requirements_file):
    with open(opts.requirements_file, 'r') as req_file:
        packages = [package.strip() for package in req_file.readlines()]
else:
    packages = opts.packages


if opts.python2:
    pip_executable = 'pip2'
    pip_install_prefix = '--install-option="--prefix=${FLATPAK_DEST}"'
else:
    pip_executable = 'pip3'
    pip_install_prefix = '--prefix=${FLATPAK_DEST}'

modules = []

for package in packages:
    package_name = 'python{}-{}'.format('2' if opts.python2 else '3',
                                        package.split("=")[0])
    tempdir_prefix = 'pip-generator-{}-'.format(package_name)
    with tempfile.TemporaryDirectory(prefix=tempdir_prefix) as tempdir:

        pip_download = [pip_executable, 'download', '--dest', tempdir]
        pip_command = [
            pip_executable,
            'install',
            '--no-index',
            '--find-links="file://${PWD}"',
            pip_install_prefix,
            shlex.quote(package)
        ]
        module = OrderedDict([
            ('name', package_name),
            ('buildsystem', 'simple'),
            ('build-commands', [' '.join(pip_command)]),
            ('sources', []),
        ])

        if opts.cleanup == 'all':
            module['cleanup'] = ['*']
        elif opts.cleanup == 'scripts':
            module['cleanup'] = ['/bin', '/share/man/man1']

        try:
            subprocess.run(pip_download + [
                '--no-binary', ':all:', package
            ], check=True)
            for filename in os.listdir(tempdir):
                name = get_package_name(filename)
                if name == 'setuptools':  # Already installed
                    continue
                sha256 = get_file_hash(os.path.join(tempdir, filename))
                url = get_pypi_url(name, filename)
                source = OrderedDict([
                    ('type', 'file'),
                    ('url', url),
                    ('sha256', sha256),
                ])
                module['sources'].append(source)
        except subprocess.CalledProcessError:
            print("Failed to download {}".format(package))
            print("Please fix the module manually in the generated file")
        modules.append(module)

if opts.requirements_file:
    output_filename = opts.output + '.json'
else:
    output_filename = opts.output or package_name + '.json'

with open(output_filename, 'w') as output:
    output.write(json.dumps(modules, indent=4))
