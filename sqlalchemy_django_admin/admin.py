from django.contrib import admin
from django.db.models import BooleanField

from sqlalchemy_django_admin.fields import CompositeKeyField


class ModelAdmin(admin.ModelAdmin):

    @property
    def _model_fields(self):
        return [f for f in self.opts.get_fields() if f.concrete]

    @property
    def raw_id_fields(self):
        return [f.name for f in self.opts.get_fields() if f.is_relation]

    def get_list_display(self, request):
        # TODO: move to settings
        if self.list_display == ('__str__',):
            return [f.db_column if f.is_relation else f.name for f in self._model_fields[:4]]
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
        And currently auto fields are not supported at all.
        """
        fields = super().get_fields(request, obj)
        if not obj:
            return fields
        primary_fields = {self.opts.pk.name}
        if isinstance(self.opts.pk, CompositeKeyField):
            primary_fields = {field.name for field in self.opts.pk.fields}
        return [field for field in fields if field not in primary_fields]
