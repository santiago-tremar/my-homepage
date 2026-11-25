
import pandas as pd

from quality_dashboards.models import RawData, ProcessMap

# /////////////////////////////////////////////////////////////////////////////

def base_dataframe_cleanup(selected_family='Alpha'):
    """ Create base Data Frame for yield calculations. """

    # Call the latest available Raw Data file. 
    # Yes, we are assuming the most recently uploaded file contains the
    # data from the most recent time period. Again, this is generally expected
    # in Production.
    if RawData.objects.all().exists():
        latest_file = RawData.objects.latest('upload_date')
        with latest_file.upload.open('rb') as uploaded_file:
            dataframe = pd.read_csv(uploaded_file)
    else:
        d = {'Station': ['NoData', 'NoData'], 'PartFamily': ['Alpha', 'Bravo']} # Dummy DF for fail-safe.
        dataframe = pd.DataFrame(data=d)


    # Get only selected stations from Station Manager.
    selected_stations = list(
         ProcessMap.objects.filter(
              family=selected_family,
              result_filter=True,
         ).values_list('station_type', flat=True)
    )
    # Cut down DataFrame to selected family and stations.
    working_df = dataframe[(dataframe['PartFamily'] == selected_family)
                           & dataframe['Station'].isin(selected_stations)
                           ]


    # Convert dates. 
    working_df['TestTime'] = pd.to_datetime(working_df['TestTime'],format='mixed',dayfirst=True)
   
    # Create Date register by Daily Shift periods.
    # Since Work shifts are not strictly aligned with calendar dates, we require a small 'off-set'
    # so a Working day begins with Shift 1 and ends with Shift 3.
    working_df['TestDate'] = (working_df['TestTime'] - pd.Timedelta(hours=7)).dt.date

    # If we wanted to calculate a Weekly Yield as well, I would activate the following statement:
    ## working_df['TestWeek'] = (working_df['TestTime'] - pd.Timedelta(hours=23)).dt.isocalendar().week
    # In this way, a Working Week begins at the start of Shift 3 of Sunday, per the conventions I worked with.


    # Drop duplicates only to ensure one row per Serial, Station, TestResult, since
    # this Yield report works by counting the amount of Rows and
    # the Raw Data contains multiple rows for a single global test result.
    # While it may seem like unnecessary work for a Demo file, it represents a real challenge
    # that I faced in the industry. 
    # The upside is that the same Raw Data can feed different reports, as will be
    # represented in this site with a Failure Mode report.
    dupe_index = ['SerialNumber','Station','TestSequence']
    # The Raw Data already provides an incremental integer 'TestSequence' to differentiate every
    # test performed on a Serial Number. De-duplicating here retains one test result per test.
    yield_df = working_df.drop_duplicates(subset=dupe_index,keep='first',inplace=False,ignore_index=False)

    # Calculate cumulative occurrences for localized Test amounts by date.
    # Sometimes the same Serial Number will be re-tested multiple times for a variety of reasons.
    # We want to keep track of how many times a Serial Number has been tested in the same day,
    # and retain the chronological order of the tests.
    # The TestSequence already provided by the raw data is global, so we could lose track
    # of tests done in a given day.
    yield_df_sorted = yield_df.sort_values(['SerialNumber','Station','TestTime'])
    yield_df_sorted['AggregatedTestLoop'] = (
        yield_df_sorted.groupby(['SerialNumber', 'Station','TestDate'])
        .cumcount()
        .add(1)
        )

    # We return the work done here, for it will be forked into two outputs.
    return yield_df_sorted

def calculate_yield_by_loop(dataframe, loops, process_map_index):
    """ Take the worked-on Base DataFrame and calculate Any-Pass Yield. """

    # Filter Data Frame by localized Test Loops.
    # Test Loop of '1' is equivalent to 'First Pass Yield' within the day.
    # Higher Test Loops mean 'Yield after this many tests', which is a good, single-view
    # indicator of the impact of high false-call rates.
    yield_df = dataframe[dataframe['AggregatedTestLoop'] <= loops]

    # Order DataFrame by most recent tests to the oldest.
    yield_df.sort_values(by='AggregatedTestLoop',inplace=True,ascending=False)
    

    # Drops duplicates to keep only the most recent result of the test according to the date.
        # This should return a "final" yield per Serial Number, according to the specified Test Loop.
    dupe_index = ['SerialNumber','Station','TestDate']
    yield_df.drop_duplicates(subset=dupe_index,keep='first',inplace=True,ignore_index=False)

    # Create a Crosstab for Dates.
    # Here is where the 'PASS' and 'FAIL' counts per station are calculated.
    yield_ct = pd.crosstab(yield_df['Station'],[yield_df['TestDate'],yield_df['GlobalTestResult']])

    # We Save the Dates that are actually present in the data.
    dates = yield_ct.columns.levels[0]

         # A small detour to fill in the gaps.
         # Whenever a given Date contains no Pass or Fail data, the column will still be created
         # and shown in the Crosstab thanks to this little code.
    expected_status = ['PASS','FAIL']
    filler = pd.MultiIndex.from_product(
       [dates,expected_status],
       names=['TestDate', 'GlobalTestResult']
    )

    yield_ct = yield_ct.reindex(columns=filler, fill_value=0)

    # Ensure the Stations are ordered according to Process Map by the Operation ID set in Station Manager.
    order_numbers = yield_ct.index.map(process_map_index)
    yield_ct.index = pd.MultiIndex.from_arrays([order_numbers, yield_ct.index], names=['OperationID', 'Station'])
    yield_ct = yield_ct.sort_index(level=0)

    rty_calculus = {} # Initialize to store Rolled-Throughput Yield data in the loop.

    for date in dates:
        # Get Pass and Fail counts. Return a Series of 0s if the PASS/FAIL column does not exist.
        # It's a possibility we accounted for in Lines106-112, but I prefer keeping fallbacks.
        pass_count = yield_ct.get((date,'PASS'),pd.Series(0, index=yield_ct.index))
        fail_count = yield_ct.get((date,'FAIL'),pd.Series(0, index=yield_ct.index))

        # Actually calculate the yield.
        yield_calculus = (pass_count / (pass_count+fail_count)).fillna(0) * 100
        rty_calculus[date] = (yield_calculus / 100).prod() * 100 # Calculate RTY with every individual yield.

        # Assign into the Crosstab for visualization.
        yield_ct[(date, 'YIELD')] = yield_calculus.map('{:.2f}%'.format)
        yield_ct[(date, 'TOTAL')] = pass_count+fail_count

    # Sort to get columns right next to eachother.
    # Sort by columns. Nice, repeatable positions by date.
    yield_ct = yield_ct.sort_index(axis=1)

    # Get only the 7 latest days.
    # Because we safe-guarded the expected columns in Lines106-112, each Date must
    # always contain 4 columns. Therefore, a fixed count here is a good way of 
    # resolving this requirement.
    yield_ct_latest = yield_ct.iloc[:,-28:]

    latest_dates = yield_ct_latest.columns.get_level_values('TestDate').unique()
    rty_calculus = {date: rty_calculus[date] for date in latest_dates}
    
    return yield_ct_latest, rty_calculus