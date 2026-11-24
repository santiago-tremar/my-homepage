from django.contrib import admin

from .models import RawData, ProcessMap

admin.site.register(RawData)
admin.site.register(ProcessMap)