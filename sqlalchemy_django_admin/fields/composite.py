import decimal
import json
import uuid

from base64 import b64encode, b64decode

from django.db import DEFAULT_DB_ALIAS, router, models
from django.db.models import signals
from django.db.models.sql.where import WhereNode, AND
from django.utils.functional import Promise


class CompositeKey(dict):

    @staticmethod
    def encode(value: dict) -> str:
        return b64encode(json.dumps(value).encode('utf-8')).decode('utf-8')

    @staticmethod
    def decode(value: str) -> dict:
        return json.loads(b64decode(value.encode('utf-8')).decode('utf-8'))

    def to_json_string(self):
        return json.dumps(self)

    def __str__(self):
        return self.encode(self)

    def __hash__(self):
        return hash(tuple(self[key] for key in sorted(self.keys())))


class CompositeKeyField(models.AutoField):

    SUPPORTED_SUBFIELD_TYPES = (
        models.BooleanField,
        models.CharField,
        models.DecimalField,
        models.IntegerField,
        models.TextField,
        models.UUIDField,
        # We rely on foreign key being used only
        # to refer columns of supported types
        models.ForeignKey,
    )

    def __init__(self, fields: list[models.Field], **kwargs):
        for field in fields:
            self._validate_field(field)
        self.fields = fields
        self.columns = [field.db_column or field.name for field in fields]
        super().__init__(primary_key=True, **kwargs)

    def _validate_field(self, field: models.Field):
        if not isinstance(field, self.SUPPORTED_SUBFIELD_TYPES):
            raise TypeError(
                f'{field.name}: {field.get_internal_type()} cannot be used '
                f'as a subfield for {self.__class__.__name__}'
            )

    def contribute_to_class(self, cls, name, private_only=False):
        self.set_attributes_from_name(name)
        self.model = cls
        self.concrete = False
        self.editable = False
        self.column = self.columns[0]  # for default order_by
        cls._meta.add_field(self, private=True)
        cls._meta.setup_pk(self)

        if not getattr(cls, self.attname, None):
            setattr(cls, self.attname, self)

        def delete(inst, using=None, keep_parents=False):
            using = using or router.db_for_write(self.model, instance=inst)

            signals.pre_delete.send(
                sender=cls, instance=inst, using=using
            )

            query = cls._default_manager.filter(**self.__get__(inst))
            query._raw_delete(using)

            for column in self.columns:
                setattr(inst, column, None)

            signals.post_delete.send(
                sender=cls, instance=inst, using=using
            )

        cls.delete = delete

    def get_prep_value(self, value):
        return self.to_python(value)

    def to_python(self, value):
        if value is None or isinstance(value, CompositeKey):
            return value
        return CompositeKey(CompositeKey.decode(value))

    def to_json(self, value):
        if isinstance(value, (decimal.Decimal, uuid.UUID, Promise)):
            return str(value)
        return value

    def bulk_related_objects(self, objs, using=DEFAULT_DB_ALIAS):
        return []

    def __get__(self, instance, cls=None):
        if instance is None:
            return self

        return CompositeKey({
            column: self.to_json(self.model._meta.get_field(column).value_from_object(instance))
            for column in self.columns
        })

    def __set__(self, instance, value):
        pass


@CompositeKeyField.register_lookup
class Exact(models.Lookup):

    lookup_name = 'exact'

    def as_sql(self, compiler, connection):
        fields = [
            self.lhs.field.model._meta.get_field(column)
            for column in self.lhs.field.columns
        ]
        lookup_classes = [field.get_lookup('exact') for field in fields]
        lookups = [
            lookup_class(field.get_col(self.lhs.alias), self.rhs[column])
            for lookup_class, field, column in zip(lookup_classes, fields, self.lhs.field.columns)
        ]
        value_constraint = WhereNode()
        for lookup in lookups:
            value_constraint.add(lookup, AND)

        return value_constraint.as_sql(compiler, connection)
