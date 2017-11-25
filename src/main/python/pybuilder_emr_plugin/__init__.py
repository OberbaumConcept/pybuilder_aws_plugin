#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flake8: noqa

from pybuilder.core import init

from .emr_tasks import emr_upload_to_s3, emr_package, emr_release


@init
def initialize_plugin(project):
    """ Setup plugin defaults. """
    project.set_property(emr_tasks.PROPERTY_S3_FILE_ACCESS_CONTROL, "bucket-owner-full-control")
    project.set_property(emr_tasks.PROPERTY_S3_RELEASE_PREFIX, emr_tasks.RELEASE_PREFIX_DEFAULT)
    project.set_property(emr_tasks.PROPERTY_S3_BUCKET_PREFIX, "")
