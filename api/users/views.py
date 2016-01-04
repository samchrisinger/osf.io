from rest_framework import generics
from rest_framework import permissions as drf_permissions
from rest_framework.exceptions import NotAuthenticated
from django.contrib.auth.models import AnonymousUser

from modularodm import Q

from framework.auth.core import Auth
from framework.auth.oauth_scopes import CoreScopes

from website.models import User, Node

from api.base import permissions as base_permissions
from api.base.utils import get_object_or_error
from api.base.views import JSONAPIBaseView
from api.base.filters import ODMFilterMixin
from api.nodes.serializers import NodeSerializer
from api.registrations.serializers import RegistrationSerializer

from .serializers import UserSerializer, UserDetailSerializer
from .permissions import ReadOnlyOrCurrentUser


class UserMixin(object):
    """Mixin with convenience methods for retrieving the current node based on the
    current URL. By default, fetches the user based on the user_id kwarg.
    """

    serializer_class = UserSerializer
    user_lookup_url_kwarg = 'user_id'

    def get_user(self, check_permissions=True):
        key = self.kwargs[self.user_lookup_url_kwarg]
        current_user = self.request.user

        if key == 'me':
            if isinstance(current_user, AnonymousUser):
                raise NotAuthenticated
            else:
                return self.request.user

        obj = get_object_or_error(User, key, 'user')
        if check_permissions:
            # May raise a permission denied
            self.check_object_permissions(self.request, obj)
        return obj


class UserList(JSONAPIBaseView, generics.ListAPIView, ODMFilterMixin):
    """List of users registered on the OSF. *Read-only*.

    Paginated list of users ordered by the date they registered.  Each resource contains the full representation of the
    user, meaning additional requests to an individual user's detail view are not necessary.

    Note that if an anonymous view_only key is being used, user information will not be serialized, and the id will be
    an empty string. Relationships to a user object will not show in this case, either.

    The subroute [`/me/`](me/) is a special endpoint that always points to the currently logged-in user.

    ##User Attributes

    <!--- Copied Attributes From UserDetail -->

    OSF User entities have the "users" `type`.

        name               type               description
        ----------------------------------------------------------------------------------------
        full_name          string             full name of the user; used for display
        given_name         string             given name of the user; for bibliographic citations
        middle_names       string             middle name of user; for bibliographic citations
        family_name        string             family name of user; for bibliographic citations
        suffix             string             suffix of user's name for bibliographic citations
        date_registered    iso8601 timestamp  timestamp when the user's account was created

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    *None*.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    Users may be filtered by their `id`, `full_name`, `given_name`, `middle_names`, or `family_name`.

    + `profile_image_size=<Int>` -- Modifies `/links/profile_image_url` of the user entities so that it points to
    the user's profile image scaled to the given size in pixels.  If left blank, the size depends on the image provider.

    #This Request/Response

    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.USERS_READ]
    required_write_scopes = [CoreScopes.USERS_WRITE]

    serializer_class = UserSerializer

    ordering = ('-date_registered')
    view_category = 'users'
    view_name = 'user-list'

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        return (
            Q('is_registered', 'eq', True) &
            Q('is_merged', 'ne', True) &
            Q('date_disabled', 'eq', None)
        )

    # overrides ListAPIView
    def get_queryset(self):
        # TODO: sort
        query = self.get_query_from_request()
        return User.find(query)


class UserDetail(JSONAPIBaseView, generics.RetrieveUpdateAPIView, UserMixin):
    """Details about a specific user. *Writeable*.

    The User Detail endpoint retrieves information about the user whose id is the final part of the path.  If `me`
    is given as the id, the record of the currently logged-in user will be returned.  The returned information includes
    the user's bibliographic information and the date the user registered.

    Note that if an anonymous view_only key is being used, user information will not be serialized, and the id will be
    an empty string. Relationships to a user object will not show in this case, either.

    ##Attributes

    OSF User entities have the "users" `type`.

        name               type               description
        ----------------------------------------------------------------------------------------
        full_name          string             full name of the user; used for display
        given_name         string             given name of the user; for bibliographic citations
        middle_names       string             middle name of user; for bibliographic citations
        family_name        string             family name of user; for bibliographic citations
        suffix             string             suffix of user's name for bibliographic citations
        date_registered    iso8601 timestamp  timestamp when the user's account was created

    ##Relationships

    ###Nodes

    A list of all nodes the user has contributed to.  If the user id in the path is the same as the logged-in user, all
    nodes will be visible.  Otherwise, you will only be able to see the other user's publicly-visible nodes.

    ##Links

        self:               the canonical api endpoint of this user
        html:               this user's page on the OSF website
        profile_image_url:  a url to the user's profile image

    ##Actions

    ###Update

        Method:        PUT / PATCH
        URL:           /links/self
        Query Params:  <none>
        Body (JSON):   {
                         "data": {
                           "type": "users",   # required
                           "id":   {user_id}, # required
                           "attributes": {
                             "full_name":    {full_name},    # mandatory
                             "given_name":   {given_name},   # optional
                             "middle_names": {middle_names}, # optional
                             "family_name":  {family_name},  # optional
                             "suffix":       {suffix}        # optional
                           }
                         }
                       }
        Success:       200 OK + node representation

    To update your user profile, issue a PUT request to either the canonical URL of your user resource (as given in
    `/links/self`) or to `/users/me/`.  Only the `full_name` attribute is required.  Unlike at signup, the given, middle,
    and family names will not be inferred from the `full_name`.  Currently, only `full_name`, `given_name`,
    `middle_names`, `family_name`, and `suffix` are updateable.

    A PATCH request issued to this endpoint will behave the same as a PUT request, but does not require `full_name` to
    be set.

    **NB:** If you PUT/PATCH to the `/users/me/` endpoint, you must still provide your full user id in the `id` field of
    the request.  We do not support using the `me` alias in request bodies at this time.

    ##Query Params

    + `profile_image_size=<Int>` -- Modifies `/links/profile_image_url` so that it points the image scaled to the given
    size in pixels.  If left blank, the size depends on the image provider.

    #This Request/Response

    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        ReadOnlyOrCurrentUser,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.USERS_READ]
    required_write_scopes = [CoreScopes.USERS_WRITE]
    view_category = 'users'
    view_name = 'user-detail'

    serializer_class = UserDetailSerializer

    # overrides RetrieveAPIView
    def get_object(self):
        return self.get_user()

    # overrides RetrieveUpdateAPIView
    def get_serializer_context(self):
        # Serializer needs the request in order to make an update to privacy
        context = JSONAPIBaseView.get_serializer_context(self)
        context['request'] = self.request
        return context


class UserNodes(JSONAPIBaseView, generics.ListAPIView, UserMixin, ODMFilterMixin):
    """List of nodes that the user contributes to. *Read-only*.

    Paginated list of nodes that the user contributes to.  Each resource contains the full representation of the node,
    meaning additional requests to an individual node's detail view are not necessary. If the user id in the path is the
    same as the logged-in user, all nodes will be visible.  Otherwise, you will only be able to see the other user's
    publicly-visible nodes.  The special user id `me` can be used to represent the currently logged-in user.

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
        fork           boolean            is this project a fork?
        registration   boolean            has this project been registered?
        fork           boolean            is this node a fork of another node?
        dashboard      boolean            is this node visible on the user dashboard?
        public         boolean            has this node been made publicly-visible?

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    *None*.

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
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.USERS_READ, CoreScopes.NODE_BASE_READ]
    required_write_scopes = [CoreScopes.USERS_WRITE, CoreScopes.NODE_BASE_WRITE]

    serializer_class = NodeSerializer
    view_category = 'users'
    view_name = 'user-nodes'

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        user = self.get_user()
        return (
            Q('contributors', 'eq', user) &
            Q('is_folder', 'ne', True) &
            Q('is_deleted', 'ne', True)
        )

    # overrides ListAPIView
    def get_queryset(self):
        current_user = self.request.user
        if current_user.is_anonymous():
            auth = Auth(None)
        else:
            auth = Auth(current_user)
        query = self.get_query_from_request()
        raw_nodes = Node.find(self.get_default_odm_query() & query)
        nodes = [each for each in raw_nodes if each.is_public or each.can_view(auth)]
        return nodes


class UserRegistrations(UserNodes):
    """List of registrations that the user contributes to. *Read-only*.

    Paginated list of registrations that the user contributes to.  Each resource contains the full representation of the
    registration, meaning additional requests to an individual registration's detail view are not necessary. If the user
    id in the path is the same as the logged-in user, all nodes will be visible.  Otherwise, you will only be able to
    see the other user's publicly-visible nodes.  The special user id `me` can be used to represent the currently
    logged-in user. Retracted registrations will display a limited number of fields, namely, title, description,
    date_created, registration, retracted, date_registered, retraction_justification, and registration supplement.

    ##Registration Attributes

    <!--- Copied Attributes from RegistrationList -->

    Registrations have the "registrations" `type`.

        name                            type               description
        -------------------------------------------------------------------------------------------------------
        title                           string             title of the registered project or component
        description                     string             description of the registered node
        category                        string             node category, must be one of the allowed values
        date_created                    iso8601 timestamp  timestamp that the node was created
        date_modified                   iso8601 timestamp  timestamp when the node was last updated
        tags                            array of strings   list of tags that describe the registered node
        fork                            boolean            is this project a fork?
        registration                    boolean            has this project been registered?
        dashboard                       boolean            is this registered node visible on the user dashboard?
        public                          boolean            has this registration been made publicly-visible?
        retracted                       boolean            has this registration been retracted?
        date_registered                 iso8601 timestamp  timestamp that the registration was created
        retraction_justification        string             reasons for retracting the registration
        pending_retraction              boolean            is this registration pending retraction?
        pending_registration_approval   boolean            is this registration pending approval?
        pending_embargo                 boolean            is this registration pending an embargo?
        registered_meta                 dictionary         registration supplementary information
        registration_supplement         string             registration template


    ##Relationships

    ###Registered from

    The registration is branched from this node.

    ###Registered by

    The registration was initiated by this user.

    ###Other Relationships

    See documentation on registered_from detail view.  A registration has many of the same properties as a node.

    ##Links

    See the [JSON-API spec regarding pagination](http://jsonapi.org/format/1.0/#fetching-pagination).

    ##Actions

    *None*.

    ##Query Params

    + `page=<Int>` -- page number of results to view, default 1

    + `filter[<fieldname>]=<Str>` -- fields and values to filter the search results on.

    <!--- Copied Query Params from NodeList -->

    Registrations may be filtered by their `title`, `category`, `description`, `public`, or `tags`.  `title`, `description`,
    and `category` are string fields and will be filtered using simple substring matching.  `public` is a boolean and
    can be filtered using truthy values, such as `true`, `false`, `0`, or `1`.  Note that quoting `true` or `false` in
    the query will cause the match to fail regardless.  `tags` is an array of simple strings.

    #This Request/Response

    """
    required_read_scopes = [CoreScopes.USERS_READ, CoreScopes.NODE_REGISTRATIONS_READ]
    required_write_scopes = [CoreScopes.USERS_WRITE, CoreScopes.NODE_REGISTRATIONS_WRITE]

    serializer_class = RegistrationSerializer
    view_category = 'users'
    view_name = 'user-registrations'

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        user = self.get_user()
        return (
            Q('contributors', 'eq', user) &
            Q('is_folder', 'ne', True) &
            Q('is_deleted', 'ne', True) &
            Q('is_registration', 'eq', True)
        )
