import datetime
import decimal
import json
import uuid

from base64 import b64encode, b64decode

from django.db import DEFAULT_DB_ALIAS, router, models
from django.db.models import signals
from django.db.models.sql.where import WhereNode, AND
from django.utils.duration import duration_iso_string
from django.utils.functional import Promise
from django.utils.timezone import is_aware


class ForeignKey(models.ForeignKey):

    def get_attname(self):
        return self.db_column or super().get_attname()


class RawJSONField(models.JSONField):
    """
    Json field that works with `json` type columns in admin forms
    instead of `jsonb` for PostgreSQL
    """
    def db_type(self, connection):
        return 'json'

    def from_db_value(self, value, expression, connection):
        try:
            return super().from_db_value(value, expression, connection)
        except TypeError:
            return value


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

    def __init__(self, fields: list[models.Field], **kwargs):
        self.fields = fields
        self.columns = [field.db_column or field.name for field in fields]
        super().__init__(primary_key=True, **kwargs)

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

        # FIXME: удаление не работает, как полагается
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
        if isinstance(value, datetime.datetime):
            result = value.isoformat()
            if value.microsecond:
                result = result[:23] + result[26:]
            if result.endswith('+00:00'):
                result = result[:-6] + 'Z'
            return result
        elif isinstance(value, datetime.date):
            return value.isoformat()
        elif isinstance(value, datetime.time):
            if is_aware(value):
                raise ValueError("JSON can't represent timezone-aware times.")
            result = value.isoformat()
            if value.microsecond:
                result = result[:12]
            return result
        elif isinstance(value, datetime.timedelta):
            return duration_iso_string(value)
        elif isinstance(value, (decimal.Decimal, uuid.UUID, Promise)):
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

        lookup_classes = [
            field.get_lookup('exact')
            for field in fields
        ]

        lookups = [
            lookup_class(field.get_col(self.lhs.alias), self.rhs[column])
            for lookup_class, field, column in zip(
                lookup_classes, fields, self.lhs.field.columns
            )
        ]

        value_constraint = WhereNode()
        for lookup in lookups:
            value_constraint.add(lookup, AND)
        return value_constraint.as_sql(compiler, connection)
