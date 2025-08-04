import pandas as pd
import re
from datetime import datetime


'''
Field Museum Date Cleaning and Collector Matching Script

Purpose:
- Cleans and standardizes date formats in collector records
- Matches collectors against master database to add IRN and Botanist IDs

Usage:
1. Place new collector data in CSV format (matching Example CSV for Max - Sheet1.csv)
    -Change New data sheet from max to match the name above:
    - Or change the path in Line 172 {example_file = "../Examples/Example CSV for Max - Sheet1.csv"} to match new file
2. Run script; outputs will generate in the same directory
    -One file as cleaned_dates.csv
    -One file saved based on user input

This script was created by: Riley Herbst and Alex Wcislo
'''

#Spanish to English month mapping
SPANISH_TO_ENGLISH = {
    'enero': 'Jan', 'febrero': 'Feb', 'marzo': 'Mar', 'abril': 'Apr',
    'mayo': 'May', 'junio': 'Jun', 'julio': 'Jul', 'agosto': 'Aug',
    'septiembre': 'Sep', 'octubre': 'Oct', 'noviembre': 'Nov', 'diciembre': 'Dec'
}

def clean_date(date_str):
    if pd.isna(date_str) or str(date_str).strip() == '':
        return ''
    
    date_str = str(date_str).strip()
    
    # Check for s.d.
    if date_str.lower() == 's.d.':
        return 's.d.'
    
    #Check for bracketed dates - leave as is for now
    if date_str.startswith('[') and date_str.endswith(']'):
        return date_str
    
    #Handle Spanish month names and remove "de"
    for spanish_month, eng_abbr in SPANISH_TO_ENGLISH.items():
        if spanish_month in date_str.lower():
            # Replace Spanish month with English abbreviation and remove "de"
            pattern = re.compile(re.escape(spanish_month), re.IGNORECASE)
            date_str = pattern.sub(eng_abbr, date_str)
            date_str = re.sub(r'\s*de\s*', ' ', date_str).strip()
            break
    
    #Handle month-year formats with periods (e.g., "Oct. 1934")
    if re.search(r'^[A-Za-z]{3}\.\s\d{4}$', date_str):
        return date_str.replace('.', '')
    
    #Handle formats with commas (e.g., "MON. DD, YYYY" or "MON. YYYY")
    if ',' in date_str:
        cleaned = date_str.replace('.', '')
        
        #Parse the date
        for fmt in ['%b %d, %Y', '%B %d, %Y', '%b %Y', '%B %Y']:
            try:
                dt = datetime.strptime(cleaned, fmt)
                if '%d' in fmt:
                    return f"{dt.day:02d} {dt.strftime('%b').replace('.', '')} {dt.year}"
                else:
                    return f"{dt.strftime('%b').replace('.', '')} {dt.year}"
            except ValueError:
                continue
    
    #Handle standard DD MONTH YYYY format (e.g., "08 July 1988")
    for fmt in ['%d %B %Y', '%d %b %Y', '%d %b. %Y']:
        try:
            dt = datetime.strptime(date_str, fmt)
            return f"{dt.day:02d} {dt.strftime('%b').replace('.', '')} {dt.year}"
        except ValueError:
            continue
    
    #Handle cases where month already has period (e.g., "3 Feb. 1972")
    if re.search(r'\b[A-Za-z]{3}\.\s\d{4}', date_str) or re.search(r'\d+\s[A-Za-z]{3}\.\s\d{4}', date_str):
        #Extract components and reformat with zero-padded day
        match = re.search(r'(\d+)\s([A-Za-z]{3})\.?\s(\d{4})', date_str)
        if match:
            day = int(match.group(1))
            month = match.group(2)
            year = match.group(3)
            return f"{day:02d} {month} {year}"
    
    #Handle already clean formats (e.g., "7 Feb 1999")
    if re.search(r'^\d{1,2}\s[A-Za-z]{3}\s\d{4}$', date_str):
        parts = date_str.split()
        day = int(parts[0])
        return f"{day:02d} {parts[1]} {parts[2]}"
    
    #Handle month-year formats without day (e.g., "Oct 1934")
    if re.search(r'^[A-Za-z]{3}\s\d{4}$', date_str):
        return date_str

    #Handle other formats that should remain as-is
    #Or add new chunks to handle new formats (e.g., roman numerals - "IX or VII")
    return date_str

def process_csv(input_file, output_file):
    df = pd.read_csv(input_file)
    #Process date columns
    date_columns = ['minimumDate', 'maximumDate', 'verbatimCollectionDate']
    original_columns = list(df.columns)
    
    for col in date_columns:
        if col in df.columns:
            clean_col = f'clean{col}'
            df[clean_col] = df[col].apply(clean_date)
            col_index = original_columns.index(col)
            original_columns.insert(col_index + 1, clean_col)
    
    # Reorder and save
    df = df[original_columns]
    df.to_csv(output_file, index=False, float_format='%.0f')

#Add our "Special" Columns into the right place just before each collector
def merge_collector_data(example_csv_path, master_csv_path, output_csv_path):
    
    example_df = pd.read_csv(example_csv_path)
    master_df = pd.read_csv(master_csv_path)
    
    # Create lookup dictionary from master sheet
    collector_lookup = {}
    for _, row in master_df.iterrows():
        name = row['Standard_Label_Name']
        if pd.notna(name):
            collector_lookup[name] = (row['Collector_irn'], row['ASA_Botanist_ID'])
    
    # Insert IRN and Botanist ID columns before each collector
    new_columns = []
    for col in example_df.columns:
        if col.startswith('collectorName'):
            collector_num = col.replace('collectorName', '')
            new_columns.extend([f'Collector_IRN_{collector_num}', f'Botanist_ID_{collector_num}'])
        new_columns.append(col)
    
    
    for i in range(1, 6):
        example_df[f'Collector_IRN_{i}'] = None
        example_df[f'Botanist_ID_{i}'] = None
    
    example_df = example_df[new_columns]
    
    
    for idx, row in example_df.iterrows():
        for i in range(1, 6):
            collector_col = f'collectorName{i}'
            if collector_col in row and pd.notna(row[collector_col]):
                collector_name = row[collector_col]
                if collector_name in collector_lookup:
                    irn, botanist_id = collector_lookup[collector_name]
                    example_df.at[idx, f'Collector_IRN_{i}'] = irn
                    example_df.at[idx, f'Botanist_ID_{i}'] = botanist_id
    
    
    example_df.to_csv(output_csv_path, index=False, float_format='%.0f')
    return example_df

def get_output_filename():
    filename = input("Enter the Output name for the file: ")
    if not filename.endswith('.csv'):
        filename += '.csv'
    return filename

if __name__ == "__main__":
    process_csv('Examples/Example_MAX_Sheet.csv', 
                'cleaned_dates.csv') ##Change example path to path of new file from max with new data
    output_file = get_output_filename()
    result_df = merge_collector_data(
        'cleaned_dates.csv',
        'Master_Collector(newmain).csv',
        output_file
    )
    print(f"Final sheet created successfully as {output_file}!")