.. image:: https://travis-ci.org/OberbaumConcept/pybuilder_emr_plugin.svg?branch=master
    :target: https://travis-ci.org/OberbaumConcept/pybuilder_emr_plugin
.. image:: https://coveralls.io/repos/github/OberbaumConcept/pybuilder_emr_plugin/badge.svg?branch=master
    :target: https://coveralls.io/github/OberbaumConcept/pybuilder_emr_plugin?branch=master
.. image:: https://badge.fury.io/py/pybuilder-emr-plugin.svg
    :target: https://badge.fury.io/py/pybuilder-emr-plugin

====================
pybuilder_emr_plugin
====================

PyBuilder plugin to simplify building projects for Amazon EMR. The
following use cases are supported:

* Packaging Python code for EMR_ and uploading the result to S3_.

This project is based heavily on pybuilder_aws_plugin_ by Immobilienscout. It uses Boto3_ for s3 uploads.

.. _EMR: http://aws.amazon.com/documentation/emr/
.. _S3: http://aws.amazon.com/documentation/s3/
.. _pybuilder_aws_plugin: https://github.com/ImmobilienScout24/pybuilder_aws_plugin
.. _Boto3: https://github.com/boto/boto3

Usage
=====================

Add the following plugin dependency to your ``build.py`` (will install directly
from PyPi and require the install_dependencies plugin):

.. code:: python

    use_plugin('python.install_dependencies')
    use_plugin('pypi:pybuilder_emr_plugin')

After this you have the following additional tasks, which are explained below:

* ``emr_package``
* ``emr_upload_to_s3``
* ``emr_release``

@Task: emr_package
--------------------------
This task assembles the Zip-file (a.k.a. the *emr-zip*) which will be
uploaded to S3_ with the task ``emr_upload_to_s3``. The files are assembled using
a directory *$target/emr-release*. This task consists of the following steps:

Add all dependencies
~~~~~~~~~~~~~~~~~~~~~~~~
Install every entry in ``build.py``, that is specified by using
``project.depends_on()``, into a temporary directory via ``pip install -t``.
These will be included in the resulting emr-zip. Set the project property
``install_dependencies_index_url`` to use a custom index url (e.g. an internal
`PYPI server`__).

**Note:** This excludes `boto`, `boto3` and `pyspark` as they are included in `AWS EMR dependencies`__ by default

.. __: http://doc.devpi.net/latest/

Add all own modules
~~~~~~~~~~~~~~~~~~~~~~~
All modules which are found in ``src/main/python/`` are copied directly into
the lambda-zip.

Add all resources
~~~~~~~~~~~~~~~~~~~~~~~
All files which are found in ``src/main/resources/`` are copied directly into
the lambda-zip.

Copy all script files
~~~~~~~~~~~~~~~~~~~~~~~~
The content of the scripts folder (``src/main/scripts``) in a PyBuilder project
is normally intended to be placed in ``/usr/bin``. This plugin assumes this
directory contains scripts which are used as *main.py* argument to *spark-submit*,
therefore they are copied to the release directory and will be copied
to S3_ with the task ``emr_upload_to_s3``. They are not part of the *emr-zip*

Pack everything into the Zip-file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All these files are packed as a Zip-file, except the script files

@Task: emr_upload_to_s3
-----------------------
This task uploads the generated zip and all script files to an S3_ bucket. The bucket name is set in
``build.py``:

.. code:: python

    project.set_property('emr.s3.bucket-name', 'my_emr_bucket')

The default acl for zips to be uploaded is ``bucket-owner-full-control``. But
if you need another acl you can overwrite this as follows in ``build.py``:

.. code:: python

    project.set_property('emr.s3.file-access-control', '<acl>')

.. _acl:

Possible acl values are:

* ``private``
* ``public-read``
* ``public-read-write``
* ``authenticated-read``
* ``bucket-owner-read``
* ``bucket-owner-full-control``

For server side encryption use the properies

.. code:: python

    project.set_property('emr.s3.sse-kms-keyid', '<keyAlias>')
    project.set_property('emr.s3.server-side-encryption', '<sse>')

.. _sse:

Possible sse values are:
* ``aws:kms``
* ``AES256``

Furthermore, the plugin assumes that you already have a shell with enabled AWS
access (exported keys or .boto or ...).

The uploaded files will be placed in a directory with the version number like:
``v123/projectname.zip`` and ``v123/main.py``.

Use the property ``bucket_prefix`` to add a prefix to the uploaded
files. For example:

.. code:: python

   project.set_property('emr.s3.bucket-prefix', 'my_emr/')

This will upload the zip-file to the following key:
``my_emr/v123/projectname.zip``

@Task: emr_release
-----------------------------------

These tasks copy the emr-zip and script files from the versioned path
to version independant path named ``latest``. For Example:

- ``my_emr/v123/my-project.zip`` is copied to ``my_emr/latest/my-project.zip``

This provides a simple release mechanism that follows the "latest greatest"
principle. Users can rely on the files under ``latest`` to be the latest tested
version.

Use the property ``emr.s3.release-prefix`` to modify your release prefix. For example:

.. code:: python

   project.set_property('emr.s3.release-prefix', 'LATEST/')

Licence
=======

Copyright 2017, Oberbaum Concept UG

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
