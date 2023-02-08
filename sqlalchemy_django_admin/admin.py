from django.contrib import admin
from django.db.models import Field, BooleanField

from sqlalchemy_django_admin.fields import CompositeKeyField


# TODO: move to settings
DEFAULT_COLUMNS_COUNT = 4


class ModelAdmin(admin.ModelAdmin):
    """
    Adds some changes to default behavior of admin.ModelAdmin:
    1. Foreign keys are automatically added to `raw_id_fields`
       to prevent loading of all related objects on the form page.
    2. If `list_display` is not defined the first DEFAULT_COLUMNS_COUNT fields
       are shown on the list page instead of `__str__()` of the model.
    3. If `search_fields` is not defined it will search by the exact value
       of the primary key. Doesn't work for composite primary keys.
    4. If `list_filter` is not defined it will be filled with fields that have choices
       and fields of boolean type.
    5. All primary key fields (except auto fields) by default are shown on creation page
       but hidden on edition page.
    """
    @property
    def _model_fields(self) -> list[Field]:
        return [f for f in self.opts.get_fields() if f.concrete]

    @property
    def _primary_field_names(self) -> set[str]:
        if isinstance(self.opts.pk, CompositeKeyField):
            return {field.name for field in self.opts.pk.fields}
        return {self.opts.pk.name}

    @property
    def raw_id_fields(self):
        return [f.name for f in self.opts.get_fields() if f.is_relation]

    def get_list_display(self, request):
        if self.list_display == ('__str__',):
            return tuple(
                f.db_column if f.is_relation else f.name
                for f in self._model_fields[:DEFAULT_COLUMNS_COUNT]
            )
        return super().get_list_display(request)

    def get_search_fields(self, request):
        if not self.search_fields:
            return ['=pk']
        return super().get_search_fields(request)

    def get_list_filter(self, request):
        if not self.list_filter:
            return [f.name for f in self._model_fields if f.choices or isinstance(f, BooleanField)]
        return super().get_list_filter(request)

    def get_fields(self, request, obj=None):
        """
        In addition to default behavior, removes from edition page all primary key fields.
        PK has to be immutable, because if you change it,
        Django will just create a new object on .save()

        Django has similar model field parameter for this – `editable=False`,
        but it also removes a field from creation page.
        Thus it can't be automatically used for fields which must be set manually.
        """
        fields = super().get_fields(request, obj)
        if not obj:
            return fields
        return [field for field in fields if field not in self._primary_field_names]
