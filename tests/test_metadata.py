# -*- coding: utf-8 -*-
'''Unit tests for models and their factories.'''
import unittest
from nose.tools import *  # PEP8 asserts

from framework.forms.utils import prepare_payload
from website.project.model import MetaSchema
from website.project.model import ensure_schemas
from website.project.metadata.schemas import OSF_META_SCHEMAS

from tests.base import DbTestCase


class TestMetaData(DbTestCase):

    def test_ensure_schemas(self):

        # Should be zero MetaSchema records to begin with
        assert_equal(
            MetaSchema.find().count(),
            0
        )

        ensure_schemas()

        assert_equal(
            MetaSchema.find().count(),
            len(OSF_META_SCHEMAS)
        )

    def test_sanitize_clean(self):
        sanitized = prepare_payload({'foo': 'bar&baz'})
        assert_equal(sanitized['foo'], 'bar%26baz')

    def test_sanitize_clean_list(self):
        sanitized = prepare_payload({'foo': ['bar', 'baz&bob']})
        assert_equal(sanitized['foo'][1], 'baz%26bob')

if __name__ == '__main__':
    unittest.main()
