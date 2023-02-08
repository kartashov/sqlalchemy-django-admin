from django.db import models

from .composite import CompositeKey, CompositeKeyField


class ForeignKey(models.ForeignKey):

    def get_attname(self):
        return self.db_column or super().get_attname()


class RawJSONField(models.JSONField):
    """
    Json field that works with `json` type columns in admin forms
    instead of `jsonb` for PostgreSQL
    """
    # Only null is invalid when blank=False
    empty_values = [None]

    def db_type(self, connection):
        return 'json'

    def from_db_value(self, value, expression, connection):
        try:
            return super().from_db_value(value, expression, connection)
        except TypeError:
            return value
