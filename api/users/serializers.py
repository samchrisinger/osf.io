from rest_framework import serializers as ser
from api.base.serializers import AllowMissing
from website.models import User

from api.base.serializers import (
    JSONAPISerializer, LinksField, JSONAPIHyperlinkedIdentityField, DevOnly, IDField, TypeField
)
from api.base.utils import add_dev_only_items


class UserSerializer(JSONAPISerializer):
    filterable_fields = frozenset([
        'full_name',
        'given_name',
        'middle_names',
        'family_name',
        'id'
    ])
    id = IDField(source='_id', read_only=True)
    type = TypeField()
    full_name = ser.CharField(source='fullname', required=True, label='Full name', help_text='Display name used in the general user interface')
    given_name = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    middle_names = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    family_name = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    suffix = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    date_registered = ser.DateTimeField(read_only=True)

    # Social Fields are broken out to get around DRF complex object bug and to make API updating more user friendly.
    gitHub = DevOnly(ser.CharField(required=False, label='GitHub', source='social.github', allow_blank=True, help_text='GitHub Handle'))
    scholar = DevOnly(ser.CharField(required=False, source='social.scholar', allow_blank=True, help_text='Google Scholar Account'))
    personal_website = DevOnly(ser.URLField(required=False, source='social.personal', allow_blank=True, help_text='Personal Website'))
    twitter = DevOnly(ser.CharField(required=False, source='social.twitter', allow_blank=True, help_text='Twitter Handle'))
    linkedIn = DevOnly(ser.CharField(required=False, source='social.linkedIn', allow_blank=True, help_text='LinkedIn Account'))
    impactStory = DevOnly(ser.CharField(required=False, source='social.impactStory', allow_blank=True, help_text='ImpactStory Account'))
    orcid = DevOnly(ser.CharField(required=False, label='ORCID', source='social.orcid', allow_blank=True, help_text='ORCID'))
    researcherId = DevOnly(ser.CharField(required=False, label='ResearcherID', source='social.researcherId', allow_blank=True, help_text='ResearcherId Account'))

    links = LinksField(
        add_dev_only_items({
            'html': 'absolute_url',
        }, {
            'profile_image': 'profile_image_url',
        })
    )
    nodes = JSONAPIHyperlinkedIdentityField(view_name='users:user-nodes', lookup_field='pk', lookup_url_kwarg='user_id',
                                             link_type='related')

    class Meta:
        type_ = 'users'

    def absolute_url(self, obj):
        return obj.absolute_url

    def profile_image_url(self, user):
        size = self.context['request'].query_params.get('profile_image_size')
        return user.profile_image_url(size=size)

    def update(self, instance, validated_data):
        assert isinstance(instance, User), 'instance must be a User'
        for attr, value in validated_data.items():
            if 'social' == attr:
                for key, val in value.items():
                    instance.social[key] = val
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance


class UserDetailSerializer(UserSerializer):
    """
    Overrides UserSerializer to make id required.
    """
    id = IDField(source='_id', required=True)
