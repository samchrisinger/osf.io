from rest_framework import serializers as ser

from modularodm.exceptions import ValidationValueError

from api.base.exceptions import InvalidModelValueError
from api.base.serializers import AllowMissing
from website.models import User

from api.base.serializers import (
    JSONAPISerializer, LinksField, RelationshipField, DevOnly, IDField, TypeField, DoNotRelateWhenAnonymous
)
from api.base.utils import add_dev_only_items


class UserSerializer(DoNotRelateWhenAnonymous, JSONAPISerializer):
    filterable_fields = frozenset([
        'full_name',
        'given_name',
        'middle_names',
        'family_name',
        'id'
    ])
    non_anonymized_fields = ['type']
    id = IDField(source='_id', read_only=True)
    type = TypeField()
    full_name = ser.CharField(source='fullname', required=True, label='Full name', help_text='Display name used in the general user interface')
    given_name = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    middle_names = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    family_name = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    suffix = ser.CharField(required=False, allow_blank=True, help_text='For bibliographic citations')
    date_registered = ser.DateTimeField(read_only=True)

    # Social Fields are broken out to get around DRF complex object bug and to make API updating more user friendly.
    gitHub = DevOnly(AllowMissing(ser.CharField(required=False, source='social.github',
                                                          allow_blank=True, help_text='GitHub Handle'), required=False, source='social.github'))
    scholar = DevOnly(AllowMissing(ser.CharField(required=False, source='social.scholar',
                                                           allow_blank=True, help_text='Google Scholar Account'), required=False, source='social.scholar'))
    personal_website = DevOnly(AllowMissing(ser.URLField(required=False, source='social.personal',
                                                                   allow_blank=True, help_text='Personal Website'), required=False, source='social.personal'))
    twitter = DevOnly(AllowMissing(ser.CharField(required=False, source='social.twitter',
                                                           allow_blank=True, help_text='Twitter Handle'), required=False, source='social.twitter'))
    linkedIn = DevOnly(AllowMissing(ser.CharField(required=False, source='social.linkedIn',
                                                            allow_blank=True, help_text='LinkedIn Account'), required=False, source='social.linkedIn'))
    impactStory = DevOnly(AllowMissing(ser.CharField(required=False, source='social.impactStory',
                                                               allow_blank=True, help_text='ImpactStory Account'), required=False, source='social.impactStory'))
    orcid = DevOnly(AllowMissing(ser.CharField(required=False, source='social.orcid',
                                                         allow_blank=True, help_text='ORCID'), required=False, source='social.orcid'))
    researcherId = DevOnly(AllowMissing(ser.CharField(required=False, source='social.researcherId',
                                                                allow_blank=True, help_text='ResearcherId Account'), required=False, source='social.researcherId'))

    links = LinksField(
        add_dev_only_items({
            'html': 'absolute_url',
        }, {
            'profile_image': 'profile_image_url',
        })
    )

    nodes = RelationshipField(
        related_view='users:user-nodes',
        related_view_kwargs={'user_id': '<pk>'},
    )

    class Meta:
        type_ = 'users'

    def absolute_url(self, obj):
        if obj is not None:
            return obj.absolute_url
        return None

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
        try:
            instance.save()
        except ValidationValueError as e:
            raise InvalidModelValueError(detail=e.message)
        return instance


class UserDetailSerializer(UserSerializer):
    """
    Overrides UserSerializer to make id required.
    """
    id = IDField(source='_id', required=True)
