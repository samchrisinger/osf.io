from __future__ import unicode_literals

import os
import bson
import logging

import furl

import pymongo
from modularodm import fields, Q
from modularodm import exceptions as modm_errors
from modularodm.storage.base import KeyExistsException
from dateutil.parser import parse as parse_date

from framework.auth import Auth
from framework.mongo import StoredObject
from framework.mongo.utils import unique_on
from framework.analytics import get_basic_counters

from website.models import NodeLog
from website.addons.base import AddonNodeSettingsBase, GuidFile

from website.addons.osfstorage import logs
from website.addons.osfstorage import errors
from website.addons.osfstorage import settings


logger = logging.getLogger(__name__)

oid_primary_key = fields.StringField(
    primary=True,
    default=lambda: str(bson.ObjectId())
)


def copy_file_tree(tree, node_settings):
    """Recursively copy file tree.

    :param OsfStorageFileTree tree: Tree to copy
    :param node_settings: Root node settings record
    """
    children = [copy_files(child, node_settings) for child in tree.children]
    clone = tree.clone()
    clone.children = children
    clone.node_settings = node_settings
    clone.save()
    return clone


def copy_file_record(record, node_settings):
    """Copy versions of an `OsfStorageFileRecord`. Versions are copied
    by primary key and will not be duplicated in the database.

    :param OsfStorageFileRecord record: Record to copy
    :param node_settings: Root node settings record
    """
    clone = record.clone()
    clone.versions = record.versions
    clone.node_settings = node_settings
    clone.save()
    return clone


def copy_files(files, node_settings):
    if isinstance(files, OsfStorageFileTree):
        return copy_file_tree(files, node_settings)
    if isinstance(files, OsfStorageFileRecord):
        return copy_file_record(files, node_settings)
    raise TypeError('Input must be `OsfStorageFileTree` or `OsfStorageFileRecord`')


class OsfStorageNodeSettings(AddonNodeSettingsBase):

    file_tree = fields.ForeignField('OsfStorageFileTree')
    root_node = fields.ForeignField('OsfStorageFileNode')

    def on_add(self):
        if self.root_node:
            return

        self.save()
        root = OsfStorageFileNode(name='', kind='folder', node_settings=self)
        root.save()
        self.root_node = root
        self.save()

    @property
    def has_auth(self):
        return True

    @property
    def complete(self):
        return True

    def find_or_create_file_guid(self, path):
        return OsfStorageGuidFile.get_or_create(node=self.owner, path=path.lstrip('/'))

    def copy_contents_to(self, dest):
        """Copy file tree and contents to destination. Note: destination must be
        saved before copying so that copied items can refer to it.

        :param OsfStorageNodeSettings dest: Destination settings object
        """
        dest.save()
        if self.file_tree:
            dest.file_tree = copy_file_tree(self.file_tree, dest)
            dest.save()

    def after_fork(self, node, fork, user, save=True):
        clone, message = super(OsfStorageNodeSettings, self).after_fork(
            node=node, fork=fork, user=user, save=False
        )
        self.copy_contents_to(clone)
        return clone, message

    def after_register(self, node, registration, user, save=True):
        clone = self.clone()
        clone.owner = registration
        self.copy_contents_to(clone)
        if save:
            clone.save()
        return clone, None

    def serialize_waterbutler_settings(self):
        ret = {
            'callback': self.owner.api_url_for(
                'osf_storage_update_metadata_hook',
                _absolute=True,
                _offload=True
            ),
            'metadata': self.owner.api_url_for(
                'osf_storage_get_metadata_hook',
                _absolute=True,
                _offload=True
            ),
            'revisions': self.owner.api_url_for(
                'osf_storage_get_revisions',
                _absolute=True,
                _offload=True
            ),
        }
        ret.update(settings.WATERBUTLER_SETTINGS)
        return ret

    def serialize_waterbutler_credentials(self):
        return settings.WATERBUTLER_CREDENTIALS

    def create_waterbutler_log(self, auth, action, metadata):
        pass


@unique_on(['path', 'node_settings'])
class BaseFileObject(StoredObject):

    path = fields.StringField(required=True, index=True)
    node_settings = fields.ForeignField(
        'OsfStorageNodeSettings',
        required=True,
        index=True,
    )

    _meta = {
        'abstract': True,
    }

    @property
    def name(self):
        _, value = os.path.split(self.path)
        return value

    @property
    def extension(self):
        _, value = os.path.splitext(self.path)
        return value

    @property
    def node(self):
        return self.node_settings.owner

    @classmethod
    def parent_class(cls):
        raise NotImplementedError

    @classmethod
    def find_by_path(cls, path, node_settings):
        """Find a record by path and root settings record.

        :param str path: Path to file or directory
        :param node_settings: Root node settings record
        """
        try:
            obj = cls.find_one(
                Q('path', 'eq', path.rstrip('/')) &
                Q('node_settings', 'eq', node_settings._id)
            )
            return obj
        except modm_errors.NoResultsFound:
            return None

    @classmethod
    def get_or_create(cls, path, node_settings):
        """Get or create a record by path and root settings record.

        :param str path: Path to file or directory
        :param node_settings: Root node settings record
        :returns: Tuple of (record, created)
        """
        path = path.rstrip('/')

        try:
            obj = cls(path=path, node_settings=node_settings)
            obj.save()
        except KeyExistsException:
            obj = cls.find_by_path(path, node_settings)
            assert obj is not None
            return obj, False

        # Ensure all intermediate paths
        if path:
            parent_path, _ = os.path.split(path)
            parent_class = cls.parent_class()
            parent_obj, _ = parent_class.get_or_create(parent_path, node_settings)
            parent_obj.append_child(obj)
        else:
            node_settings.file_tree = obj
            node_settings.save()

        return obj, True

    def get_download_count(self, version=None):
        """Return download count or `None` if this is not a file object (e.g. a
        folder).
        """
        return None

    def __repr__(self):
        return '<{}(path={!r}, node_settings={!r})>'.format(
            self.__class__.__name__,
            self.path,
            self.node_settings._id,
        )


class OsfStorageFileTree(BaseFileObject):

    _id = oid_primary_key
    children = fields.AbstractForeignField(list=True)

    @classmethod
    def parent_class(cls):
        return OsfStorageFileTree

    def append_child(self, child):
        """Appending children through ODM introduces a race condition such that
        concurrent requests can overwrite previously added items; use the native
        `addToSet` operation instead.
        """
        collection = self._storage[0].store
        collection.update(
            {'_id': self._id},
            {'$addToSet': {'children': (child._id, child._name)}}
        )
        # Updating MongoDB directly means the cache is wrong; reload manually
        self.reload()


class OsfStorageFileRecord(BaseFileObject):

    _id = oid_primary_key
    is_deleted = fields.BooleanField(default=False)
    versions = fields.ForeignField('OsfStorageFileVersion', list=True)

    @classmethod
    def parent_class(cls):
        return OsfStorageFileTree

    def get_version(self, index=-1, required=False):
        try:
            return self.versions[index]
        except IndexError:
            if required:
                raise errors.VersionNotFoundError
            return None

    def get_versions(self, page, size=settings.REVISIONS_PAGE_SIZE):
        start = len(self.versions) - (page * size)
        stop = max(0, start - size)
        indices = range(start, stop, -1)
        versions = [self.versions[idx - 1] for idx in indices]
        more = stop > 0
        return indices, versions, more

    def create_version(self, creator, location, metadata=None):
        latest_version = self.get_version()
        version = OsfStorageFileVersion(creator=creator, location=location)

        if latest_version and latest_version.is_duplicate(version):
            if self.is_deleted:
                self.undelete(Auth(creator))
            return latest_version

        if metadata:
            version.update_metadata(metadata)

        version.save()
        self.versions.append(version)
        self.is_deleted = False
        self.save()
        self.log(
            Auth(creator),
            NodeLog.FILE_UPDATED if len(self.versions) > 1 else NodeLog.FILE_ADDED,
        )
        return version

    def update_version_metadata(self, location, metadata):
        for version in reversed(self.versions):
            if version.location == location:
                version.update_metadata(metadata)
                return
        raise errors.VersionNotFoundError

    def log(self, auth, action, version=True):
        node_logger = logs.OsfStorageNodeLogger(
            auth=auth,
            node=self.node,
            path=self.path,
        )
        extra = {'version': len(self.versions)} if version else None
        node_logger.log(action, extra=extra, save=True)

    def delete(self, auth, log=True):
        if self.is_deleted:
            raise errors.DeleteError
        self.is_deleted = True
        self.save()
        if log:
            self.log(auth, NodeLog.FILE_REMOVED, version=False)

    def undelete(self, auth, log=True):
        if not self.is_deleted:
            raise errors.UndeleteError
        self.is_deleted = False
        self.save()
        if log:
            self.log(auth, NodeLog.FILE_ADDED)

    def get_download_count(self, version=None):
        """
        :param int version: Optional one-based version index
        """
        parts = ['download', self.node._id, self.path]
        if version is not None:
            parts.append(version)
        page = ':'.join([format(part) for part in parts])
        _, count = get_basic_counters(page)
        return count or 0


LOCATION_KEYS = ['service', settings.WATERBUTLER_RESOURCE, 'object']
def validate_location(value):
    for key in LOCATION_KEYS:
        if key not in value:
            raise modm_errors.ValidationValueError


class OsfStorageFileVersion(StoredObject):

    _id = oid_primary_key
    creator = fields.ForeignField('user', required=True)

    # Date version record was created. This is the date displayed to the user.
    date_created = fields.DateTimeField(auto_now_add=True)

    # Dictionary specifying all information needed to locate file on backend
    # {
    #     'service': 'cloudfiles',  # required
    #     'container': 'osf',       # required
    #     'object': '20c53b',       # required
    #     'worker_url': '127.0.0.1',
    #     'worker_host': 'upload-service-1',
    # }
    location = fields.DictionaryField(validate=validate_location)

    # Dictionary containing raw metadata from upload service response
    # {
    #     'size': 1024,                            # required
    #     'content_type': 'text/plain',            # required
    #     'date_modified': '2014-11-07T20:24:15',  # required
    #     'md5': 'd077f2',
    # }
    metadata = fields.DictionaryField()

    size = fields.IntegerField()
    content_type = fields.StringField()
    # Date file modified on third-party backend. Not displayed to user, since
    # this date may be earlier than the date of upload if the file already
    # exists on the backend
    date_modified = fields.DateTimeField()

    @property
    def location_hash(self):
        return self.location['object']

    def is_duplicate(self, other):
        return self.location_hash == other.location_hash

    def update_metadata(self, metadata):
        self.metadata.update(metadata)
        self.content_type = self.metadata.get('contentType', None)
        try:
            self.size = self.metadata['size']
            self.date_modified = parse_date(self.metadata['modified'], ignoretz=True)
        except KeyError as err:
            raise errors.MissingFieldError(str(err))
        self.save()


class OsfStorageGuidFile(GuidFile):
    __indices__ = [
        {
            'key_or_list': [
                ('node', pymongo.ASCENDING),
                ('path', pymongo.ASCENDING),
                ('_path', pymongo.ASCENDING),
            ],
            'unique': True,
        }
    ]

    _path = fields.StringField(index=True)
    path = fields.StringField(required=True, index=True)

    @property
    def waterbutler_path(self):
        return '/' + self.path

    @property
    def provider(self):
        return 'osfstorage'

    @property
    def version_identifier(self):
        return 'version'

    @property
    def unique_identifier(self):
        return self._metadata_cache['extra']['version']

    @property
    def file_url(self):
        return os.path.join('osfstorage', 'files', self.path)

    def get_download_path(self, version_idx):
        url = furl.furl('/{0}/'.format(self._id))
        url.args.update({
            'action': 'download',
            'version': version_idx,
            'mode': 'render',
        })
        return url.url

##### STUBBED MODEL REMOVE UPON MERGE @chrisseto #####
@unique_on(['name', 'kind', 'parent', 'node_settings'])
class OsfStorageFileNode(StoredObject):
    _id = fields.StringField(primary=True, default=lambda: str(bson.ObjectId()))

    is_deleted = fields.BooleanField(default=False)
    name = fields.StringField(required=True, index=True)
    kind = fields.StringField(required=True, index=True)
    parent = fields.ForeignField('OsfStorageFileNode', index=True)
    versions = fields.ForeignField('OsfStorageFileVersion', list=True)
    node_settings = fields.ForeignField('OsfStorageNodeSettings', required=True, index=True)

    def materialized_path(self):
        def lineage():
            current = self
            while current:
                yield current
                current = current.parent

        path = os.path.join(*reversed([x.name for x in lineage()]))
        if self.kind == 'folder':
            return '/{}/'.format(path)
        return '/{}'.format(path)

    def append_file(self, name, save=True):
        assert self.kind == 'folder'

        child = OsfStorageFileNode(
            name=name,
            kind='file',
            parent=self,
            node_settings=self.node_settings
        )

        if save:
            child.save()

        return child

    def find_child_by_name(self, name):
        assert self.kind == 'folder'

        return self.__class__.find_one(
            Q('name', 'eq', name) &
            Q('kind', 'eq', 'file') &
            Q('parent', 'eq', self)
        )

    @property
    def path(self):
        return '/{}{}'.format(self._id, '/' if self.kind == 'folder' else '')

    def get_download_count(self, version=None):
        """
        :param int version: Optional one-based version index
        """
        parts = ['download', self.node_settings.owner._id, self._id]
        if version is not None:
            parts.append(version)
        page = ':'.join([format(part) for part in parts])
        _, count = get_basic_counters(page)
        return count or 0
