from django.contrib import admin
from django.db import transaction

from .models import RawData, ProcessMap
from .forms import RawDataForm


@admin.register(RawData)
class RawDataAdmin(admin.ModelAdmin):
    form = RawDataForm

    def save_model(self, request, obj, form, change):
        pairs = form.process_map_pairs

        with transaction.atomic():
            super().save_model(request, obj, form, change)

            if pairs is not None:
                for family, station in pairs:
                    ProcessMap.objects.get_or_create(
                        family=family,
                        station_type=station,
                        defaults={'operation_id':0},
                    )
    ## When saving Raw Data through the admin, the Process Map update is automatically
    ## performed, rather than checking and updating through the view.
    ## Only the admin is meant for uploading new Raw Data, that being the site owner.

    
admin.site.register(ProcessMap)