#!/usr/bin/env python
# -*- coding: utf-8 -*-
import filecmp
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pprint import pprint

import boto3
import mock
from moto import mock_s3
from pybuilder.core import Logger, Project
from pybuilder.errors import BuildFailedException
from unittest2 import TestCase

from pybuilder_emr_plugin import emr_package, emr_upload_to_s3, initialize_plugin, emr_release, emr_tasks
from pybuilder_emr_plugin.emr_tasks import prepare_dependencies_dir
from pybuilder_emr_plugin.helpers import check_acl_parameter_validity, permissible_acl_values


class TestCheckACLParameterValidity(TestCase):
    def test_invalid_value_raises_exception(self):
        self.assertRaises(BuildFailedException, check_acl_parameter_validity, "some_acl_property", "no_such_value")

    def test_all_valid_values_ok(self):
        for v in permissible_acl_values:
            check_acl_parameter_validity("some_acl_property", v)


class TestInitializePlugin(TestCase):
    def test_initialize_sets_variables_correctly(self):
        project = Project(".")
        initialize_plugin(project)
        self.assertEqual(project.get_property(emr_tasks.PROPERTY_S3_FILE_ACCESS_CONTROL), "bucket-owner-full-control")
        self.assertEqual(project.get_property(emr_tasks.PROPERTY_S3_BUCKET_PREFIX), "")
        self.assertEqual(project.get_property(emr_tasks.PROPERTY_S3_RELEASE_PREFIX), emr_tasks.RELEASE_PREFIX_DEFAULT)


class PackageTest(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="palp-")
        self.testdir = os.path.join(self.tempdir, "package_emr_test")
        self.project = Project(basedir=self.testdir, name="palp", version="123")
        self.source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "package_emr_test/")
        shutil.copytree(self.source_dir, self.testdir)
        self.project.set_property("dir_target", "target")
        self.project.set_property("dir_source_main_python", "src/main/python")
        self.project.set_property("dir_source_main_scripts", "src/main/scripts")
        self.project.set_property("run_unit_tests_propagate_stdout", True)
        self.project.set_property("run_unit_tests_propagate_stderr", True)
        self.dir_target = os.path.join(self.testdir, "target", emr_tasks._EMR_PACKAGE_DIR + "-" + self.project.version)
        self.zipfile = os.path.join(self.dir_target, "palp.zip")

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @mock.patch("pybuilder_emr_plugin.emr_tasks.prepare_dependencies_dir")
    def test_emr_package_assembles_zipfile_correctly(self, prepare_dependencies_dir_mock):
        emr_package(self.project, mock.MagicMock(Logger))
        zf = zipfile.ZipFile(self.zipfile)
        expected = sorted(["test_dependency_module.py",
                           "test_dependency_package/__init__.py",
                           "test_package_directory/__init__.py",
                           "test_package_directory/package_file.py",
                           "test_module_file.py",
                           "resources.txt",
                           "resources_subfolder/sub_resources.txt",
                           "VERSION"])
        self.assertEqual(sorted(zf.namelist()), expected, "zipfile")
        scripts_dir = self.project.expand_path("$dir_source_main_scripts")
        for file in ["bash-script.sh", "python-script.py"]:
            self.assertTrue(filecmp.cmp(os.path.join(scripts_dir, file),
                                        os.path.join(self.dir_target, file)), "missing " + file)


class TestsWithS3(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="palp-")
        self.project = Project(basedir=self.tempdir, name="palp", version="123")
        self.project.set_property("dir_target", "target")
        self.bucket_name = "palp-lambda-zips"
        self.project.set_property(emr_tasks.PROPERTY_S3_FILE_ACCESS_CONTROL, "bucket-owner-full-control")
        self.project.set_property(emr_tasks.PROPERTY_S3_BUCKET_NAME, self.bucket_name)
        self.project.set_property(emr_tasks.PROPERTY_S3_BUCKET_PREFIX, "")
        self.project.set_property(emr_tasks.PROPERTY_S3_RELEASE_PREFIX, "release")
        self.dir_target = os.path.join(self.tempdir, "target", emr_tasks._EMR_PACKAGE_DIR + "-" + self.project.version)
        os.makedirs(self.dir_target)
        for file in ["palp.zip", "bash-script.sh", "python-script.py"]:
            self.filepath = os.path.join(self.dir_target, file)
            self.test_data = b"testdata"
            with open(self.filepath, "wb") as fp:
                fp.write(self.test_data)
        self.my_mock_s3 = mock_s3()
        self.my_mock_s3.start()
        self.s3 = boto3.resource("s3")
        self.s3.create_bucket(Bucket=self.bucket_name)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        self.my_mock_s3.stop()


class UploadToS3Test(TestsWithS3):
    def test_if_file_was_uploaded_to_s3(self):
        emr_upload_to_s3(self.project, mock.MagicMock(Logger))
        s3_object_list = [o for o in self.s3.Bucket("palp-lambda-zips").objects.all()]
        self.assertEqual(s3_object_list[0].bucket_name, "palp-lambda-zips")
        self.assertEqual(s3_object_list[0].key, "v123/bash-script.sh")
        self.assertEqual(s3_object_list[1].bucket_name, "palp-lambda-zips")
        self.assertEqual(s3_object_list[1].key, "v123/palp.zip")
        self.assertEqual(s3_object_list[2].bucket_name, "palp-lambda-zips")
        self.assertEqual(s3_object_list[2].key, "v123/python-script.py")

    def test_if_file_was_uploaded_to_s3_with_bucket_prefix(self):
        self.project.set_property(emr_tasks.PROPERTY_S3_BUCKET_PREFIX, "palp/")
        emr_upload_to_s3(self.project, mock.MagicMock(Logger))
        s3_object_list = [o for o in self.s3.Bucket("palp-lambda-zips").objects.all()]
        self.assertEqual(s3_object_list[0].bucket_name, "palp-lambda-zips")
        self.assertEqual(s3_object_list[0].key, "palp/v123/bash-script.sh")
        self.assertEqual(s3_object_list[1].bucket_name, "palp-lambda-zips")
        self.assertEqual(s3_object_list[1].key, "palp/v123/palp.zip")
        self.assertEqual(s3_object_list[2].bucket_name, "palp-lambda-zips")
        self.assertEqual(s3_object_list[2].key, "palp/v123/python-script.py")

    def test_upload_fails_with_invalid_acl_value(self):
        self.project.set_property(emr_tasks.PROPERTY_S3_FILE_ACCESS_CONTROL, "no_such_value")
        self.assertRaises(BuildFailedException, emr_upload_to_s3, self.project, mock.MagicMock(Logger))

    def test_upload_fails_with_invalid_sse_value(self):
        self.project.set_property(emr_tasks.PROPERTY_S3_SERVER_SIDE_ENCRYPTION, "no_such_value")
        self.assertRaises(BuildFailedException, emr_upload_to_s3, self.project, mock.MagicMock(Logger))

    @mock_s3
    def test_handle_failure_if_no_such_bucket(self):
        pass


class ReleaseTest(TestsWithS3):
    def test_release_successful(self):
        emr_upload_to_s3(self.project, mock.MagicMock(Logger))
        emr_release(self.project, mock.MagicMock(Logger))
        s3_keys = [o.key for o in self.s3.Bucket(self.bucket_name).objects.all()]
        pprint(s3_keys)
        for file in ["palp.zip", "bash-script.sh", "python-script.py"]:
            release_keyname = "{0}{1}/{2}".format(self.project.get_property(emr_tasks.PROPERTY_S3_BUCKET_PREFIX),
                                                  self.project.get_property(emr_tasks.PROPERTY_S3_RELEASE_PREFIX),
                                                  file)
            self.assertTrue(release_keyname in s3_keys, "file: " + release_keyname)
            s3_grants = self.s3.Object(bucket_name=self.bucket_name, key=release_keyname).Acl().grants
            self.assertDictContainsSubset({"Permission": "FULL_CONTROL"}, s3_grants[0],
                                          "Default ACL of FULL_CONTROL not found!")

    def test_release_successful_with_bucket_prefix(self):
        self.project.set_property("bucket_prefix", "palp/")
        emr_upload_to_s3(self.project, mock.MagicMock(Logger))
        emr_release(self.project, mock.MagicMock(Logger))
        s3_keys = [o.key for o in self.s3.Bucket(self.bucket_name).objects.all()]
        pprint(s3_keys)
        for file in ["palp.zip", "bash-script.sh", "python-script.py"]:
            release_keyname = "{0}{1}/{2}".format(self.project.get_property(emr_tasks.PROPERTY_S3_BUCKET_PREFIX),
                                                  self.project.get_property(emr_tasks.PROPERTY_S3_RELEASE_PREFIX),
                                                  file)
            self.assertTrue(release_keyname in s3_keys, "file: " + release_keyname)
            s3_grants = self.s3.Object(bucket_name=self.bucket_name, key=release_keyname).Acl().grants
            self.assertDictContainsSubset({"Permission": "FULL_CONTROL"}, s3_grants[0],
                                          "Default ACL of FULL_CONTROL not found!")


class TestPrepareDependenciesDir(TestCase):
    """Testcases for prepare_dependencies_dir()"""

    def setUp(self):
        self.patch_popen = mock.patch("pybuilder_emr_plugin.emr_tasks.subprocess.Popen")
        self.mock_popen = self.patch_popen.start()
        self.mock_process = mock.Mock()
        self.mock_process.returncode = 0
        self.mock_popen.return_value = self.mock_process
        self.input_project = Project(".")
        self.mock_logger = mock.Mock()

    def tearDown(self):
        self.patch_popen.stop()

    def test_prepare_dependencies_no_excludes(self):
        """Test prepare_dependencies_dir() w/o excludes."""
        for dependency in ["a", "b", "c"]:
            self.input_project.depends_on(dependency)
        prepare_dependencies_dir(
            self.mock_logger, self.input_project, "targetdir")
        self.assertEqual(
            list(self.mock_popen.call_args_list), [
                mock.call(
                    ["pip", "install", "--target", "targetdir", "a"],
                    stdout=subprocess.PIPE),
                mock.call(
                    ["pip", "install", "--target", "targetdir", "b"],
                    stdout=subprocess.PIPE),
                mock.call(
                    ["pip", "install", "--target", "targetdir", "c"],
                    stdout=subprocess.PIPE)])
        self.assertEqual(self.mock_popen.return_value.communicate.call_count, 3)
        self.assertNotEqual(self.mock_popen.return_value.communicate.call_count, 1)

    def test_prepare_dependencies_with_excludes(self):
        """Test prepare_dependencies_dir() w/ excludes."""
        for dependency in ["a", "b", "c", "d", "e"]:
            self.input_project.depends_on(dependency)
        prepare_dependencies_dir(self.mock_logger, self.input_project, "targetdir", excludes=["b", "e", "a"])
        self.assertEqual(
            list(self.mock_popen.call_args_list), [
                mock.call(
                    ["pip", "install", "--target", "targetdir", "c"],
                    stdout=subprocess.PIPE),
                mock.call(
                    ["pip", "install", "--target", "targetdir", "d"],
                    stdout=subprocess.PIPE)])
        self.assertEqual(self.mock_popen.return_value.communicate.call_count, 2)
        self.assertNotEqual(self.mock_popen.return_value.communicate.call_count, 1)

    def test_prepare_dependencies_with_custom_index_url(self):
        self.input_project.depends_on("a")
        self.input_project.set_property("install_dependencies_index_url", "http://example.domain")
        prepare_dependencies_dir(self.mock_logger, self.input_project, "targetdir")
        self.assertEqual(
            list(self.mock_popen.call_args_list),
            [
                mock.call(
                    ["pip", "install", "--target", "targetdir", "--index-url",
                     "http://example.domain", "a"],
                    stdout=subprocess.PIPE),
            ])

    def test_prepare_dependencies_reports_errors(self):
        self.input_project.depends_on("a")
        self.mock_process.returncode = 1
        self.assertRaises(Exception, prepare_dependencies_dir, self.mock_logger, self.input_project, "targetdir")


if __name__ == "__main__":
    unittest.main()
