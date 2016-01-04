# -*- coding: utf-8 -*-
from modularodm import Q
from modularodm.exceptions import NoResultsFound
from rest_framework.exceptions import NotFound
from rest_framework.reverse import reverse
import furl

from website import util as website_util  # noqa
from website import settings as website_settings
from framework.auth import Auth, User
from api.base.exceptions import Gone

# These values are copied from rest_framework.fields.BooleanField
# BooleanField cannot be imported here without raising an
# ImproperlyConfigured error
TRUTHY = set(('t', 'T', 'true', 'True', 'TRUE', '1', 1, True))
FALSY = set(('f', 'F', 'false', 'False', 'FALSE', '0', 0, 0.0, False))

UPDATE_METHODS = ['PUT', 'PATCH']

def is_bulk_request(request):
    """
    Returns True if bulk request.  Can be called as early as the parser.
    """
    content_type = request.content_type
    return 'ext=bulk' in content_type

def is_truthy(value):
    return value in TRUTHY

def is_falsy(value):
    return value in FALSY

def get_user_auth(request):
    """Given a Django request object, return an ``Auth`` object with the
    authenticated user attached to it.
    """
    user = request.user
    private_key = request.query_params.get('view_only', None)
    if user.is_anonymous():
        auth = Auth(None, private_key=private_key)
    else:
        auth = Auth(user, private_key=private_key)
    return auth


def absolute_reverse(view_name, query_kwargs=None, args=None, kwargs=None):
    """Like django's `reverse`, except returns an absolute URL. Also add query parameters."""
    relative_url = reverse(view_name, kwargs=kwargs)

    url = website_util.api_v2_url(relative_url, params=query_kwargs, base_prefix='')
    return url


def get_object_or_error(model_cls, query_or_pk, display_name=None):
    display_name = display_name or None

    if isinstance(query_or_pk, basestring):
        query = Q('_id', 'eq', query_or_pk)
    else:
        query = query_or_pk

    try:
        obj = model_cls.find_one(query)
        if getattr(obj, 'is_deleted', False) is True:
            if display_name is None:
                raise Gone
            else:
                raise Gone(detail='The requested {name} is no longer available.'.format(name=display_name))
        # For objects that have been disabled (is_active is False), return a 410.
        # The User model is an exception because we still want to allow
        # users who are unconfirmed or unregistered, but not users who have been
        # disabled.
        if model_cls is User:
            if obj.is_disabled:
                raise Gone(detail='The requested user is no longer available.')
        else:
            if not getattr(obj, 'is_active', True) or getattr(obj, 'is_deleted', False):
                if display_name is None:
                    raise Gone
                else:
                    raise Gone(detail='The requested {name} is no longer available.'.format(name=display_name))
        return obj

    except NoResultsFound:
        raise NotFound

def waterbutler_url_for(request_type, provider, path, node_id, token, obj_args=None, **query):
    """Reverse URL lookup for WaterButler routes
    :param str request_type: data or metadata
    :param str provider: The name of the requested provider
    :param str path: The path of the requested file or folder
    :param str node_id: The id of the node being accessed
    :param str token: The cookie to be used or None
    :param dict **query: Addition query parameters to be appended
    """
    url = furl.furl(website_settings.WATERBUTLER_URL)
    url.path.segments.append(request_type)

    url.args.update({
        'path': path,
        'nid': node_id,
        'provider': provider,
    })

    if token is not None:
        url.args['cookie'] = token

    if 'view_only' in obj_args:
        url.args['view_only'] = obj_args['view_only']

    url.args.update(query)
    return url.url

def add_dev_only_items(items, dev_only_items):
    """Add some items to a dictionary if in ``DEV_MODE``.
    """
    items = items.copy()
    if website_settings.DEV_MODE:
        items.update(dev_only_items)
    return items
