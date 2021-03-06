from rest_framework import serializers as ser

from api.base.serializers import JSONAPISerializer, LinksField, JSONAPIListField

class TaxonomyField(ser.Field):
    def to_representation(self, obj):
        if obj is not None:
            return {'id': obj._id,
                    'text': obj.text}
        return None

    def to_internal_value(self, data):
        return data

class TaxonomySerializer(JSONAPISerializer):
    filterable_fields = frozenset([
        'text',
        'parents',
        'id'
    ])
    id = ser.CharField(source='_id', required=True)
    text = ser.CharField(max_length=200)
    parents = JSONAPIListField(child=TaxonomyField())
    child_count = ser.IntegerField()

    links = LinksField({
        'parents': 'get_parent_urls',
        'self': 'get_absolute_url',
    })

    def get_parent_urls(self, obj):
        return [p.get_absolute_url() for p in obj.parents]

    def get_absolute_url(self, obj):
        return obj.get_absolute_url()

    class Meta:
        type_ = 'taxonomies'
