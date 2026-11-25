import pandas as pd

from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from urllib.parse import urlencode

from .models import ProcessMap
from .forms import StationProcessFormSet

from .scripts.utils import (
    get_family_selection,
)

from .scripts.yields import (
    base_dataframe_cleanup,
    calculate_yield_by_loop,
)

def station_list_view(request):
    """ Allow Visitors to define Station Operation IDs
        and toggle reporting of each. """

    # For Family selection dropdown menu.
    families, selected_family = get_family_selection(request)

    # Get all the data we need to display.
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

def yield_view(request):
    """ Calculate and show the Yield of the latest 7 days.
     (Relative to available data, mind you.) """

    # For Family selection dropdown menu.
    families, selected_family = get_family_selection(request)

    # Get data related to selected family from the ProcessMap.
    process_map = ProcessMap.objects.filter(family=selected_family)

    # Turn data into DataFrame...
    process_map_df = pd.DataFrame(list(process_map.values('station_type','operation_id')))
    # ...and then set the index, which will allow the Yield report to show the proper Station order.
    process_map_index = process_map_df.set_index('station_type')['operation_id']

    # We work the base dataframe, which will
    # be used for two calculations.
    clean_dataframe = base_dataframe_cleanup(selected_family)

    # Then we calculate data for the First Pass Yield.
    fpy, rty_fpy = calculate_yield_by_loop(clean_dataframe, 1, process_map_index)

    # And then we calculate for "Third" Pass Yield.
    # It is a way to remove Test False Calls and get a feel
    # for how much this phenomenon impacts production.
    tpy, rty_tpy = calculate_yield_by_loop(clean_dataframe, 3, process_map_index)

    ## Please refer to the Comments in the definition of these two functions.

    # For Styling, I broke down the components of the resulting Crosstabs
    # to get more granular control on the Template.

    metrics = ['FAIL', 'PASS','TOTAL','YIELD']
    fpy_dates = list(fpy.columns.get_level_values('TestDate').unique())

    fpy_rows = [] # Initialization

    # Reconstruct the Crosstab into a new table.
    # .to_html() is too literal when translating the Crosstab. This results in a leaner end-view.
    for operation_id, station_type in fpy.index:
        fpy_rows.append({
            'operation_id': operation_id,
            'station_type': station_type,
            'cells': [
                fpy.loc[(operation_id, station_type), (date, metric)]
                for date in fpy_dates
                for metric in metrics
            ],
        })
    fpy_rty_values = [f'{rty_fpy[date]:.2f}%' for date in fpy_dates]

    tpy_rows =[]
    tpy_dates = list(tpy.columns.get_level_values('TestDate').unique())

    for operation_id, station_type in tpy.index:
        tpy_rows.append({
            'operation_id': operation_id,
            'station_type': station_type,
            'cells': [
                tpy.loc[(operation_id, station_type), (date, metric)]
                for date in tpy_dates
                for metric in metrics
            ],
        })
    tpy_rty_values = [f'{rty_tpy[date]:.2f}%' for date in tpy_dates]


    context = {
        'fpy_dates': fpy_dates,
        'metrics': metrics,
        'fpy_rows': fpy_rows,
        'fpy_rty_values': fpy_rty_values,
        'tpy_dates': tpy_dates,
        'tpy_rows': tpy_rows,
        'tpy_rty_values': tpy_rty_values,
        'families': families,
        'selected_family': selected_family
    }

    return render(request, 'dashboard_yields.html', context)