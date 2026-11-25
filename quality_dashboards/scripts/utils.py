from quality_dashboards.models import RawData, ProcessMap

import pandas as pd

def get_family_selection(request):
    families = list(
        ProcessMap.objects
        .order_by('family')
        .values_list('family', flat=True)
        .distinct()
    )
    requested_family = request.GET.get('family')
    selected_family = (
        requested_family
        if requested_family in families
        else families[0] if families else None # Fallback if invalid family is requested (URL)
    )
    return families, selected_family
