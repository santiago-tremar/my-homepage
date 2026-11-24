from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from urllib.parse import urlencode

from .models import ProcessMap
from .forms import StationProcessFormSet

from .scripts.utils import (
    get_family_selection,
)

def station_list_view(request):
    """ Allow Visitors to define Station Operation IDs
        and toggle reporting of each. """

    families, selected_family = get_family_selection(request)

    station_queryset = ProcessMap.objects.filter(family=selected_family)

    if request.method == 'POST':
        formset = StationProcessFormSet(request.POST, queryset=station_queryset)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Changes saved.')
            url = f'{reverse("station-manager")}?{urlencode({"family": selected_family})}'
            return redirect(url)
    else:
        formset = StationProcessFormSet(queryset=station_queryset)
    ## A production-read version of this tool would include User Authentication
    ## and user permission checks for the Forms here. Again, as a demo, I am
    ## prioritizing accessibility.

    context = {
        'formset': formset,
        'stations': station_queryset,
        'families': families,
        'selected_family': selected_family,
    }

    return render(request, 'dashboard_config.html', context)