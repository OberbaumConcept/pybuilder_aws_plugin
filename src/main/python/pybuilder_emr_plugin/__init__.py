#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flake8: noqa

from pybuilder.core import init

from .emr_tasks import emr_upload_to_s3, emr_package, emr_release


@init
def initialize_plugin(project):
    """ Setup plugin defaults. """
    project.set_property("emr.file_access_control", "bucket-owner-full-control")
    project.set_property("emr.bucket_prefix", "")
    project.set_property("emr.main-file", "main.py")

