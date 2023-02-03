from django.db.models import JSONField


class RawJSONField(JSONField):
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
