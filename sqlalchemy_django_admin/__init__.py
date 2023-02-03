from enum import Enum
from functools import partial

from django.db import models
from sqlalchemy import Table, Column, types
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy_django_admin import fields


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
    return ''.join(part.capitalize() for part in table.name.split('_'))


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


def _column_as_field(column: Column, pk_column: Column = None) -> tuple[str, models.Field]:
    """
    Converts SQLAlchemy Column to Django Model Field
    """
    name = column.name
    field_class = SA_TYPE_TO_MODEL[type(column.type)]
    kwargs = dict(
        null=column.nullable,
        default=_convert_default(column.default),
        # Primary key is calculated implicitly or can be set explicitly.
        # Make sure that pk_column refers to a column with unique values
        primary_key=column.primary_key or column is pk_column,
        # PK is not editable by default, except cases when it refers
        # to a column of another table
        editable=bool(not column.primary_key or column.foreign_keys),
        # By default only nullable fields marked as not required
        blank=column.nullable,
    )

    if isinstance(column.type, types.Enum):
        kwargs['choices'] = [(i, i) for i in column.type.enums]

    if isinstance(column.type, types.String):
        if column.type.length:
            kwargs['max_length'] = column.type.length
        else:
            field_class = SA_TYPE_TO_MODEL[types.Text]

    # FIXME: what do we do if there are more than 1 fk?
    if len(column.foreign_keys) == 1:
        # Trying to find the original table column which is referred from here.
        # Way to deal with composite fk (composite pk reference)
        foreign_key = None
        col = column
        while col.foreign_keys:
            foreign_key, *_ = col.foreign_keys
            col = foreign_key.column

        # FIXME: dirty hack
        name = name[:-3] if name.endswith('_id') else f'{name}_obj'

        field_class = models.ForeignKey
        related_model_name = _generate_model_name(foreign_key.column.table)
        kwargs |= dict(
            to=f'sqlalchemy_django_admin.{related_model_name}',
            on_delete=models.PROTECT,
            to_field=foreign_key.column.name,
            db_column=column.name,
        )

    return name, field_class(**kwargs)


def table_as_model(
    table: Table,
    name: str = None,
    name_plural: str = None,
    str_template: str = None,
    pk_column: Column = None,
) -> models.Model:
    """
    Converts SQLAlchemy Table to Django Model
    """
    model_name = _generate_model_name(table)
    attrs = dict(_column_as_field(column, pk_column) for column in table.columns)

    class Meta:
        db_table = table.name
        managed = False
        app_label = 'sqlalchemy_django_admin'
        verbose_name = name or model_name
        verbose_name_plural = name_plural or f'{verbose_name}s'

    def __str__(obj):
        return str_template.format(self=obj) if str_template else f'{model_name} object({obj.pk})'

    attrs['Meta'] = Meta
    attrs['__str__'] = __str__
    attrs['__module__'] = 'sqlalchemy_django_admin'

    return type(model_name, (models.Model,), attrs)
