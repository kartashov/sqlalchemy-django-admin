from django.contrib import admin
from django.db.models import BooleanField


class ModelAdmin(admin.ModelAdmin):

    @property
    def _model_fields(self):
        return [f for f in self.model._meta.get_fields() if f.concrete]

    @property
    def raw_id_fields(self):
        return [f.name for f in self.model._meta.get_fields() if f.is_relation]

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
