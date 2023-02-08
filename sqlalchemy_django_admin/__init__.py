import logging

from enum import Enum
from functools import partial

from django.db import models
from sqlalchemy import Table, Column, types
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy_django_admin import fields


logger = logging.getLogger(__name__)


SA_TYPE_TO_MODEL = {
    types.String: models.CharField,
    types.Integer: models.IntegerField,
    types.DateTime: models.DateTimeField,
    types.Date: models.DateField,
    types.DECIMAL: models.DecimalField,
    types.Boolean: models.BooleanField,
    types.BigInteger: models.BigIntegerField,
    types.Text: models.TextField,
    types.Enum: models.CharField,
    UUID: models.UUIDField,
    # Use `json` field instead of `jsonb` for PostgreSQL
    types.JSON: fields.RawJSONField,
}


def _generate_model_name(table: Table):
    # Currently the name of the table is used as the corresponding model name
    return table.name


def _generate_model_verbose_name(table: Table):
    return ' '.join(part.capitalize() for part in table.name.split('_'))


def _convert_default(default):
    """
    Converts SQLAlchemy's default to Django supported default .
    Supports only small scope of SQLAlchemy's functionality:
    - https://docs.sqlalchemy.org/en/14/core/defaults.html#scalar-defaults
    - https://docs.sqlalchemy.org/en/14/core/defaults.html#python-executed-functions
    - enum
    """
    default = default and default.arg
    if default:
        if isinstance(default, Enum):
            default = default.value
        if callable(default):
            default = partial(default, None)
    return default


def _column_as_field(column: Column, pk_column: Column = None) -> models.Field:
    """
    Converts SQLAlchemy Column to Django Model Field
    """
    field_class = SA_TYPE_TO_MODEL[type(column.type)]
    kwargs = dict(
        name=column.name,
        null=column.nullable,
        default=_convert_default(column.default),
        # Primary key is calculated implicitly or can be set explicitly via `pk_column`.
        # Make sure `pk_column` refers to a column with unique values
        primary_key=column.primary_key or column is pk_column,
        # By default only nullable fields marked as not required
        blank=column.nullable,
    )

    if column is column.table.primary_key._autoincrement_column:
        field_class = models.AutoField

    if isinstance(column.type, types.Enum):
        kwargs['choices'] = [(i, i) for i in column.type.enums]

    if isinstance(column.type, types.String):
        if column.type.length:
            kwargs['max_length'] = column.type.length
        else:
            field_class = SA_TYPE_TO_MODEL[types.Text]

    if column.foreign_keys:
        # Trying to find the original table column which is referred from here.
        # Way to deal with composite fk (composite pk reference)
        foreign_key = None
        related_column = column
        while related_column.foreign_keys:
            # FIXME: what do we do if there are more than 1 fk?
            foreign_key, *_ = related_column.foreign_keys
            related_column = foreign_key.column

        # Making django foreign key only if the column refers
        # to the only primary key of related table
        is_unique_pk = (
            related_column.primary_key
            and len(related_column.table.primary_key.columns) == 1
        )
        if is_unique_pk:
            field_class = fields.ForeignKey
            related_model_name = _generate_model_name(related_column.table)
            kwargs |= dict(
                # Act as Django when name ends with `_id`
                name=column.name[:-3] if column.name.endswith('_id') else f'{column.name}_obj',
                to=f'sqlalchemy_django_admin.{related_model_name}',
                on_delete=models.PROTECT,
                to_field=related_column.name,
                db_column=column.name,
            )

    return field_class(**kwargs)


def table_as_model(
    table: Table,
    name: str = None,
    name_plural: str = None,
    str_template: str = None,
    pk_column: Column = None,
) -> type[models.Model]:
    """
    Converts SQLAlchemy Table to Django Model
    """
    model_name = _generate_model_name(table)
    model_verbose_name = name or _generate_model_verbose_name(table)
    model_fields = [_column_as_field(column, pk_column) for column in table.columns]

    # Deal with composite primary key
    primary_fields = [field for field in model_fields if field.primary_key]
    if len(primary_fields) > 1:
        for field in primary_fields:
            field.primary_key = False
        model_fields.append(fields.CompositeKeyField(primary_fields, name='composite_id'))

    class Meta:
        db_table = table.name
        managed = False
        app_label = 'sqlalchemy_django_admin'
        verbose_name = model_verbose_name
        verbose_name_plural = name_plural or f'{verbose_name}s'

    def __str__(obj):
        pk = obj.pk.to_json_string() if isinstance(obj.pk, fields.CompositeKey) else obj.pk
        template = str_template or '{model_verbose_name} object({pk})'
        return template.format(self=obj, pk=pk, model_verbose_name=model_verbose_name)

    attrs = {field.name: field for field in model_fields}
    attrs['Meta'] = Meta
    attrs['__str__'] = __str__
    attrs['__module__'] = 'sqlalchemy_django_admin'

    return type(model_name, (models.Model,), attrs)
