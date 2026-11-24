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
        else families[0] if families else None
    )
    return families, selected_family

def load_rawdata():
    """ Load Raw Data from the Media files. """
    file_list = RawData.objects.all()

    ## Define DataFrame from most recent file loaded to DB.
    if file_list.exists():
        latest_file = RawData.objects.latest('upload_date')
        with latest_file.upload.open("rb") as uploaded_file:
            dataframe = pd.read_csv(uploaded_file)
    else:
        d = {'Station': ['NoData', 'NoData'], 'PartFamily': ['Alpha', 'Bravo']} # Dummy DF for fail-safe.
        dataframe = pd.DataFrame(data=d)

    return dataframe

def write_families_and_stations_to_database():
    """ 
    Read Latest Raw Data, get families and stations, and write to Database
    to make available on the Station Manager and the Yield Report.
    """
    # Read latest Raw Data.
    dataframe = load_rawdata()

    ## Column names are hard-coded because, in a manufacturing context,
    ## we expect consistency in the queries that would feed a tool such as this.
    pairs = dataframe[["PartFamily", "Station"]].dropna().drop_duplicates()

    for family, station in pairs.itertuples(index=False, name=None):
        ProcessMap.objects.get_or_create(
            family=family,
            station_type=station,
            defaults={"operation_id": 0},
        )
    ## As this is just a demo and I currently lack the tools to
    ## constantly generate more mock data, I am writing to the DB
    ## only if it has no data to ensure quicker page refreshes. 