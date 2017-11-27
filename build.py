#!/usr/bin/env python
#   -*- coding: utf-8 -*-
from pybuilder.core import Author, init, use_plugin
from pybuilder.vcs import VCSRevision

use_plugin("python.core")
use_plugin("python.unittest")
use_plugin("python.install_dependencies")
use_plugin("python.flake8")
use_plugin("python.coverage")
use_plugin("python.distutils")
use_plugin("python.pycharm")

name = "pybuilder_emr_plugin"
default_task = "publish"
# we are simple using the numbers git commits as version number
version = VCSRevision().count

summary = "PyBuilder plugin to handle Amazon EMR functionality"
authors = [Author("Janne K. Olesen", "janne.olesen@oberbaum-concept.com"),
           ]
license = "Apache"
url = "https://github.com/OberbaumConcept/pybuilder_emr_plugin.git"


@init
def set_properties(project):
    project.set_property("install_dependencies_upgrade", True)
    project.depends_on("boto3")
    project.depends_on("httpretty")
    project.build_depends_on("unittest2")
    project.build_depends_on("mock")
    project.build_depends_on("moto")
    project.set_property("coverage_break_build", False)
    project.set_property("distutils_classifiers", [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
        "Topic :: System :: Archiving :: Packaging",
        "Topic :: Utilities",
    ])
