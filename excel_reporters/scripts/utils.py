import pandas as pd
import numpy as np

from pathlib import Path
from datetime import datetime


# SCRIPT_DIR = Path(__file__).resolve().parent
# randomizer_data_path = SCRIPT_DIR / 'text' / 'randomizer.csv'

# base_data = pd.read_csv(randomizer_data_path)

def generate_single_expenditures(base_data):
    """ Generate the data to be turned into Excel report. """

    # Ensure CSV data is read as numbers by Pandas.
    monthly = pd.to_numeric(base_data['monthly'], errors='coerce')
    # Initialize NumPy's Random Number Generator.
    rng = np.random.default_rng()

    # Generate a month's expenditure as a random percentage from the budgeted amounts.
    ## Allow some overspending.
    base_data['exercised_this_month'] = rng.uniform(low=0, high=1.3, size=len(monthly)) * monthly

    return base_data

# month = datetime.now().month

def generate_bulk_expenditures(month, base_data):
    """ Create any number of expenditure reports from January to the current month of the year. """
    # 'month' argument is the current month as an integer.

    # Create a dictionary for every month up to now.
    results = {
        f'report_{ i + 1 }': generate_single_expenditures(base_data.copy()) # Avoir reusing and overwriting dataframes. 
        for i in range(month)
    }

    return results

# Call the function.
# individual_reports = generate_bulk_expenditures(month)

def result_calculation(individual_report_dictionary, month):
    """ Calulate Resulting Report's Data. """
    # Create single DataFrame with all year's data.
    accumulated_report = pd.concat(individual_report_dictionary)

    # Extract only the current month's data.
    working_df = individual_report_dictionary[f'report_{(month)}']
    # Change the columns' names.
    working_df.columns = [
        'Account Code',
        'Account Description',
        'Approved Annual Budget',
        'Monthly Budget Allocation',
        'Current-Month Actual Expenditures'
    ]

    # Build report.
    working_df['Current-Month Budget Utilization (%)'] = working_df['Current-Month Actual Expenditures'] / working_df['Monthly Budget Allocation']
    # Because the feed files have predictable accounts that match on every "month", the following setup is optimal. 
    # In a real product, it would have to actively scan the account numbers and sum the monthly expenditures by them.
    working_df['YTD Actual Expenditures'] = accumulated_report.groupby(level=1)['exercised_this_month'].sum()
    working_df['Remaining Annual Budget'] = (
        working_df['Approved Annual Budget'] - working_df['YTD Actual Expenditures']
    )
    working_df['YTD Expenditures as % of Annual Budget'] = working_df['YTD Actual Expenditures'] / working_df['Approved Annual Budget']

    return working_df


def final_touches(results):
    """ Add TOTALS rows to base report, grouped by account Number. """
    # 1. Identify the category header rows
    is_header = results['Account Code'].astype(str).str.endswith('000-000')

    # 2. Create a group key that increments at each header
    # This assigns the same group number to the header and all accounts following it
    results['group_key'] = is_header.cumsum()

    def add_totals(group):
            # Separate the header from the data rows
            header = group.iloc[[0]]
            data = group.iloc[1:]
    
            if len(data) == 0:
                return header  # If there are no accounts, just return the header
        
            # Calculate the totals for numeric columns
            totals = data.select_dtypes(include=[np.number]).sum()
    
            # Create the Totals row
            totals_row = pd.DataFrame([totals])
    
            # Combine header, data, and the new totals row
            return pd.concat([header, data, totals_row], ignore_index=True)

    # 3. Apply the function to each group and drop the temporary key
    final_result = results.groupby('group_key', group_keys=False).apply(add_totals)
   #final_result = final_result.drop(columns=['group_key'])
    final_result['YTD Expenditures as % of Annual Budget'] = final_result['YTD Actual Expenditures'] / final_result['Approved Annual Budget']
    empty_accounts = (
        final_result['Account Code'].isna()
        | final_result['Account Code'].astype(str).str.strip().eq('')
    )
    final_result.loc[empty_accounts, 'Account Description'] = 'SUBTOTAL'
    return final_result

def summary_report(results):
    """ Create secondary report, grouped by account description. """
    working_result = results.drop(columns=['Account Code','Monthly Budget Allocation','YTD Expenditures as % of Annual Budget','Remaining Annual Budget','Current-Month Budget Utilization (%)'])
    working_result = working_result.groupby(
        'Account Description',
        as_index=False,
    ).sum(numeric_only=True)

    working_result['YTD Expenditures as % of Annual Budget'] = working_result['YTD Actual Expenditures'] / working_result['Approved Annual Budget']
    working_result['Remaining Annual Budget'] = working_result['Approved Annual Budget'] - working_result['YTD Actual Expenditures']

    subtotal = {column: np.nan for column in working_result.columns}
    subtotal['Account Description'] = 'GRAND TOTAL'
    subtotal['Approved Annual Budget'] = working_result['Approved Annual Budget'].sum()
    subtotal['YTD Actual Expenditures'] = working_result['YTD Actual Expenditures'].sum()
    working_result = pd.concat(
        [working_result, pd.DataFrame([subtotal])],
        ignore_index=True,
    )

    return working_result