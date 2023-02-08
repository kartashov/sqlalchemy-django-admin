# Django Admin for SQLAlchemy

## How to use it
1. Install 
```
pip install sqlalchemy-django-admin
```

2. Add it to `INSTALLED_APPS`
```python
INSTALLED_APPS = [
    ...
    'sqlalchemy_django_admin',
]
```

3. Register table in admin
```python
from django.contrib import admin
from sqlalchemy_django_admin import table_as_model


admin.site.register(table_as_model(your_sqlalchemy_table))
```

There's also the other `ModelAdmin` with extra defined default behaviour.
```python
from django.contrib import admin
from sqlalchemy_django_admin.admin import ModelAdmin
from sqlalchemy_django_admin import table_as_model


@admin.register(table_as_model(your_sqlalchemy_table))
class YourAdmin(ModelAdmin):

    readonly_fields = ('field_x',)
```


## Supported functions
*TODO*

## Known issues
1. `on_update` is not supported.
2. For tables without primary key you must define it explicitly while converting.
If there is no suitable unique column, `MultipleObjectsReturned` exception 
and other inconsistencies can occur.
3. Only small scope of SQLAlchemy's defaults is supported:
   - [scalar](https://docs.sqlalchemy.org/en/14/core/defaults.html#scalar-defaults)
   - [python executed functions](https://docs.sqlalchemy.org/en/14/core/defaults.html#python-executed-functions)
   - enum
4. Only nullable fields in admin forms are not required by default (`blank=True`).
5. Foreign keys work correctly only if there is **exactly one** foreign key on the given column.
6. The lib was only tested for `types.DateTime(timezone=True)` and wasn't tested for naive datetimes.
7. Integrity errors that occur on db level are not caught and lead to 500.
8. Now there is no way to define django fields on your own – they're always created automatically.
