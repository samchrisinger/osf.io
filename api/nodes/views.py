import requests

from modularodm import Q
from rest_framework import generics, permissions as drf_permissions
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.status import is_server_error

from framework.auth.oauth_scopes import CoreScopes

from api.base import generic_bulk_views as bulk_views
from api.base import permissions as base_permissions
from api.base.filters import ODMFilterMixin, ListFilterMixin
from api.base.views import JSONAPIBaseView
from api.base.utils import get_object_or_error, is_bulk_request, get_user_auth
from api.files.serializers import FileSerializer
from api.comments.serializers import CommentSerializer, CommentCreateSerializer
from api.comments.permissions import CanCommentOrPublic
from api.users.views import UserMixin

from api.nodes.serializers import (
    NodeSerializer,
    NodeLinksSerializer,
    NodeDetailSerializer,
    NodeProviderSerializer,
    NodeContributorsSerializer,
    NodeContributorDetailSerializer,
    NodeAlternativeCitationSerializer,
    NodeContributorsCreateSerializer
)
from api.registrations.serializers import RegistrationSerializer
from api.nodes.permissions import (
    AdminOrPublic,
    ContributorOrPublic,
    ContributorOrPublicForPointers,
    ContributorDetailPermissions,
    ReadOnlyIfRegistration,
    ExcludeRetractions,
)
from api.base.exceptions import ServiceUnavailableError
from api.logs.serializers import NodeLogSerializer

from website.exceptions import NodeStateError
from website.util.permissions import ADMIN
from website.files.models import FileNode
from website.files.models import OsfStorageFileNode
from website.models import Node, Pointer, Comment, NodeLog
from framework.auth.core import User
from website.util import waterbutler_api_url_for


class NodeMixin(object):
    """Mixin with convenience methods for retrieving the current node based on the
    current URL. By default, fetches the current node based on the node_id kwarg.
    """

    serializer_class = NodeSerializer
    node_lookup_url_kwarg = 'node_id'

    def get_node(self, check_object_permissions=True):
        node = get_object_or_error(
            Node,
            self.kwargs[self.node_lookup_url_kwarg],
            display_name='node'
        )
        # Nodes that are folders/collections are treated as a separate resource, so if the client
        # requests a collection through a node endpoint, we return a 404
        if node.is_folder or node.is_registration:
            raise NotFound
        # May raise a permission denied
        if check_object_permissions:
            self.check_object_permissions(self.request, node)
        return node


class WaterButlerMixin(object):

    path_lookup_url_kwarg = 'path'
    provider_lookup_url_kwarg = 'provider'

    def get_file_item(self, item):
        attrs = item['attributes']
        file_node = FileNode.resolve_class(
            attrs['provider'],
            FileNode.FOLDER if attrs['kind'] == 'folder'
            else FileNode.FILE
        ).get_or_create(self.get_node(check_object_permissions=False), attrs['path'])

        file_node.update(None, attrs, user=self.request.user)

        self.check_object_permissions(self.request, file_node)

        return file_node

    def fetch_from_waterbutler(self):
        node = self.get_node(check_object_permissions=False)
        path = self.kwargs[self.path_lookup_url_kwarg]
        provider = self.kwargs[self.provider_lookup_url_kwarg]

        if provider == 'osfstorage':
            # Kinda like /me for a user
            # The one odd case where path is not really path
            if path == '/':
                obj = node.get_addon('osfstorage').get_root()
            else:
                obj = get_object_or_error(
                    OsfStorageFileNode,
                    Q('node', 'eq', node._id) &
                    Q('_id', 'eq', path.strip('/')) &
                    Q('is_file', 'eq', not path.endswith('/'))
                )

            self.check_object_permissions(self.request, obj)

            return obj

        url = waterbutler_api_url_for(node._id, provider, path, meta=True)
        waterbutler_request = requests.get(
            url,
            cookies=self.request.COOKIES,
            headers={'Authorization': self.request.META.get('HTTP_AUTHORIZATION')},
        )

        if waterbutler_request.status_code == 401:
            raise PermissionDenied

        if waterbutler_request.status_code == 404:
            raise NotFound

        if is_server_error(waterbutler_request.status_code):
            raise ServiceUnavailableError(detail='Could not retrieve files information at this time.')

        try:
            return waterbutler_request.json()['data']
        except KeyError:
            raise ServiceUnavailableError(detail='Could not retrieve files information at this time.')


class NodeList(JSONAPIBaseView, bulk_views.BulkUpdateJSONAPIView, bulk_views.BulkDestroyJSONAPIView, bulk_views.ListBulkCreateJSONAPIView, ODMFilterMixin):
    """Nodes that represent projects and components. *Writeable*.

    Paginated list of nodes ordered by their `date_modified`.  Each resource contains the full representation of the
    node, meaning additional requests to an individual node's detail view are not necessary.  For a registration,
    however, navigate to the individual registration's detail view for registration-specific information.

    <!--- Copied Spiel from NodeDetail -->

    On the front end, nodes are considered 'projects' or 'components'. The difference between a project and a component
    is that a project is the top-level node, and components are children of the project. There is also a [category
    field](/v2/#osf-node-categories) that includes 'project' as an option. The categorization essentially determines
    which icon is displayed by the node in the front-end UI and helps with search organization. Top-level nodes may have
    a category other than project, and children nodes may have a category of project.  Registrations can be accessed
    from this endpoint, but retracted registrations are excluded.

    ##Node Attributes

    <!--- Copied Attributes from NodeDetail -->

    OSF Node entities have the "nodes" `type`.

        name           type               description
        ---------------------------------------------------------------------------------
        title          string             title of project or component
        description    string             description of the node
        category       string             node category, must be one of the allowed values
        date_created   iso8601 timestamp  timestamp that the node was created
        date_modified  iso8601 timestamp  timestamp when the node was last updated
        tags           array of strings   list of tags that describe the node
        registration   boolean            is this a registration?
        fork           boolean            is this node a fork of another node?
        dashboard      boolean            is this node visible on the user dashboard?
        public         boolean            has this node been made publicly-visible?

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    ###Creating New Nodes

        Method:        POST
        URL:           /links/self
        Query Params:  <none>
        Body (JSON):   {
                         "data": {
                           "type": "nodes", # required
                           "attributes": {
                             "title":       {title},          # required
                             "category":    {category},       # required
                             "description": {description},    # optional
                             "tags":        [{tag1}, {tag2}], # optional
                             "public":      true|false        # optional
                           }
                         }
                       }
        Success:       201 CREATED + node representation

    New nodes are created by issuing a POST request to this endpoint.  The `title` and `category` fields are
    mandatory. `category` must be one of the [permitted node categories](/v2/#osf-node-categories).  `public` defaults
    to false.  All other fields not listed above will be ignored.  If the node creation is successful the API will
    return a 201 response with the representation of the new node in the body.  For the new node's canonical URL, see
    the `/links/self` field of the response.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    + `view_only=<Str>` -- Allow users with limited access keys to access this node. Note that some keys are anonymous, so using the view_only key will cause user-related information to no longer serialize. This includes blank ids for users and contributors and missing serializer fields and relationships.

    Nodes may be filtered by their `title`, `category`, `description`, `public`, `registration`, or `tags`.  `title`,
    `description`, and `category` are string fields and will be filtered using simple substring matching.  `public` and
    `registration` are booleans, and can be filtered using truthy values, such as `true`, `false`, `0`, or `1`.  Note
    that quoting `true` or `false` in the query will cause the match to fail regardless.  `tags` is an array of simple strings.

    #This Request/Response

    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.NODE_BASE_READ]
    required_write_scopes = [CoreScopes.NODE_BASE_WRITE]
    model_class = Node

    serializer_class = NodeSerializer
    view_category = 'nodes'
    view_name = 'node-list'

    ordering = ('-date_modified', )  # default ordering

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        base_query = (
            Q('is_deleted', 'ne', True) &
            Q('is_folder', 'ne', True) &
            Q('is_registration', 'ne', True)
        )
        user = self.request.user
        permission_query = Q('is_public', 'eq', True)
        if not user.is_anonymous():
            permission_query = (permission_query | Q('contributors', 'icontains', user._id))

        query = base_query & permission_query
        return query

    # overrides ListBulkCreateJSONAPIView, BulkUpdateJSONAPIView
    def get_queryset(self):
        # For bulk requests, queryset is formed from request body.
        if is_bulk_request(self.request):
            query = Q('_id', 'in', [node['id'] for node in self.request.data])
            auth = get_user_auth(self.request)

            nodes = Node.find(query)
            for node in nodes:
                if not node.can_edit(auth):
                    raise PermissionDenied
            return nodes
        else:
            query = self.get_query_from_request()
            return Node.find(query)

    # overrides ListBulkCreateJSONAPIView, BulkUpdateJSONAPIView, BulkDestroyJSONAPIView
    def get_serializer_class(self):
        """
        Use NodeDetailSerializer which requires 'id'
        """
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return NodeDetailSerializer
        else:
            return NodeSerializer

    # overrides ListBulkCreateJSONAPIView
    def perform_create(self, serializer):
        """Create a node.

        :param serializer:
        """
        # On creation, make sure that current user is the creator
        user = self.request.user
        serializer.save(creator=user)

    # overrides BulkDestroyJSONAPIView
    def allow_bulk_destroy_resources(self, user, resource_list):
        """User must have admin permissions to delete nodes."""
        for node in resource_list:
            if not node.has_permission(user, ADMIN):
                return False
        return True

    # Overrides BulkDestroyJSONAPIView
    def perform_destroy(self, instance):
        auth = get_user_auth(self.request)
        try:
            instance.remove_node(auth=auth)
        except NodeStateError as err:
            raise ValidationError(err.message)
        instance.save()


class NodeDetail(JSONAPIBaseView, generics.RetrieveUpdateDestroyAPIView, NodeMixin):
    """Details about a given node (project or component). *Writeable*.

    On the front end, nodes are considered 'projects' or 'components'. The difference between a project and a component
    is that a project is the top-level node, and components are children of the project. There is also a [category
    field](/v2/#osf-node-categories) that includes 'project' as an option. The categorization essentially determines
    which icon is displayed by the node in the front-end UI and helps with search organization. Top-level nodes may have
    a category other than project, and children nodes may have a category of project. Registrations can be accessed through
    this endpoint, though registration-specific fields must be retrieved through a registration's detail view.

    ###Permissions

    Nodes that are made public will give read-only access to everyone. Private nodes require explicit read
    permission. Write and admin access are the same for public and private nodes. Administrators on a parent node have
    implicit read permissions for all child nodes.

    ##Attributes

    OSF Node entities have the "nodes" `type`.

        name           type               description
        ---------------------------------------------------------------------------------
        title          string             title of project or component
        description    string             description of the node
        category       string             node category, must be one of the allowed values
        date_created   iso8601 timestamp  timestamp that the node was created
        date_modified  iso8601 timestamp  timestamp when the node was last updated
        tags           array of strings   list of tags that describe the node
        registration   boolean            has this project been registered?
        fork           boolean            is this node a fork of another node?
        dashboard      boolean            is this node visible on the user dashboard?
        public         boolean            has this node been made publicly-visible?

    ##Relationships

    ###Children

    List of nodes that are children of this node.  New child nodes may be added through this endpoint.

    ###Contributors

    List of users who are contributors to this node. Contributors may have "read", "write", or "admin" permissions.
    A node must always have at least one "admin" contributor.  Contributors may be added via this endpoint.

    ###Files

    List of top-level folders (actually cloud-storage providers) associated with this node. This is the starting point
    for accessing the actual files stored within this node.

    ###Parent

    If this node is a child node of another node, the parent's canonical endpoint will be available in the
    `/parent/links/related/href` key.  Otherwise, it will be null.

    ###Forked From

    If this node was forked from another node, the canonical endpoint of the node that was forked from will be
    available in the `/forked_from/links/related/href` key.  Otherwise, it will be null.

    ###Registrations

    List of registrations of the current node.

    ##Links

        self:  the canonical api endpoint of this node
        html:  this node's page on the OSF website

    ##Actions

    ###Update

        Method:        PUT / PATCH
        URL:           /links/self
        Query Params:  <none>
        Body (JSON):   {
                         "data": {
                           "type": "nodes",   # required
                           "id":   {node_id}, # required
                           "attributes": {
                             "title":       {title},          # mandatory
                             "category":    {category},       # mandatory
                             "description": {description},    # optional
                             "tags":        [{tag1}, {tag2}], # optional
                             "public":      true|false        # optional
                           }
                         }
                       }
        Success:       200 OK + node representation

    To update a node, issue either a PUT or a PATCH request against the `/links/self` URL.  The `title` and `category`
    fields are mandatory if you PUT and optional if you PATCH.  The `tags` parameter must be an array of strings.
    Non-string values will be accepted and stringified, but we make no promises about the stringification output.  So
    don't do that.

    ###Delete

        Method:   DELETE
        URL:      /links/self
        Params:   <none>
        Success:  204 No Content

    To delete a node, issue a DELETE request against `/links/self`.  A successful delete will return a 204 No Content
    response. Attempting to delete a node you do not own will result in a 403 Forbidden.

    ##Query Params

    + `view_only=<Str>` -- Allow users with limited access keys to access this node. Note that some keys are anonymous, so using the view_only key will cause user-related information to no longer serialize. This includes blank ids for users and contributors and missing serializer fields and relationships.

    #This Request/Response

    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        ContributorOrPublic,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope,
        ExcludeRetractions,
    )

    required_read_scopes = [CoreScopes.NODE_BASE_READ]
    required_write_scopes = [CoreScopes.NODE_BASE_WRITE]

    serializer_class = NodeDetailSerializer
    view_category = 'nodes'
    view_name = 'node-detail'

    # overrides RetrieveUpdateDestroyAPIView
    def get_object(self):
        return self.get_node()

    # overrides RetrieveUpdateDestroyAPIView
    def perform_destroy(self, instance):
        auth = get_user_auth(self.request)
        node = self.get_object()
        try:
            node.remove_node(auth=auth)
        except NodeStateError as err:
            raise ValidationError(err.message)
        node.save()


class NodeContributorsList(JSONAPIBaseView, bulk_views.BulkUpdateJSONAPIView, bulk_views.BulkDestroyJSONAPIView, bulk_views.ListBulkCreateJSONAPIView, ListFilterMixin, NodeMixin):
    """Contributors (users) for a node.

    Contributors are users who can make changes to the node or, in the case of private nodes,
    have read access to the node. Contributors are divided between 'bibliographic' and 'non-bibliographic'
    contributors. From a permissions standpoint, both are the same, but bibliographic contributors
    are included in citations, while non-bibliographic contributors are not included in citations.

    Note that if an anonymous view_only key is being used, the user relationship will not be exposed and the id for
    the contributor will be an empty string.

    ##Node Contributor Attributes

    <!--- Copied Attributes from NodeContributorDetail -->

    `type` is "contributors"

        name           type     description
        ------------------------------------------------------------------------------------------------------
        bibliographic  boolean  Whether the user will be included in citations for this node. Default is true.
        permission     string   User permission level. Must be "read", "write", or "admin". Default is "write".

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Relationships

    ###Users

    This endpoint shows the contributor user detail and is automatically embedded.

    ##Actions

    ###Adding Contributors

        Method:        POST
        URL:           /links/self
        Query Params:  <none>
        Body (JSON): {
                      "data": {
                        "type": "contributors",                   # required
                        "attributes": {
                          "bibliographic": true|false,            # optional
                          "permission": "read"|"write"|"admin"    # optional
                        },
                        "relationships": {
                          "users": {
                            "data": {
                              "type": "users",                    # required
                              "id":   "{user_id}"                 # required
                            }
                        }
                    }
                }
            }
        Success:       201 CREATED + node contributor representation

    Add a contributor to a node by issuing a POST request to this endpoint.  This effectively creates a relationship
    between the node and the user.  Besides the top-level type, there are optional "attributes" which describe the
    relationship between the node and the user. `bibliographic` is a boolean and defaults to `true`.  `permission` must
    be a [valid OSF permission key](/v2/#osf-node-permission-keys) and defaults to `"write"`.  A relationship object
    with a "data" member, containing the user `type` and user `id` must be included.  The id must be a valid user id.
    All other fields not listed above will be ignored.  If the request is successful the API will return
    a 201 response with the representation of the new node contributor in the body.  For the new node contributor's
    canonical URL, see the `/links/self` field of the response.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    NodeContributors may be filtered by `bibliographic`, or `permission` attributes.  `bibliographic` is a boolean, and
    can be filtered using truthy values, such as `true`, `false`, `0`, or `1`.  Note that quoting `true` or `false` in
    the query will cause the match to fail regardless.

    + `profile_image_size=<Int>` -- Modifies `/links/profile_image_url` of the user entities so that it points to
    the user's profile image scaled to the given size in pixels.  If left blank, the size depends on the image provider.

    #This Request/Response
    """
    permission_classes = (
        AdminOrPublic,
        drf_permissions.IsAuthenticatedOrReadOnly,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.NODE_CONTRIBUTORS_READ]
    required_write_scopes = [CoreScopes.NODE_CONTRIBUTORS_WRITE]
    model_class = User

    serializer_class = NodeContributorsSerializer
    view_category = 'nodes'
    view_name = 'node-contributors'

    def get_default_queryset(self):
        node = self.get_node()
        visible_contributors = node.visible_contributor_ids
        contributors = []
        for contributor in node.contributors:
            contributor.bibliographic = contributor._id in visible_contributors
            contributor.permission = node.get_permissions(contributor)[-1]
            contributor.node_id = node._id
            contributors.append(contributor)
        return contributors

    # overrides ListBulkCreateJSONAPIView, BulkUpdateJSONAPIView, BulkDeleteJSONAPIView
    def get_serializer_class(self):
        """
        Use NodeContributorDetailSerializer which requires 'id'
        """
        if self.request.method == 'PUT' or self.request.method == 'PATCH' or self.request.method == 'DELETE':
            return NodeContributorDetailSerializer
        elif self.request.method == 'POST':
            return NodeContributorsCreateSerializer
        else:
            return NodeContributorsSerializer

    # overrides ListBulkCreateJSONAPIView, BulkUpdateJSONAPIView
    def get_queryset(self):
        queryset = self.get_queryset_from_request()

        # If bulk request, queryset only contains contributors in request
        if is_bulk_request(self.request):
            contrib_ids = [item['id'] for item in self.request.data]
            queryset[:] = [contrib for contrib in queryset if contrib._id in contrib_ids]
        return queryset

    # overrides ListCreateAPIView
    def get_parser_context(self, http_request):
        """
        Tells parser that we are creating a relationship
        """
        res = super(NodeContributorsList, self).get_parser_context(http_request)
        res['is_relationship'] = True
        return res

    # Overrides BulkDestroyJSONAPIView
    def perform_destroy(self, instance):
        auth = get_user_auth(self.request)
        node = self.get_node()
        if len(node.visible_contributors) == 1 and node.get_visible(instance):
            raise ValidationError("Must have at least one visible contributor")
        if instance not in node.contributors:
                raise NotFound('User cannot be found in the list of contributors.')
        removed = node.remove_contributor(instance, auth)
        if not removed:
            raise ValidationError("Must have at least one registered admin contributor")


class NodeContributorDetail(JSONAPIBaseView, generics.RetrieveUpdateDestroyAPIView, NodeMixin, UserMixin):
    """Detail of a contributor for a node. *Writeable*.

    Contributors are users who can make changes to the node or, in the case of private nodes,
    have read access to the node. Contributors are divided between 'bibliographic' and 'non-bibliographic'
    contributors. From a permissions standpoint, both are the same, but bibliographic contributors
    are included in citations, while non-bibliographic contributors are not included in citations.

    Note that if an anonymous view_only key is being used, the user relationship will not be exposed and the id for
    the contributor will be an empty string.

    Contributors can be viewed, removed, and have their permissions and bibliographic status changed via this
    endpoint.

    ##Attributes

    `type` is "contributors"

        name           type     description
        ------------------------------------------------------------------------------------------------------
        bibliographic  boolean  Whether the user will be included in citations for this node. Default is true.
        permission     string   User permission level. Must be "read", "write", or "admin". Default is "write".

    ##Relationships

    ###Users

    This endpoint shows the contributor user detail.

    ##Links

        self:           the canonical api endpoint of this contributor
        html:           the contributing user's page on the OSF website
        profile_image:  a url to the contributing user's profile image

    ##Actions

    ###Update Contributor

        Method:        PUT / PATCH
        URL:           /links/self
        Query Params:  <none>
        Body (JSON):   {
                         "data": {
                           "type": "contributors",                    # required
                           "id": {contributor_id},                    # required
                           "attributes": {
                             "bibliographic": true|false,             # optional
                             "permission": "read"|"write"|"admin"     # optional
                           }
                         }
                       }
        Success:       200 OK + node representation

    To update a contributor's bibliographic preferences or access permissions for the node, issue a PUT request to the
    `self` link. Since this endpoint has no mandatory attributes, PUT and PATCH are functionally the same.  If the given
    user is not already in the contributor list, a 404 Not Found error will be returned.  A node must always have at
    least one admin, and any attempt to downgrade the permissions of a sole admin will result in a 400 Bad Request
    error.

    ###Remove Contributor

        Method:        DELETE
        URL:           /links/self
        Query Params:  <none>
        Success:       204 No Content

    To remove a contributor from a node, issue a DELETE request to the `self` link.  Attempting to remove the only admin
    from a node will result in a 400 Bad Request response.  This request will only remove the relationship between the
    node and the user, not the user itself.

    ##Query Params

    + `profile_image_size=<Int>` -- Modifies `/links/profile_image_url` so that it points the image scaled to the given
    size in pixels.  If left blank, the size depends on the image provider.

    #This Request/Response

    """
    permission_classes = (
        ContributorDetailPermissions,
        drf_permissions.IsAuthenticatedOrReadOnly,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.NODE_CONTRIBUTORS_READ]
    required_write_scopes = [CoreScopes.NODE_CONTRIBUTORS_WRITE]

    serializer_class = NodeContributorDetailSerializer
    view_category = 'nodes'
    view_name = 'node-contributor-detail'

    # overrides RetrieveAPIView
    def get_object(self):
        node = self.get_node()
        user = self.get_user()
        # May raise a permission denied
        self.check_object_permissions(self.request, user)
        if user not in node.contributors:
            raise NotFound('{} cannot be found in the list of contributors.'.format(user))
        user.permission = node.get_permissions(user)[-1]
        user.bibliographic = node.get_visible(user)
        user.node_id = node._id
        return user

    # overrides DestroyAPIView
    def perform_destroy(self, instance):
        node = self.get_node()
        auth = get_user_auth(self.request)
        if len(node.visible_contributors) == 1 and node.get_visible(instance):
            raise ValidationError("Must have at least one visible contributor")
        removed = node.remove_contributor(instance, auth)
        if not removed:
            raise ValidationError("Must have at least one registered admin contributor")


# TODO: Support creating registrations
class NodeRegistrationsList(JSONAPIBaseView, generics.ListAPIView, NodeMixin):
    """Registrations of the current node.

    Registrations are read-only snapshots of a project. This view is a list of all the registrations of the current node.

    Each resource contains the full representation of the registration, meaning additional requests to an individual
    registrations's detail view are not necessary.

    ##Registration Attributes

    Registrations have the "registrations" `type`.

        name               type               description
        ---------------------------------------------------------------------------------
        title              string             title of the registered project or component
        description        string             description of the registered node
        category           string             node category, must be one of the allowed values
        date_created       iso8601 timestamp  timestamp that the node was created
        date_modified      iso8601 timestamp  timestamp when the node was last updated
        tags               array of strings   list of tags that describe the registered node
        fork               boolean            is this project a fork?
        registration       boolean            has this project been registered?
        dashboard          boolean            is this registered node visible on the user dashboard?
        public             boolean            has this registration been made publicly-visible?
        retracted          boolean            has this registration been retracted?
        date_registered    iso8601 timestamp  timestamp that the registration was created


    ##Relationships

    ###Registered from

    The registration is branched from this node.

    ###Registered by

    The registration was initiated by this user.

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    #This request/response

    """
    permission_classes = (
        ContributorOrPublic,
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
        ExcludeRetractions
    )

    required_read_scopes = [CoreScopes.NODE_REGISTRATIONS_READ]
    required_write_scopes = [CoreScopes.NODE_REGISTRATIONS_WRITE]

    serializer_class = RegistrationSerializer
    view_category = 'nodes'
    view_name = 'node-registrations'

    # overrides ListAPIView
    # TODO: Filter out retractions by default
    def get_queryset(self):
        nodes = self.get_node().node__registrations
        auth = get_user_auth(self.request)
        registrations = [node for node in nodes if node.can_view(auth)]
        return registrations


class NodeChildrenList(JSONAPIBaseView, bulk_views.ListBulkCreateJSONAPIView, NodeMixin, ODMFilterMixin):
    """Children of the current node. *Writeable*.

    This will get the next level of child nodes for the selected node if the current user has read access for those
    nodes. Creating a node via this endpoint will behave the same as the [node list endpoint](/v2/nodes/), but the new
    node will have the selected node set as its parent.

    ##Node Attributes

    <!--- Copied Attributes from NodeDetail -->

    OSF Node entities have the "nodes" `type`.

        name           type               description
        ---------------------------------------------------------------------------------
        title          string             title of project or component
        description    string             description of the node
        category       string             node category, must be one of the allowed values
        date_created   iso8601 timestamp  timestamp that the node was created
        date_modified  iso8601 timestamp  timestamp when the node was last updated
        tags           array of strings   list of tags that describe the node
        registration   boolean            has this project been registered?
        fork           boolean            is this node a fork of another node?
        dashboard      boolean            is this node visible on the user dashboard?
        public         boolean            has this node been made publicly-visible?

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    ###Create Child Node

    <!--- Copied Creating New Node from NodeList -->

        Method:        POST
        URL:           /links/self
        Query Params:  <none>
        Body (JSON):   {
                         "data": {
                           "type": "nodes", # required
                           "attributes": {
                             "title":       {title},         # required
                             "category":    {category},      # required
                             "description": {description},   # optional
                             "tags":        [{tag1}, {tag2}] # optional
                           }
                         }
                       }
        Success:       201 CREATED + node representation

    To create a child node of the current node, issue a POST request to this endpoint.  The `title` and `category`
    fields are mandatory. `category` must be one of the [permitted node categories](/v2/#osf-node-categories).  If the
    node creation is successful the API will return a 201 response with the representation of the new node in the body.
    For the new node's canonical URL, see the `/links/self` field of the response.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    <!--- Copied Query Params from NodeList -->

    Nodes may be filtered by their `title`, `category`, `description`, `public`, `registration`, or `tags`.  `title`,
    `description`, and `category` are string fields and will be filtered using simple substring matching.  `public` and
    `registration` are booleans, and can be filtered using truthy values, such as `true`, `false`, `0`, or `1`.  Note
    that quoting `true` or `false` in the query will cause the match to fail regardless.  `tags` is an array of simple strings.

    #This Request/Response

    """
    permission_classes = (
        ContributorOrPublic,
        drf_permissions.IsAuthenticatedOrReadOnly,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope,
        ExcludeRetractions
    )

    required_read_scopes = [CoreScopes.NODE_CHILDREN_READ]
    required_write_scopes = [CoreScopes.NODE_CHILDREN_WRITE]

    serializer_class = NodeSerializer
    view_category = 'nodes'
    view_name = 'node-children'

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        return (
            Q('is_deleted', 'ne', True) &
            Q('is_folder', 'ne', True)
        )

    # overrides ListBulkCreateJSONAPIView
    def get_queryset(self):
        node = self.get_node()
        req_query = self.get_query_from_request()

        query = (
            Q('_id', 'in', [e._id for e in node.nodes if e.primary]) &
            req_query
        )
        nodes = Node.find(query)
        auth = get_user_auth(self.request)
        children = [each for each in nodes if each.can_view(auth)]
        return children

    # overrides ListBulkCreateJSONAPIView
    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(creator=user, parent=self.get_node())


# TODO: Make NodeLinks filterable. They currently aren't filterable because we have can't
# currently query on a Pointer's node's attributes.
# e.g. Pointer.find(Q('node.title', 'eq', ...)) doesn't work
class NodeLinksList(JSONAPIBaseView, bulk_views.BulkDestroyJSONAPIView, bulk_views.ListBulkCreateJSONAPIView, NodeMixin):
    """Node Links to other nodes. *Writeable*.

    Node Links act as pointers to other nodes. Unlike Forks, they are not copies of nodes;
    Node Links are a direct reference to the node that they point to.

    ##Node Link Attributes
    `type` is "node_links"

        None

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Relationships

    ### Target Node

    This endpoint shows the target node detail and is automatically embedded.

    ##Actions

    ###Adding Node Links
        Method:        POST
        URL:           /links/self
        Query Params:  <none>
        Body (JSON): {
                       "data": {
                          "type": "node_links",                  # required
                          "relationships": {
                            "nodes": {
                              "data": {
                                "type": "nodes",                 # required
                                "id": "{target_node_id}",        # required
                              }
                            }
                          }
                       }
                    }
        Success:       201 CREATED + node link representation

    To add a node link (a pointer to another node), issue a POST request to this endpoint.  This effectively creates a
    relationship between the node and the target node.  The target node must be described as a relationship object with
    a "data" member, containing the nodes `type` and the target node `id`.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    #This Request/Response
    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        ContributorOrPublic,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope,
        ExcludeRetractions,
    )

    required_read_scopes = [CoreScopes.NODE_LINKS_READ]
    required_write_scopes = [CoreScopes.NODE_LINKS_WRITE]
    model_class = Pointer

    serializer_class = NodeLinksSerializer
    view_category = 'nodes'
    view_name = 'node-pointers'

    def get_queryset(self):
        return [
            pointer for pointer in
            self.get_node().nodes_pointer
            if not pointer.node.is_deleted
        ]

    # Overrides BulkDestroyJSONAPIView
    def perform_destroy(self, instance):
        auth = get_user_auth(self.request)
        node = self.get_node()
        try:
            node.rm_pointer(instance, auth=auth)
        except ValueError as err:  # pointer doesn't belong to node
            raise ValidationError(err.message)
        node.save()

    # overrides ListCreateAPIView
    def get_parser_context(self, http_request):
        """
        Tells parser that we are creating a relationship
        """
        res = super(NodeLinksList, self).get_parser_context(http_request)
        res['is_relationship'] = True
        return res


class NodeLinksDetail(JSONAPIBaseView, generics.RetrieveDestroyAPIView, NodeMixin):
    """Node Link details. *Writeable*.

    Node Links act as pointers to other nodes. Unlike Forks, they are not copies of nodes;
    Node Links are a direct reference to the node that they point to.

    ##Attributes
    `type` is "node_links"

        None

    ##Links

    *None*

    ##Relationships

    ###Target node

    This endpoint shows the target node detail and is automatically embedded.

    ##Actions

    ###Remove Node Link

        Method:        DELETE
        URL:           /links/self
        Query Params:  <none>
        Success:       204 No Content

    To remove a node link from a node, issue a DELETE request to the `self` link.  This request will remove the
    relationship between the node and the target node, not the nodes themselves.

    ##Query Params

    *None*.

    #This Request/Response
    """
    permission_classes = (
        ContributorOrPublicForPointers,
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
        ReadOnlyIfRegistration,
        ExcludeRetractions
    )

    required_read_scopes = [CoreScopes.NODE_LINKS_READ]
    required_write_scopes = [CoreScopes.NODE_LINKS_WRITE]

    serializer_class = NodeLinksSerializer
    view_category = 'nodes'
    view_name = 'node-pointer-detail'

    # overrides RetrieveAPIView
    def get_object(self):
        node_link_lookup_url_kwarg = 'node_link_id'
        node_link = get_object_or_error(
            Pointer,
            self.kwargs[node_link_lookup_url_kwarg],
            'node link'
        )
        # May raise a permission denied
        self.check_object_permissions(self.request, node_link)
        return node_link

    # overrides DestroyAPIView
    def perform_destroy(self, instance):
        auth = get_user_auth(self.request)
        node = self.get_node()
        pointer = self.get_object()
        try:
            node.rm_pointer(pointer, auth=auth)
        except ValueError as err:  # pointer doesn't belong to node
            raise NotFound(err.message)
        node.save()


class NodeFilesList(JSONAPIBaseView, generics.ListAPIView, WaterButlerMixin, ListFilterMixin, NodeMixin):
    """Files attached to a node for a given provider. *Read-only*.

    This gives a list of all of the files and folders that are attached to your project for the given storage provider.
    If the provider is not "osfstorage", the metadata for the files in the storage will be retrieved and cached whenever
    this endpoint is accessed.  To see the cached metadata, GET the endpoint for the file directly (available through
    its `/links/info` attribute).

    When a create/update/delete action is performed against the file or folder, the action is handled by an external
    service called WaterButler.  The WaterButler response format differs slightly from the OSF's.

    <!--- Copied from FileDetail.Spiel -->

    ###Waterbutler Entities

    When an action is performed against a WaterButler endpoint, it will generally respond with a file entity, a folder
    entity, or no content.

    ####File Entity

        name          type       description
        -------------------------------------------------------------------------
        name          string     name of the file
        path          string     unique identifier for this file entity for this
                                 project and storage provider. may not end with '/'
        materialized  string     the full path of the file relative to the storage
                                 root.  may not end with '/'
        kind          string     "file"
        etag          string     etag - http caching identifier w/o wrapping quotes
        modified      timestamp  last modified timestamp - format depends on provider
        contentType   string     MIME-type when available
        provider      string     id of provider e.g. "osfstorage", "s3", "googledrive".
                                 equivalent to addon_short_name on the OSF
        size          integer    size of file in bytes
        extra         object     may contain additional data beyond what's described here,
                                 depending on the provider
          version     integer    version number of file. will be 1 on initial upload
          downloads   integer    count of the number times the file has been downloaded
          hashes      object
            md5       string     md5 hash of file
            sha256    string     SHA-256 hash of file

    ####Folder Entity

        name          type    description
        ----------------------------------------------------------------------
        name          string  name of the folder
        path          string  unique identifier for this folder entity for this
                              project and storage provider. must end with '/'
        materialized  string  the full path of the folder relative to the storage
                              root.  must end with '/'
        kind          string  "folder"
        etag          string  etag - http caching identifier w/o wrapping quotes
        extra         object  varies depending on provider

    ##File Attributes

    <!--- Copied Attributes from FileDetail -->

    For an OSF File entity, the `type` is "files" regardless of whether the entity is actually a file or folder.  They
    can be distinguished by the `kind` attribute.  Files and folders use the same representation, but some attributes may
    be null for one kind but not the other. `size` will be null for folders.  A list of storage provider keys can be
    found [here](/v2/#storage-providers).

        name          type               description
        ---------------------------------------------------------------------------------
        name          string             name of the file or folder; use for display
        kind          string             "file" or "folder"
        path          url path           unique path for this entity, used in "move" actions
        size          integer            size of file in bytes, null for folders
        provider      string             storage provider for this file. "osfstorage" if stored on the OSF.  Other
                                         examples include "s3" for Amazon S3, "googledrive" for Google Drive, "box"
                                         for Box.com.
        last_touched  iso8601 timestamp  last time the metadata for the file was retrieved. only applies to non-OSF
                                         storage providers.
        date_modified iso8601 timestamp  timestamp of when this file was last updated
        extra         object             may contain additional data beyond what's described here, depending on
                                         the provider
          hashes      object
            md5       string             md5 hash of file, null for folders
            sha256    string             SHA-256 hash of file, null for folders

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    <!--- Copied from FileDetail.Actions -->

    The `links` property of the response provides endpoints for common file operations. The currently-supported actions
    are:

    ###Get Info (*files, folders*)

        Method:   GET
        URL:      /links/info
        Params:   <none>
        Success:  200 OK + file representation

    The contents of a folder or details of a particular file can be retrieved by performing a GET request against the
    `info` link. The response will be a standard OSF response format with the [OSF File attributes](#attributes).

    ###Download (*files*)

        Method:   GET
        URL:      /links/download
        Params:   <none>
        Success:  200 OK + file body

    To download a file, issue a GET request against the `download` link.  The response will have the Content-Disposition
    header set, which will will trigger a download in a browser.

    ###Create Subfolder (*folders*)

        Method:       PUT
        URL:          /links/new_folder
        Query Params: ?kind=folder&name={new_folder_name}
        Body:         <empty>
        Success:      201 Created + new folder representation

    You can create a subfolder of an existing folder by issuing a PUT request against the `new_folder` link.  The
    `?kind=folder` portion of the query parameter is already included in the `new_folder` link.  The name of the new
    subfolder should be provided in the `name` query parameter.  The response will contain a [WaterButler folder
    entity](#folder-entity).  If a folder with that name already exists in the parent directory, the server will return
    a 409 Conflict error response.

    ###Upload New File (*folders*)

        Method:       PUT
        URL:          /links/upload
        Query Params: ?kind=file&name={new_file_name}
        Body (Raw):   <file data (not form-encoded)>
        Success:      201 Created or 200 OK + new file representation

    To upload a file to a folder, issue a PUT request to the folder's `upload` link with the raw file data in the
    request body, and the `kind` and `name` query parameters set to `'file'` and the desired name of the file.  The
    response will contain a [WaterButler file entity](#file-entity) that describes the new file.  If a file with the
    same name already exists in the folder, it will be considered a new version.  In this case, the response will be a
    200 OK.

    ###Update Existing File (*file*)

        Method:       PUT
        URL:          /links/upload
        Query Params: ?kind=file
        Body (Raw):   <file data (not form-encoded)>
        Success:      200 OK + updated file representation

    To update an existing file, issue a PUT request to the file's `upload` link with the raw file data in the request
    body and the `kind` query parameter set to `"file"`.  The update action will create a new version of the file.
    The response will contain a [WaterButler file entity](#file-entity) that describes the updated file.

    ###Rename (*files, folders*)

        Method:        POST
        URL:           /links/move
        Query Params:  <none>
        Body (JSON):   {
                        "action": "rename",
                        "rename": {new_file_name}
                       }
        Success:       200 OK + new entity representation

    To rename a file or folder, issue a POST request to the `move` link with the `action` body parameter set to
    `"rename"` and the `rename` body parameter set to the desired name.  The response will contain either a folder
    entity or file entity with the new name.

    ###Move & Copy (*files, folders*)

        Method:        POST
        URL:           /links/move
        Query Params:  <none>
        Body (JSON):   {
                        // mandatory
                        "action":   "move"|"copy",
                        "path":     {path_attribute_of_target_folder},
                        // optional
                        "rename":   {new_name},
                        "conflict": "replace"|"keep", // defaults to 'replace'
                        "resource": {node_id},        // defaults to current {node_id}
                        "provider": {provider}        // defaults to current {provider}
                       }
        Success:       200 OK or 201 Created + new entity representation

    Move and copy actions both use the same request structure, a POST to the `move` url, but with different values for
    the `action` body parameters.  The `path` parameter is also required and should be the OSF `path` attribute of the
    folder being written to.  The `rename` and `conflict` parameters are optional.  If you wish to change the name of
    the file or folder at its destination, set the `rename` parameter to the new name.  The `conflict` param governs how
    name clashes are resolved.  Possible values are `replace` and `keep`.  `replace` is the default and will overwrite
    the file that already exists in the target folder.  `keep` will attempt to keep both by adding a suffix to the new
    file's name until it no longer conflicts.  The suffix will be ' (**x**)' where **x** is a increasing integer
    starting from 1.  This behavior is intended to mimic that of the OS X Finder.  The response will contain either a
    folder entity or file entity with the new name.

    Files and folders can also be moved between nodes and providers.  The `resource` parameter is the id of the node
    under which the file/folder should be moved.  It *must* agree with the `path` parameter, that is the `path` must
    identify a valid folder under the node identified by `resource`.  Likewise, the `provider` parameter may be used to
    move the file/folder to another storage provider, but both the `resource` and `path` parameters must belong to a
    node and folder already extant on that provider.  Both `resource` and `provider` default to the current node and
    providers.

    If a moved/copied file is overwriting an existing file, a 200 OK response will be returned.  Otherwise, a 201
    Created will be returned.

    ###Delete (*file, folders*)

        Method:        DELETE
        URL:           /links/delete
        Query Params:  <none>
        Success:       204 No Content

    To delete a file or folder send a DELETE request to the `delete` link.  Nothing will be returned in the response
    body.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    Node files may be filtered by `id`, `name`, `node`, `kind`, `path`, `provider`, `size`, and `last_touched`.

    #This Request/Response

    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.PermissionWithGetter(ContributorOrPublic, 'node'),
        base_permissions.PermissionWithGetter(ReadOnlyIfRegistration, 'node'),
        base_permissions.TokenHasScope,
        ExcludeRetractions
    )

    ordering = ('materialized_path',)  # default ordering

    serializer_class = FileSerializer

    required_read_scopes = [CoreScopes.NODE_FILE_READ]
    required_write_scopes = [CoreScopes.NODE_FILE_WRITE]

    view_category = 'nodes'
    view_name = 'node-files'

    def get_default_queryset(self):
        # Don't bother going to waterbutler for osfstorage
        files_list = self.fetch_from_waterbutler()

        if isinstance(files_list, list):
            return [self.get_file_item(file) for file in files_list]

        if isinstance(files_list, dict) or getattr(files_list, 'is_file', False):
            # We should not have gotten a file here
            raise NotFound

        return list(files_list.children)

    # overrides ListAPIView
    def get_queryset(self):
        return self.get_queryset_from_request()


class NodeFileDetail(JSONAPIBaseView, generics.RetrieveAPIView, WaterButlerMixin, NodeMixin):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.PermissionWithGetter(ContributorOrPublic, 'node'),
        base_permissions.PermissionWithGetter(ReadOnlyIfRegistration, 'node'),
        base_permissions.TokenHasScope,
        ExcludeRetractions
    )

    serializer_class = FileSerializer

    required_read_scopes = [CoreScopes.NODE_FILE_READ]
    required_write_scopes = [CoreScopes.NODE_FILE_WRITE]
    view_category = 'nodes'
    view_name = 'node-file-detail'

    def get_object(self):
        fobj = self.fetch_from_waterbutler()
        if isinstance(fobj, dict):
            return self.get_file_item(fobj)

        if isinstance(fobj, list) or not getattr(fobj, 'is_file', True):
            # We should not have gotten a folder here
            raise NotFound

        return fobj


class NodeProvider(object):

    def __init__(self, provider, node):
        self.path = '/'
        self.node = node
        self.kind = 'folder'
        self.name = provider
        self.provider = provider
        self.node_id = node._id
        self.pk = node._id


class NodeProvidersList(JSONAPIBaseView, generics.ListAPIView, NodeMixin):
    """List of storage providers enabled for this node. *Read-only*.

    Users of the OSF may access their data on a [number of cloud-storage](/v2/#storage-providers) services that have
    integrations with the OSF.  We call these "providers".  By default every node has access to the OSF-provided
    storage but may use as many of the supported providers as desired.  This endpoint lists all of the providers that are
    configured for this node.  If you want to add more, you will need to do that in the Open Science Framework front end
    for now.

    In the OSF filesystem model, providers are treated as folders, but with special properties that distinguish them
    from regular folders.  Every provider folder is considered a root folder, and may not be deleted through the regular
    file API.  To see the contents of the provider, issue a GET request to the `/relationships/files/links/related/href`
    attribute of the provider resource.  The `new_folder` and `upload` actions are handled by another service called
    WaterButler, whose response format differs slightly from the OSF's.

    <!--- Copied from FileDetail.Spiel -->

    ###Waterbutler Entities

    When an action is performed against a WaterButler endpoint, it will generally respond with a file entity, a folder
    entity, or no content.

    ####File Entity

        name          type       description
        -------------------------------------------------------------------------
        name          string     name of the file
        path          string     unique identifier for this file entity for this
                                 project and storage provider. may not end with '/'
        materialized  string     the full path of the file relative to the storage
                                 root.  may not end with '/'
        kind          string     "file"
        etag          string     etag - http caching identifier w/o wrapping quotes
        modified      timestamp  last modified timestamp - format depends on provider
        contentType   string     MIME-type when available
        provider      string     id of provider e.g. "osfstorage", "s3", "googledrive".
                                 equivalent to addon_short_name on the OSF
        size          integer    size of file in bytes
        extra         object     may contain additional data beyond what's described here,
                                 depending on the provider
          version     integer    version number of file. will be 1 on initial upload
          downloads   integer    count of the number times the file has been downloaded
          hashes      object
            md5       string     md5 hash of file
            sha256    string     SHA-256 hash of file

    ####Folder Entity

        name          type    description
        ----------------------------------------------------------------------
        name          string  name of the folder
        path          string  unique identifier for this folder entity for this
                              project and storage provider. must end with '/'
        materialized  string  the full path of the folder relative to the storage
                              root.  must end with '/'
        kind          string  "folder"
        etag          string  etag - http caching identifier w/o wrapping quotes
        extra         object  varies depending on provider

    ##Provider Attributes

    `type` is "files"

        name      type    description
        ---------------------------------------------------------------------------------
        name      string  name of the provider
        kind      string  type of this file/folder.  always "folder"
        path      path    relative path of this folder within the provider filesys. always "/"
        node      string  node this provider belongs to
        provider  string  provider id, same as "name"

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    <!--- Copied from FileDetail.Actions -->

    ###Create Subfolder (*folders*)

        Method:       PUT
        URL:          /links/new_folder
        Query Params: ?kind=folder&name={new_folder_name}
        Body:         <empty>
        Success:      201 Created + new folder representation

    You can create a subfolder of an existing folder by issuing a PUT request against the `new_folder` link.  The
    `?kind=folder` portion of the query parameter is already included in the `new_folder` link.  The name of the new
    subfolder should be provided in the `name` query parameter.  The response will contain a [WaterButler folder
    entity](#folder-entity).  If a folder with that name already exists in the parent directory, the server will return
    a 409 Conflict error response.

    ###Upload New File (*folders*)

        Method:       PUT
        URL:          /links/upload
        Query Params: ?kind=file&name={new_file_name}
        Body (Raw):   <file data (not form-encoded)>
        Success:      201 Created or 200 OK + new file representation

    To upload a file to a folder, issue a PUT request to the folder's `upload` link with the raw file data in the
    request body, and the `kind` and `name` query parameters set to `'file'` and the desired name of the file.  The
    response will contain a [WaterButler file entity](#file-entity) that describes the new file.  If a file with the
    same name already exists in the folder, it will be considered a new version.  In this case, the response will be a
    200 OK.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    #This Request/Response

    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        ContributorOrPublic,
        ExcludeRetractions,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.NODE_FILE_READ]
    required_write_scopes = [CoreScopes.NODE_FILE_WRITE]

    serializer_class = NodeProviderSerializer
    view_category = 'nodes'
    view_name = 'node-providers'

    def get_provider_item(self, provider):
        return NodeProvider(provider, self.get_node())

    def get_queryset(self):
        return [
            self.get_provider_item(addon.config.short_name)
            for addon
            in self.get_node().get_addons()
            if addon.config.has_hgrid_files
            and addon.complete
        ]

class NodeAlternativeCitationsList(JSONAPIBaseView, generics.ListCreateAPIView, NodeMixin):
    """List of alternative citations for a project.

    ##Actions

    ###Create Alternative Citation

        Method:         POST
        Body (JSON):    {
                            "data": {
                                "type": "citations",    # required
                                "attributes": {
                                    "name": {name},     # mandatory
                                    "text": {text}      # mandatory
                                }
                            }
                        }
        Success:        201 Created + new citation representation
    """

    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        AdminOrPublic,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope
    )

    required_read_scopes = [CoreScopes.NODE_CITATIONS_READ]
    required_write_scopes = [CoreScopes.NODE_CITATIONS_WRITE]

    serializer_class = NodeAlternativeCitationSerializer
    view_category = 'nodes'
    view_name = 'alternative-citations'

    def get_queryset(self):
        return self.get_node().alternative_citations

class NodeAlternativeCitationDetail(JSONAPIBaseView, generics.RetrieveUpdateDestroyAPIView, NodeMixin):
    """Details about an alternative citations for a project.

    ##Actions

    ###Update Alternative Citation

        Method:         PUT
        Body (JSON):    {
                            "data": {
                                "type": "citations",    # required
                                "id": {{id}}            # required
                                "attributes": {
                                    "name": {name},     # mandatory
                                    "text": {text}      # mandatory
                                }
                            }
                        }
        Success:        200 Ok + updated citation representation

    ###Delete Alternative Citation

        Method:         DELETE
        Success:        204 No content
    """

    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        AdminOrPublic,
        ReadOnlyIfRegistration,
        base_permissions.TokenHasScope
    )

    required_read_scopes = [CoreScopes.NODE_CITATIONS_READ]
    required_write_scopes = [CoreScopes.NODE_CITATIONS_WRITE]

    serializer_class = NodeAlternativeCitationSerializer
    view_category = 'nodes'
    view_name = 'alternative-citation-detail'

    def get_object(self):
        try:
            return self.get_node().alternative_citations.find(Q('_id', 'eq', str(self.kwargs['citation_id'])))[0]
        except IndexError:
            raise NotFound

    def perform_destroy(self, instance):
        self.get_node().remove_citation(get_user_auth(self.request), instance, save=True)

class NodeLogList(JSONAPIBaseView, generics.ListAPIView, NodeMixin, ODMFilterMixin):
    """List of Logs associated with a given Node. *Read-only*.

    <!--- Copied Description from LogList -->

    Paginated list of Logs ordered by their `date`. This includes the Logs of the specified Node as well as the logs of that Node's children that the current user has access to.

    Note that if an anonymous view_only key is being used, the user relationship will not be exposed.

    On the front end, logs show record and show actions done on the OSF. The complete list of loggable actions (in the format {identifier}: {description}) is as follows:

    * 'project_created': A Node is created
    * 'project_registered': A Node is registered
    * 'project_deleted': A Node is deleted
    * 'created_from': A Node is created using an existing Node as a template
    * 'pointer_created': A Pointer is created
    * 'pointer_forked': A Pointer is forked
    * 'pointer_removed': A Pointer is removed
    ---
    * 'made_public': A Node is made public
    * 'made_private': A Node is made private
    * 'tag_added': A tag is added to a Node
    * 'tag_removed': A tag is removed from a Node
    * 'edit_title': A Node's title is changed
    * 'edit_description': A Node's description is changed
    * 'updated_fields': One or more of a Node's fields are changed
    * 'external_ids_added': An external identifier is added to a Node (e.g. DOI, ARK)
    ---
    * 'contributor_added': A Contributor is added to a Node
    * 'contributor_removed': A Contributor is removed from a Node
    * 'contributors_reordered': A Contributor's position is a Node's biliography is changed
    * 'permissions_update': A Contributor's permissions on a Node are changed
    * 'made_contributor_visible': A Contributor is made bibliographically visible on a Node
    * 'made_contributor_invisible': A Contributor is made bibliographically invisible on a Node
    ---
    * 'wiki_updated': A Node's wiki is updated
    * 'wiki_deleted': A Node's wiki is deleted
    * 'wiki_renamed': A Node's wiki is renamed
    * 'made_wiki_public': A Node's wiki is made public
    * 'made_wiki_private': A Node's wiki is made private
    ---
    * 'addon_added': An add-on is linked to a Node
    * 'addon_removed': An add-on is unlinked from a Node
    * 'addon_file_moved': A File in a Node's linked add-on is moved
    * 'addon_file_copied': A File in a Node's linked add-on is copied
    * 'addon_file_renamed': A File in a Node's linked add-on is renamed
    * 'folder_created': A Folder is created in a Node's linked add-on
    * 'file_added': A File is added to a Node's linked add-on
    * 'file_updated': A File is updated on a Node's linked add-on
    * 'file_removed': A File is removed from a Node's linked add-on
    * 'file_restored': A File is restored in a Node's linked add-on
    ---
    * 'comment_added': A Comment is added to some item
    * 'comment_removed': A Comment is removed from some item
    * 'comment_updated': A Comment is updated on some item
    ---
    * 'embargo_initiated': An embargoed Registration is proposed on a Node
    * 'embargo_approved': A proposed Embargo of a Node is approved
    * 'embargo_cancelled': A proposed Embargo of a Node is cancelled
    * 'embargo_completed': A proposed Embargo of a Node is completed
    * 'retraction_initiated': A Retraction of a Registration is proposed
    * 'retraction_approved': A Retraction of a Registration is approved
    * 'retraction_cancelled': A Retraction of a Registration is cancelled
    * 'registration_initiated': A Registration of a Node is proposed
    * 'registration_approved': A proposed Registration is approved
    * 'registration_cancelled': A proposed Registration is cancelled
    ---
    * 'node_created': A Node is created (_deprecated_)
    * 'node_forked': A Node is forked (_deprecated_)
    * 'node_removed': A Node is dele (_deprecated_)

   ##Log Attributes

    <!--- Copied Attributes from LogList -->

    OSF Log entities have the "logs" `type`.

        name           type                   description
        ----------------------------------------------------------------------------
        date           iso8601 timestamp      timestamp of Log creation
        action         string                 Log action (see list above)

    ##Relationships

    ###Nodes

    A list of all Nodes this Log is added to.

    ###User

    The user who performed the logged action.

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    ##Query Params

    <!--- Copied Query Params from LogList -->

    Logs may be filtered by their `action` and `date`.

    #This Request/Response

    """

    serializer_class = NodeLogSerializer
    view_category = 'nodes'
    view_name = 'node-logs'

    required_read_scopes = [CoreScopes.NODE_LOG_READ]
    required_write_scopes = [CoreScopes.NULL]

    log_lookup_url_kwarg = 'node_id'

    ordering = ('-date', )

    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        ContributorOrPublic,
        base_permissions.TokenHasScope,
        ExcludeRetractions
    )

    def get_default_odm_query(self):
        auth = get_user_auth(self.request)
        query = self.get_node().get_aggregate_logs_query(auth)
        return query

    def get_queryset(self):
        queryset = NodeLog.find(self.get_query_from_request())
        return queryset


class NodeCommentsList(JSONAPIBaseView, generics.ListCreateAPIView, ODMFilterMixin, NodeMixin):
    """List of comments on a node. *Writeable*.

    Paginated list of comments ordered by their `date_created.` Each resource contains the full representation of the
    comment, meaning additional requests to an individual comment's detail view are not necessary.

    Note that if an anonymous view_only key is being used, the user relationship will not be exposed.

    ###Permissions

    Comments on public nodes are given read-only access to everyone. If the node comment-level is "private",
    only contributors have permission to comment. If the comment-level is "public" any logged-in OSF user can comment.
    Comments on private nodes are only visible to contributors and administrators on the parent node.

    ##Attributes

    OSF comment entities have the "comments" `type`.

        name           type               description
        ---------------------------------------------------------------------------------
        content        string             content of the comment
        date_created   iso8601 timestamp  timestamp that the comment was created
        date_modified  iso8601 timestamp  timestamp when the comment was last updated
        modified       boolean            has this comment been edited?
        deleted        boolean            is this comment deleted?

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    ###Create

        Method:        POST
        URL:           /links/self
        Query Params:  <none>
        Body (JSON):   {
                         "data": {
                           "type": "comments",   # required
                           "attributes": {
                             "content":       {content},        # mandatory
                           },
                           "relationships": {
                             "target": {
                               "data": {
                                  "type": {target type}         # mandatory
                                  "id": {target._id}            # mandatory
                               }
                             }
                           }
                         }
                       }
        Success:       201 CREATED + comment representation

    To create a comment on this node, issue a POST request against this endpoint. The comment target id and target type
    must be specified. To create a comment on the node overview page, the target `type` would be "nodes" and the `id`
    would be the node id. To reply to a comment on this node, the target `type` would be "comments" and the `id` would
    be the id of the comment to reply to. The `content` field is mandatory.

    If the comment creation is successful the API will return
    a 201 response with the representation of the new comment in the body. For the new comment's canonical URL, see the
    `/links/self` field of the response.

    ##Query Params

    + `filter[deleted]=True|False` -- filter comments based on whether or not they are deleted.

    The list of node comments includes deleted comments by default. The `deleted` field is a boolean and can be
    filtered using truthy values, such as `true`, `false`, `0`, or `1`. Note that quoting `true` or `false` in
    the query will cause the match to fail regardless.

    + `filter[date_created][comparison_operator]=YYYY-MM-DDTH:M:S` -- filter comments based on date created.

    Comments can also be filtered based on their `date_created` and `date_modified` fields. Possible comparison
    operators include 'gt' (greater than), 'gte'(greater than or equal to), 'lt' (less than) and 'lte'
    (less than or equal to). The date must be in the format YYYY-MM-DD and the time is optional.

    + `filter[target]=target_id` -- filter comments based on their target id.

    The list of comments can be filtered by target id. For example, to get all comments with target = project,
    the target_id would be the project_id.

    #This Request/Response
    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        CanCommentOrPublic,
        base_permissions.TokenHasScope,
        ExcludeRetractions
    )

    required_read_scopes = [CoreScopes.NODE_COMMENTS_READ]
    required_write_scopes = [CoreScopes.NODE_COMMENTS_WRITE]

    serializer_class = CommentSerializer
    view_category = 'nodes'
    view_name = 'node-comments'

    ordering = ('-date_created', )  # default ordering

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        return Q('target', 'eq', self.get_node())

    def get_queryset(self):
        return Comment.find(self.get_query_from_request())

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CommentCreateSerializer
        else:
            return CommentSerializer

    # overrides ListCreateAPIView
    def get_parser_context(self, http_request):
        """
        Tells parser that we are creating a relationship
        """
        res = super(NodeCommentsList, self).get_parser_context(http_request)
        res['is_relationship'] = True
        return res

    def perform_create(self, serializer):
        node = self.get_node()
        serializer.validated_data['user'] = self.request.user
        serializer.validated_data['node'] = node
        serializer.save()
