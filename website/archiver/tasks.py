import requests
import json

import celery
from celery.utils.log import get_task_logger
from modularodm import Q

from framework.tasks import app as celery_app
from framework.tasks.utils import logged
from framework.exceptions import HTTPError

from website.archiver import (
    ARCHIVER_SUCCESS,
    ARCHIVER_FAILURE,
    ARCHIVER_SIZE_EXCEEDED,
    ARCHIVER_NETWORK_ERROR,
    ARCHIVER_FILE_NOT_FOUND,
    ARCHIVER_UNCAUGHT_ERROR,
    NO_ARCHIVE_LIMIT,
    AggregateStatResult,
)
from website.archiver import utils
from website.archiver.model import ArchiveJob
from website.archiver import signals as archiver_signals

from website.project import signals as project_signals
from website.project.model import Node, MetaSchema
from website import settings
from website.app import init_addons, do_set_backends


def create_app_context():
    try:
        init_addons(settings)
        do_set_backends(settings)
    except AssertionError:  # ignore AssertionErrors
        pass


logger = get_task_logger(__name__)


class ArchiverSizeExceeded(Exception):

    def __init__(self, result, *args, **kwargs):
        super(ArchiverSizeExceeded, self).__init__(*args, **kwargs)
        self.result = result


class ArchiverStateError(Exception):

    def __init__(self, info, *args, **kwargs):
        super(ArchiverStateError, self).__init__(*args, **kwargs)
        self.info = info


class ArchivedFileNotFound(Exception):

    def __init__(self, file_name, node_id, *args, **kwargs):
        super(ArchivedFileNotFound, self).__init__(*args, **kwargs)
        self.file_name = file_name
        self.node_id = node_id


class ArchiverTask(celery.Task):
    abstract = True
    max_retries = 0

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job = ArchiveJob.load(kwargs.get('job_pk'))
        import pydevd
        pydevd.settrace('localhost', port=54735, stdoutToServer=True, stderrToServer=True)
        if not job:
            raise ArchiverStateError({
                'exception': exc,
                'args': args,
                'kwargs': kwargs,
                'einfo': einfo,
            })
        if job.status == ARCHIVER_FAILURE:
            # already captured
            return
        src, dst, user = job.info()
        errors = []
        if isinstance(exc, ArchiverSizeExceeded):
            dst.archive_status = ARCHIVER_SIZE_EXCEEDED
            errors = exc.result
        elif isinstance(exc, HTTPError):
            dst.archive_status = ARCHIVER_NETWORK_ERROR
            errors = dst.archive_job.target_info()
        elif isinstance(exc, ArchivedFileNotFound):
            dst.archive_status = ARCHIVER_FILE_NOT_FOUND
            errors = {
                'file_name': exc.file_name,
                'node': Node.load(exc.node_id)
            }
        else:
            dst.archive_status = ARCHIVER_UNCAUGHT_ERROR
            errors = [einfo]
        dst.save()
        archiver_signals.archive_fail.send(dst, errors=errors)


@celery_app.task(base=ArchiverTask, name="archiver.stat_addon")
@logged('stat_addon')
def stat_addon(addon_short_name, job_pk):
    """Collect metadata about the file tree of a given addon

    :param addon_short_name: AddonConfig.short_name of the addon to be examined
    :param job_pk: primary key of archive_job
    :return: AggregateStatResult containing file tree metadata
    """
    # Dataverse reqires special handling for draft and
    # published content
    addon_name = addon_short_name
    version = None
    if 'dataverse' in addon_short_name:
        addon_name = 'dataverse'
        version = 'latest' if addon_short_name.split('-')[-1] == 'draft' else 'latest-published'
    create_app_context()
    job = ArchiveJob.load(job_pk)
    src, dst, user = job.info()
    src_addon = src.get_addon(addon_name)
    try:
        file_tree = src_addon._get_file_tree(user=user, version=version)
    except HTTPError as e:
        dst.archive_job.update_target(
            addon_short_name,
            ARCHIVER_NETWORK_ERROR,
            errors=[e.data['error']],
        )
        raise
    result = AggregateStatResult(
        src_addon._id,
        addon_short_name,
        targets=[utils.aggregate_file_tree_metadata(addon_short_name, file_tree, user)],
    )
    return result


@celery_app.task(base=ArchiverTask, name="archiver.make_copy_request")
@logged('make_copy_request')
def make_copy_request(job_pk, url, data):
    """Make the copy request to the WaterBulter API and handle
    successful and failed responses

    :param job_pk: primary key of ArchiveJob
    :param url: URL to send request to
    :param data: <dict> of setting to send in POST to WaterBulter API
    :return: None
    """
    create_app_context()
    job = ArchiveJob.load(job_pk)
    src, dst, user = job.info()
    provider = data['source']['provider']
    logger.info("Sending copy request for addon: {0} on node: {1}".format(provider, dst._id))
    requests.post(url, data=json.dumps(data))


def make_waterbutler_payload(src, dst, addon_short_name, rename, cookie, revision=None):
    ret = {
        'source': {
            'cookie': cookie,
            'nid': src._id,
            'provider': addon_short_name,
            'path': '/',
        },
        'destination': {
            'cookie': cookie,
            'nid': dst._id,
            'provider': settings.ARCHIVE_PROVIDER,
            'path': '/',
        },
        'rename': rename.replace('/', '-')
    }
    if revision:
        ret['source']['revision'] = revision
    return ret


@celery_app.task(base=ArchiverTask, name="archiver.archive_addon")
@logged('archive_addon')
def archive_addon(addon_short_name, job_pk, stat_result):
    """Archive the contents of an addon by making a copy request to the
    WaterBulter API

    :param addon_short_name: AddonConfig.short_name of the addon to be archived
    :param job_pk: primary key of ArchiveJob
    :return: None
    """
    # Dataverse requires special handling for draft
    # and published content
    addon_name = addon_short_name
    if 'dataverse' in addon_short_name:
        addon_name = 'dataverse'
    create_app_context()
    job = ArchiveJob.load(job_pk)
    src, dst, user = job.info()
    logger.info("Archiving addon: {0} on node: {1}".format(addon_short_name, src._id))
    src_provider = src.get_addon(addon_name)
    folder_name = src_provider.archive_folder_name
    cookie = user.get_or_create_cookie()
    copy_url = settings.WATERBUTLER_URL + '/ops/copy'
    if addon_name == 'dataverse':
        # The dataverse API will not differentiate between published and draft files
        # unless expcicitly asked. We need to create seperate folders for published and
        # draft in the resulting archive.
        #
        # Additionally trying to run the archive without this distinction creates a race
        # condition that non-deterministically caused archive jobs to fail.
        data = make_waterbutler_payload(src, dst, addon_name, '{0} (published)'.format(folder_name), cookie, revision='latest-published')
        make_copy_request.delay(job_pk=job_pk, url=copy_url, data=data)
        data = make_waterbutler_payload(src, dst, addon_name, '{0} (draft)'.format(folder_name), cookie, revision='latest')
        make_copy_request.delay(job_pk=job_pk, url=copy_url, data=data)
    else:
        data = make_waterbutler_payload(src, dst, addon_name, folder_name, cookie)
        make_copy_request.delay(job_pk=job_pk, url=copy_url, data=data)


@celery_app.task(base=ArchiverTask, name="archiver.archive_node")
@logged('archive_node')
def archive_node(stat_results, job_pk):
    """First use the results of #stat_node to check disk usage of the
    initiated registration, then either fail the registration or
    create a celery.group group of subtasks to archive addons

    :param results: results from the #stat_addon subtasks spawned in #stat_node
    :param job_pk: primary key of ArchiveJob
    :return: None
    """
    create_app_context()
    job = ArchiveJob.load(job_pk)
    src, dst, user = job.info()
    logger.info("Archiving node: {0}".format(src._id))

    if not isinstance(stat_results, list):
        stat_results = [stat_results]
    stat_result = AggregateStatResult(
        dst._id,
        dst.title,
        targets=stat_results
    )
    if (NO_ARCHIVE_LIMIT not in job.initiator.system_tags) and (stat_result.disk_usage > settings.MAX_ARCHIVE_SIZE):
        raise ArchiverSizeExceeded(result=stat_result)
    else:
        if not stat_result.targets:
            job.status = ARCHIVER_SUCCESS
            job.save()
        for result in stat_result.targets:
            if not result.num_files:
                job.update_target(result.target_name, ARCHIVER_SUCCESS)
            else:
                archive_addon.delay(
                    addon_short_name=result.target_name,
                    job_pk=job_pk,
                    stat_result=result,
                )
        project_signals.archive_callback.send(dst)


def archive(job_pk):
    """Starts a celery.chord that runs stat_addon for each
    complete addon attached to the Node, then runs
    #archive_node with the result

    :param job_pk: primary key of ArchiveJob
    :return: None
    """
    create_app_context()
    job = ArchiveJob.load(job_pk)
    src, dst, user = job.info()
    logger = get_task_logger(__name__)
    logger.info("Received archive task for Node: {0} into Node: {1}".format(src._id, dst._id))
    return celery.chain(
        [
            celery.group(
                stat_addon.si(
                    addon_short_name=target.name,
                    job_pk=job_pk,
                )
                for target in job.target_addons
            ),
            archive_node.s(
                job_pk=job_pk
            )
        ]
    )

def find_registration_file(value, node):
    orig_sha256 = value['extra']['sha256']
    orig_name = value['extra']['selectedFileName']
    orig_node = value['extra']['nodeId']
    file_map = utils.get_file_map(node)
    for sha256, value, node_id in file_map:
        registered_from_id = Node.load(node_id).registered_from._id
        if sha256 == orig_sha256 and registered_from_id == orig_node and orig_name == value['name']:
            return value, node_id
    raise ArchivedFileNotFound(file_name=orig_name, node_id=orig_node)

VIEW_FILE_URL_TEMPLATE = '/project/{node_id}/files/osfstorage/{path}/'

@celery_app.task(base=ArchiverTask, name="archiver.archive_success")
@logged('archive_success')
def archive_success(dst_pk, job_pk):
    """Archiver's final callback. For the time being the use case for this task
    is to rewrite references to files selected in a registration schema (the Prereg
    Challenge being the first to expose this feature). The created references point
    to files on the registered_from Node (needed for previewing schema data), and
    must be re-associated with the corresponding files in the newly created registration.

    :param str dst_pk: primary key of registration Node

    note:: At first glance this task makes redundant calls to utils.get_file_map (which
    returns a generator yielding  (<sha256>, <file_metadata>) pairs) on the dst Node. Two
    notes about utils.get_file_map: 1) this function memoizes previous results to reduce
    overhead and 2) this function returns a generator that lazily fetches the file metadata
    of child Nodes (it is possible for a selected file to belong to a child Node) using a
    non-recursive DFS. Combined this allows for a relatively effient implementation with
    seemingly redundant calls.
    """
    create_app_context()
    dst = Node.load(dst_pk)
    # The filePicker extension addded with the Prereg Challenge registration schema
    # allows users to select files in OSFStorage as their response to some schema
    # questions. These files are references to files on the unregistered Node, and
    # consequently we must migrate those file paths after archiver has run. Using
    # sha256 hashes is a convenient way to identify files post-archival.
    prereg_schema = MetaSchema.find_one(
        Q('name', 'eq', 'Prereg Challenge') &
        Q('schema_version', 'eq', 2)
    )
    if prereg_schema in dst.registered_schema:
        prereg_metadata = dst.registered_meta[prereg_schema._id]
        updated_metadata = {}
        for key, question in prereg_metadata.items():
            if isinstance(question['value'], dict):
                for subkey, subvalue in question['value'].items():
                    registration_file = None
                    if subvalue.get('extra', {}).get('sha256'):
                        registration_file, node_id = find_registration_file(subvalue, dst)
                        if not registration_file:
                            subvalue['extra'].update({
                                'selectedFileName': 'File not found',
                                'viewUrl': ''
                            })
                        else:
                            subvalue['extra'].update({
                                'viewUrl': VIEW_FILE_URL_TEMPLATE.format(node_id=node_id, path=registration_file['path'].lstrip('/'))
                            })
                    question['value'][subkey] = subvalue
            else:
                if question.get('extra', {}).get('sha256'):
                    registration_file, node_id = find_registration_file(question, dst)
                    question['extra'].update({
                        'viewUrl': VIEW_FILE_URL_TEMPLATE.format(node_id=node_id, path=registration_file['path'].lstrip('/'))
                    })
            updated_metadata[key] = question
        prereg_metadata.update(updated_metadata)
        dst.registered_meta[prereg_schema._id] = prereg_metadata
        dst.save()

    job = ArchiveJob.load(job_pk)
    job.sent = True
    job.save()
    dst.sanction.ask(dst.active_contributors())
