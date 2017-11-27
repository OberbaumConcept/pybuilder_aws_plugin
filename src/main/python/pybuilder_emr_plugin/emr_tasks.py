#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import os
import subprocess
import zipfile
from distutils import dir_util

from pybuilder.core import depends, task
from pybuilder.plugins.python.distutils_plugin import build_install_dependencies_string

from .helpers import (upload_helper,
                      check_acl_parameter_validity,
                      )

PROPERTY_S3_BUCKET_NAME = "emr.s3.bucket-name"
PROPERTY_S3_BUCKET_PREFIX = "emr.s3.bucket-prefix"
PROPERTY_S3_FILE_ACCESS_CONTROL = "emr.s3.file-access-control"
PROPERTY_S3_RELEASE_PREFIX = "emr.s3.release-prefix"
RELEASE_PREFIX_DEFAULT = "latest"
_EMR_PACKAGE_DIR = "emr-package"


def zip_recursive(archive, directory, folder="", excludes=[]):
    """Zip directories recursively"""
    for item in os.listdir(directory):
        if item in excludes:
            continue
        if os.path.isfile(os.path.join(directory, item)):
            archive.write(os.path.join(directory, item), os.path.join(folder, item), zipfile.ZIP_DEFLATED)
        elif os.path.isdir(os.path.join(directory, item)):
            zip_recursive(archive, os.path.join(directory, item), folder=os.path.join(folder, item), excludes=excludes)


def prepare_dependencies_dir(logger, project, target_directory, excludes=None):
    """Get all dependencies from project and install them to given dir"""
    excludes = excludes or []
    dependencies = ast.literal_eval(build_install_dependencies_string(project))

    index_url = project.get_property("install_dependencies_index_url")
    if index_url:
        index_url = "--index-url {0}".format(index_url)
    else:
        index_url = ""

    pip_cmd = "pip install --target {0} {1} {2}"
    for dependency in dependencies:
        if dependency in excludes:
            logger.debug("Not installing dependency {0}.".format(dependency))
            continue

        cmd = pip_cmd.format(target_directory, index_url, dependency)
        logger.debug("Installing dependency {0}: {1}".format(dependency, cmd))

        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        process.communicate()
        if process.returncode != 0:
            msg = "Command {0} failed to install dependency: {1}".format(cmd, process.returncode)
            raise Exception(msg)


def get_emr_package_dir(project):
    return os.path.join(project.expand_path("$dir_target"), _EMR_PACKAGE_DIR)


def get_path_to_zipfile(project):
    return os.path.join(get_emr_package_dir(project), "{0}.zip".format(project.name))


def write_version(project, archive):
    """Get the current version and write it to a version file"""
    filename = os.path.join(get_emr_package_dir(project), "VERSION")
    with open(filename, "w") as version_file:
        version_file.write(project.version)
    archive.write(filename, "VERSION")


@task("emr_package",
      description="Package the modules, dependencies and scripts into a emr zip")
@depends("clean",
         "install_build_dependencies",
         "publish",
         "package")
def emr_package(project, logger):
    emr_package_dir = get_emr_package_dir(project)
    emr_dependencies_dir = os.path.join(emr_package_dir, "dependencies")
    excludes = ["boto", "boto3"]
    logger.info("Going to prepare dependencies.")
    prepare_dependencies_dir(logger, project, emr_dependencies_dir, excludes=excludes)
    logger.info("Going to assemble the emr-package-zip.")
    path_to_zipfile = get_path_to_zipfile(project)
    logger.debug("Going to assemble the emr-package-zip: {}".format(path_to_zipfile))
    archive = zipfile.ZipFile(path_to_zipfile, "w")
    if os.path.isdir(emr_dependencies_dir):
        zip_recursive(archive, emr_dependencies_dir)
    sources = project.expand_path("$dir_source_main_python")
    excludes = ["spark-warehouse"]
    zip_recursive(archive, sources, excludes=excludes)
    write_version(project, archive)
    resources = os.path.join(os.path.dirname(sources), "resources")
    print("resources {}".format(resources))
    if os.path.exists(resources) and os.path.isdir(resources):
        zip_recursive(archive, resources)
    archive.close()
    logger.info("emr-package-zip is available at: {0}".format(path_to_zipfile))
    scripts = project.expand_path("$dir_source_main_scripts")
    if os.path.exists(scripts) and os.path.isdir(scripts):
        logger.info("copying scripts to: {0}".format(emr_package_dir))
        dir_util.copy_tree(scripts, emr_package_dir)


@task("emr_upload_to_s3", description="Upload a packaged lambda-zip to S3")
@depends("emr_package")
def emr_upload_to_s3(project, logger):
    emr_package_dir = get_emr_package_dir(project)
    bucket_prefix = project.get_property(PROPERTY_S3_BUCKET_PREFIX)
    bucket_name = project.get_mandatory_property(PROPERTY_S3_BUCKET_NAME)
    acl = project.get_property(PROPERTY_S3_FILE_ACCESS_CONTROL)
    check_acl_parameter_validity(PROPERTY_S3_FILE_ACCESS_CONTROL, acl)

    for item in os.listdir(get_emr_package_dir(project)):
        filepath = os.path.join(emr_package_dir, item)
        if os.path.isfile(filepath):
            logger.debug("Found file to upload: {0}".format(item))
            with open(filepath, "rb") as fp:
                data = fp.read()
            keyname_version = "{0}v{1}/{2}".format(bucket_prefix, project.version, item)
            upload_helper(logger, bucket_name, keyname_version, data, acl)
            logger.info("uploaded: {0} to {1}".format(item, keyname_version))


@task("emr_release", description="Copy emr zip file from versioned path to latest path in S3")
def emr_release(project, logger):
    emr_package_dir = get_emr_package_dir(project)
    bucket_prefix = project.get_property(PROPERTY_S3_BUCKET_PREFIX)
    bucket_name = project.get_mandatory_property(PROPERTY_S3_BUCKET_NAME)
    release_prefix = project.get_property(PROPERTY_S3_RELEASE_PREFIX, RELEASE_PREFIX_DEFAULT)
    acl = project.get_property(PROPERTY_S3_FILE_ACCESS_CONTROL)
    check_acl_parameter_validity(PROPERTY_S3_FILE_ACCESS_CONTROL, acl)

    for item in os.listdir(get_emr_package_dir(project)):
        filepath = os.path.join(emr_package_dir, item)
        if os.path.isfile(filepath):
            logger.debug("Found file to upload: {0}".format(item))
            with open(filepath, "rb") as fp:
                data = fp.read()
            keyname_version = "{0}{1}/{2}".format(bucket_prefix, release_prefix, item)
            upload_helper(logger, bucket_name, keyname_version, data, acl)
            logger.info("uploaded: {0} to {1}".format(item, keyname_version))
