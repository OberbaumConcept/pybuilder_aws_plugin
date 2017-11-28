#!/usr/bin/env python
# -*- coding: utf-8 -*-

import boto3
from pybuilder.errors import BuildFailedException

permissible_acl_values = [
    "private",
    "public-read",
    "public-read-write",
    "authenticated-read",
    "bucket-owner-read",
    "bucket-owner-full-control",
]
permissible_sse_values = ["aws:kms", "AES256"]


def upload_helper(logger, bucket_name, keyname, data, acl, server_side_encryption=None, sse_kms_keyid=None):
    s3 = boto3.resource("s3")
    logger.info("Uploading to bucket '{0}' key {1}".format(bucket_name, keyname))
    kwargs = {"Key": keyname,
              "Body": data,
              "ACL": acl
              }
    if server_side_encryption:
        kwargs.update({"ServerSideEncryption": server_side_encryption})
    if sse_kms_keyid:
        kwargs.update({"SSEKMSKeyId": sse_kms_keyid})
    logger.debug("using put_object kwargs: {}".format(kwargs))
    s3.Bucket(bucket_name).put_object(**kwargs)


def copy_helper(logger, bucket_name, source_key, destination_key, acl, server_side_encryption=None, sse_kms_keyid=None):
    """Copy S3 source_key to destination_key in bucket_name applying acl"""
    logger.info('Copying in {0} from {1} to {2}'.format(bucket_name, source_key, destination_key))
    client = boto3.client("s3")
    kwargs = {"ACL": acl,
              "Bucket": bucket_name,
              "CopySource": {"Bucket": bucket_name, "Key": source_key},
              "Key": destination_key,
              "MetadataDirective": "COPY"
              }
    if server_side_encryption:
        kwargs.update({"ServerSideEncryption": server_side_encryption})
    if sse_kms_keyid:
        kwargs.update({"SSEKMSKeyId": sse_kms_keyid})
    logger.debug("using copy_object kwargs: {}".format(kwargs))
    client.copy_object(**kwargs)


def check_acl_parameter_validity(property_, acl_value):
    if acl_value not in permissible_acl_values:
        raise BuildFailedException("ACL value: '{0}' not allowed for property: '{1}'".format(acl_value, property_))


def check_sse_parameter_validity(property_, sse_value):
    if sse_value and sse_value not in permissible_sse_values:
        raise BuildFailedException("value: '{0}' not allowed for property: '{1}'".format(sse_value, property_))
