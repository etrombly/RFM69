#encoding:UTF-8

# =============================================================================
# This fabfile will setup and run test on a remote Raspberry Pi
# =============================================================================

import socket
from os import sep, remove
from fabric.api import cd, lcd, task
from fabric.operations import run, local, prompt, put, sudo
from fabric.network import needs_host
from fabric.state import env, output
from fabric.contrib import files
from fabric.contrib.project import rsync_project
from fabtools import mysql
from fabtools import user, group, require, deb
from fabtools.python import virtualenv, install_requirements, install
from termcolor import colored
from unipath import Path, DIRS

# =============================================================================
# SETTINGS 
# =============================================================================

class Settings:
    DEPLOY_USER = "pi"                      # Username for access to pi
    ROOT_NAME = "rfm69radio-test"           # A system friendly name for test project
    DIR_PROJ = "/srv/" + ROOT_NAME + "/"    # The root 
    DIR_ENVS = DIR_PROJ + 'envs/'           # Where the Virtual will live
    DIR_CODE = DIR_PROJ + 'tests/'          # Where the tests will live
    
    SYNC_DIRS = [                      
        ("./", DIR_CODE),
        ("../RFM69Radio", DIR_CODE)
    ]                  
    # Requirements
    REQUIRMENTS_FILES = [
        DIR_CODE + 'requirements_remote.txt',
    ]
    TEST_PYTHON_VERSIONS = [ (2,7), (3,5) ]

# =============================================================================
# END OF SETTINGS 
# =============================================================================

env.user = Settings.DEPLOY_USER

@task
def sync():
    sync_files()

@task
def test():
    sync_files()
    for version in Settings.TEST_PYTHON_VERSIONS:
        install_venv_requirements(version)
        run_tests(version)

@task
def init():
    make_dirs()
    sync_files()
    set_permissions()
    for version in Settings.TEST_PYTHON_VERSIONS:
        create_virtualenv(version)
        install_venv_requirements(version)

 
# =============================================================================
# SUB TASKS
# =============================================================================

# ----------------------------------------------------------------------------------------
# Helper functions below
# ----------------------------------------------------------------------------------------

def print_title(title):
    pad = "-" * (80 - len(title) - 4)
    print (colored("-- {} {}".format(title,pad), 'blue', 'on_yellow'))

def print_test_title(title):
    pad = "-" * (80 - len(title) - 4)
    print (colored("-- {} {}".format(title,pad), 'white', 'on_blue'))

def print_error(message):
    print (colored(message, 'red'))

def print_success(message):
    print (colored(message, 'green'))

# ----------------------------------------------------------------------------------------
# Sub Tasks - Project
# ----------------------------------------------------------------------------------------

# Make project folders
def make_dirs():
    print_title('Making folders')
    for d in [Settings.DIR_PROJ, Settings.DIR_ENVS] + [ y for x, y in Settings.SYNC_DIRS]:
        exists = files.exists(d)
        print("File", d, "exists?", exists)
        if not exists:
            sudo('mkdir -p {}'.format(d))
            sudo('chown -R %s %s' % (env.user, d))
    set_permissions()

# Sync project fioles to server
def sync_files():
    print_title('Synchronising code')
    for local_dir, remote_dir in Settings.SYNC_DIRS:
        print('Copy from {} to {}'.format(local_dir, remote_dir))
        rsync_project(   
            remote_dir=remote_dir,
            local_dir=local_dir,
            exclude=("fabfile.py","*.pyc",".git","*.db","*.sqlite3", "*.log", "*.csv" '__pychache__', '*.md','*.DS_Store', 'test-node/'),
            extra_opts="--filter 'protect *.csv' --filter 'protect *.json' --filter 'protect *.db'",
            delete=False
        )

# Set folder permissions
def set_permissions():
    print_title('Setting folder and file permissions')
    sudo('chmod -R %s %s' % ("u=rwx,g=rwx,o=r", Settings.DIR_CODE))
    sudo('chmod -R %s %s' % ("u=rwx,g=rwx,o=r", Settings.DIR_ENVS))

def get_env(py_version):
    major, minor = py_version
    ver_name = "{}.{}".format(major, minor)
    env_name = "env-python-{}".format(ver_name)
    return Settings.DIR_ENVS + env_name, ver_name, env_name

# Create a new environments
def create_virtualenv(py_version):
    env_path, ver_name, _ = get_env(py_version)
    print_title('Creating Python {} virtual environment: {}'.format(py_version, env_path))
    sudo('pip3 install virtualenv')
    sudo('pip install virtualenv')
    if files.exists(env_path):
        print("Virtual Environment already exists")
        return
    run('virtualenv -p python{0} {1}'.format(ver_name, env_path))

# Install Python requirments
def install_venv_requirements(py_version):
    env_path, ver_name, env_name = get_env(py_version)
    print_title('Installing remote virtual env requirements')
    with virtualenv(env_path):
        for path in Settings.REQUIRMENTS_FILES:
            if files.exists(path):
                install_requirements(path, use_sudo=False)
                print_success("Installed: {}".format(path))
            else:
                print_error("File missing: {}".format(path))
                return

def run_tests(py_version):
    env_path, _, _ = get_env(py_version)
    print_test_title('Running tests in venv: {}'.format(env_path))
    with virtualenv(env_path):
        with cd(Settings.DIR_CODE):
            run('pytest')