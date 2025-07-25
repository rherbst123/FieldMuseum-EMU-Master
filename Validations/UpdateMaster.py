'''
Field Museum Master Spreadsheet Updater

Purpose:
Updates the master collector spreadsheet with new data from transcriptions,
using validation results to determine which records need updating or addition.

Key Functions:
- Updates existing collector records with new GUIDs, dates, countries, and IDs
- Adds new collector records when validation indicates new entries
- Standardizes GUID and ID formats across datasets

Usage:
1. Place new collector data in CSV format (matching Example CSV for Max - Sheet1.csv)
    -Change New data sheet from max to match the name above:
    - Or change the path in Line 276 {example_file = "../Examples/Example CSV for Max - Sheet1.csv"} to match new file
2. Place new validated collector sheet (matching Test_Validated.csv)
    -Change file name to match above
    - or change the path in line 278 test_validated_file = "../Examples/Test_Validated.csv"
3. Run script; outputs will generate in the same directory
4. Review Updated sheets

Note: Current test_validated sheet was done purely for testing the script not accurate.
Note: Since the sheet updates itself, if more tests are done before updating it with accurate and valid records,
      a new Master_Collector(newmain).csv may need to be made from the orignal to remove these tested additions.
      
Created by: Alex Wcislo
'''

import pandas as pd
from datetime import datetime

def clean_guids(guid):
    '''extracts guids from link format'''
    if pd.isna(guid):
        return None
    if isinstance(guid, str):
        if '/' in guid:
            return guid.split('/')[-1]
    return guid

def extract_year(date_str):
    if pd.isna(date_str) or not isinstance(date_str, str):
        return None
    try:
        date_obj = datetime.strptime(date_str, '%d %b %Y')
        return date_obj.year
    except ValueError:
        return None

def convert_ids_to_int(df):
    for col in df.columns:
        if 'BotanistID' in col or 'ASA_Botanist_ID' in col or 'irn' in col.lower():
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    return df

def standardize_guid_columns(df):
    '''Convert any HUH_UUID_{i} columns to HUH_GUID_{i} format'''
    for i in range(1, 7):
        old_col = f'HUH_UUID_{i}'
        new_col = f'HUH_GUID_{i}'
        if old_col in df.columns:
            if new_col not in df.columns:
                df[new_col] = df[old_col]
            else:
                # Merge contents if both columns exist
                df[new_col] = df[new_col].combine_first(df[old_col])
            df.drop(columns=[old_col], inplace=True)
    return df

def get_collector_position(test_row):
    '''Get collector position from collector_number in test_validated'''
    if 'collector_number' in test_row and pd.notna(test_row['collector_number']):
        try:
            position = int(test_row['collector_number'])
            if 1 <= position <= 6:
                return position
        except (ValueError, TypeError):
            pass
    return None

def format_name(name):
    '''Reformat names from 'Last, First' to 'First Last' format'''
    if pd.isna(name) or not isinstance(name, str):
        return name
    
    # Handle names with commas (Last, First format)
    if ',' in name:
        parts = [p.strip() for p in name.split(',')]
        if len(parts) >= 2:
            # Reformat as "First Last" if we have both parts
            return f"{parts[1]} {parts[0]}".strip()
    return name.strip()

def get_collector_team(example_record):
    '''Extract collector team using co-collector information from transcribed records'''

    team_members = []
    
    # Check primary collector first
    if 'collectorName1' in example_record and pd.notna(example_record['collectorName1']):
        name = format_name(example_record['collectorName1'])
        if name:
            team_members.append(name)
    elif 'verbatimCollector1' in example_record and pd.notna(example_record['verbatimCollector1']):
        name = format_name(example_record['verbatimCollector1'])
        if name:
            team_members.append(name)
    
    # Check additional collectors (positions 2-6)
    for i in range(2, 7):
        name_col = f'collectorName{i}'
        verbatim_col = f'verbatimCollector{i}'
        
        # Prefer collectorName if available, fall back to verbatimCollector
        if name_col in example_record and pd.notna(example_record[name_col]):
            name = format_name(example_record[name_col])
            if name:
                team_members.append(name)
        elif verbatim_col in example_record and pd.notna(example_record[verbatim_col]):
            name = format_name(example_record[verbatim_col])
            if name:
                team_members.append(name)

    # Format as comma-separated string if multiple members
    if len(team_members) > 1:
        return ", ".join(team_members)
    elif len(team_members) == 1:
        return team_members[0]
    return None

def update_existing_record(master_df, idx, example_record, test_row):
    '''Update an existing record in the master dataframe with new information'''
    print(f"Updating existing record with IRN: {test_row['master_irn']}")
    
    # Get collector position from test_validated3.csv
    collector_position = get_collector_position(test_row)
    
    # Update GUID if we found collector position
    if collector_position is not None:
        guid_col = f'HUH_GUID_{collector_position}'
        if guid_col in example_record and pd.notna(example_record[guid_col]):
            current_guid = master_df.at[idx, 'GUID']
            if pd.isna(current_guid):
                master_df.at[idx, 'GUID'] = example_record[guid_col]
                print(f"Added GUID from position {collector_position}: {example_record[guid_col]}")
            else:
                print(f"GUID already exists, keeping existing: {current_guid}")

    # Update date range
    year = extract_year(example_record['minimumDate'])
    if year:
        current_range = master_df.at[idx, 'date_range_FM']
        if pd.isna(current_range) or not current_range:
            master_df.at[idx, 'date_range_FM'] = str(year)
            print(f"Set new date range: {year}")
        else:
            if '-' in current_range:
                start, end = map(int, current_range.split('-'))
                if year < start:
                    master_df.at[idx, 'date_range_FM'] = f"{year}-{end}"
                    print(f"Extended date range start to: {year}")
                elif year > end:
                    master_df.at[idx, 'date_range_FM'] = f"{start}-{year}"
                    print(f"Extended date range end to: {year}")
            else:
                try:
                    existing_year = int(current_range)
                    if year != existing_year:
                        master_df.at[idx, 'date_range_FM'] = f"{min(year, existing_year)}-{max(year, existing_year)}"
                        print(f"Created new date range: {min(year, existing_year)}-{max(year, existing_year)}")
                except ValueError:
                    print("Warning: Could not parse existing date range")

    # Update countries
    if 'countryName' in example_record:
        country = example_record['countryName']
        if pd.notna(country):
            current_countries = str(master_df.at[idx, 'FM_Countries']).split('|') if pd.notna(master_df.at[idx, 'FM_Countries']) else []
            if country not in current_countries:
                current_countries.append(country)
                master_df.at[idx, 'FM_Countries'] = '|'.join(current_countries)
                print(f"Added new country: {country}")
            else:
                print(f"Country {country} already exists in master")

    # Update botanist ID with proper NA handling
    if collector_position is not None:
        id_col = f'HUH_BotanistID_{collector_position}'
        if id_col in example_record and pd.notna(example_record[id_col]):
            id_value = example_record[id_col]
            if pd.notna(id_value):
                # Check if ID exists in any ASA_Botanist_ID columns
                id_exists = False
                for master_id_col in ['ASA_Botanist_ID', 'ASA_Botanist_ID_2', 'ASA_Botanist_ID_3', 'ASA_Botanist_ID_4']:
                    if (master_id_col in master_df.columns and 
                        pd.notna(master_df.at[idx, master_id_col]) and 
                        int(master_df.at[idx, master_id_col]) == int(id_value)):
                        id_exists = True
                        print(f"ID {id_value} already exists in {master_id_col}")
                        break
                
                if not id_exists:
                    # Find first empty ID column
                    added = False
                    for master_id_col in ['ASA_Botanist_ID', 'ASA_Botanist_ID_2', 'ASA_Botanist_ID_3', 'ASA_Botanist_ID_4']:
                        if master_id_col in master_df.columns and pd.isna(master_df.at[idx, master_id_col]):
                            master_df.at[idx, master_id_col] = id_value
                            print(f"Added new ID {id_value} to {master_id_col}")
                            added = True
                            break
                    
                    if not added:
                        # Create new column if needed
                        if 'ASA_Botanist_ID_5' not in master_df.columns:
                            master_df['ASA_Botanist_ID_5'] = None
                            print("Created new column ASA_Botanist_ID_5")
                        master_df.at[idx, 'ASA_Botanist_ID_5'] = id_value
                        print(f"Added ID {id_value} to ASA_Botanist_ID_5")
    
        
    # Update collector teams
    new_team = get_collector_team(example_record)
    if new_team:
        current_teams = str(master_df.at[idx, 'FM_Collector_Teams']).split(' & ') if pd.notna(master_df.at[idx, 'FM_Collector_Teams']) else []
        
        if new_team not in current_teams:
            current_teams.append(new_team)
            master_df.at[idx, 'FM_Collector_Teams'] = ' & '.join(current_teams)
            print(f"Added new collector team: {new_team}")
        else:
            print(f"Collector team already exists: {new_team}")

def add_new_record(master_df, example_record, test_row):
    '''Add a new record in the master dataframe with new information'''

    print(f"Adding new record with IRN: {test_row['master_irn']}")
    new_record = {}
    
    new_record['Collector_irn'] = test_row['master_irn']
    new_record['Standard_Label_Name'] = test_row['master_name']
    
    collector_position = get_collector_position(test_row)
    
    # Add GUID
    if collector_position is not None:
        guid_col = f'HUH_GUID_{collector_position}'
        if guid_col in example_record and pd.notna(example_record[guid_col]):
            new_record['GUID'] = example_record[guid_col]
            print(f"Added GUID from position {collector_position}: {example_record[guid_col]}")
    
    # Add date
    year = extract_year(example_record['minimumDate'])
    new_record['date_range_FM'] = str(year) if year else None
    print(f"Added date range: {new_record['date_range_FM']}")
    
    # Add country
    new_record['FM_Countries'] = example_record['countryName'] if pd.notna(example_record['countryName']) else None
    print(f"Added country: {new_record['FM_Countries']}")
    
    # Add botanist ID
    if collector_position is not None:
        id_col = f'HUH_BotanistID_{collector_position}'
        if id_col in example_record and pd.notna(example_record[id_col]):
            new_record['ASA_Botanist_ID'] = example_record[id_col]
            print(f"Added ID from position {collector_position}: {example_record[id_col]}")

        
    # Add collector teams
    team_info = get_collector_team(example_record)
    if team_info:
        new_record['FM_Collector_Teams'] = team_info
        print(f"Added collector team: {team_info}")
    
    # Add the new record to master
    master_df = pd.concat([master_df, pd.DataFrame([new_record])], ignore_index=True)
    return master_df

def update_master_with_new_records():
    #File we get back from Max Change to path of new file from max with new data
    example_file = "../Examples/Example CSV for Max - Sheet1.csv" 
    master_file = "Master_collector(newmain).csv" #Current master spreadsheet
    test_validated_file = "../Examples/Test_Validated.csv" #test Validated results (change to path of new validations)
    
    # Load and standardize data
    example_df = pd.read_csv(example_file)
    example_df = standardize_guid_columns(example_df)
    example_df = convert_ids_to_int(example_df)
    
    master_df = pd.read_csv(master_file)
    master_df = standardize_guid_columns(master_df)
    master_df = convert_ids_to_int(master_df)
    
    test_validated_df = pd.read_csv(test_validated_file)
    test_validated_df = convert_ids_to_int(test_validated_df)
    
    master_df['GUID'] = master_df['GUID'].apply(clean_guids)
    
    # Process records
    for _, test_row in test_validated_df.iterrows():
        irn = test_row['master_irn']
        barcode = test_row['barcode']
        
        print(f"\nProcessing barcode: {barcode}, IRN: {irn}")
        
        example_matches = example_df[example_df['Barcode'] == barcode]
        if example_matches.empty:
            print(f"No matching example record found for barcode {barcode}")
            continue
            
        example_record = example_matches.iloc[0]
        
        master_matches = master_df[master_df['Collector_irn'].astype('Int64') == irn]
        
        if not master_matches.empty:
            idx = master_matches.index[0]
            update_existing_record(master_df, idx, example_record, test_row)
        else:
            master_df = add_new_record(master_df, example_record, test_row)
    
    #Save results
    master_df = convert_ids_to_int(master_df)
    output_file = "Master_collector(newmain).csv"
    master_df.to_csv(output_file, index=False)
    print("\nMaster spreadsheet updated and saved to Master_collector(newmain).csv")

if __name__ == "__main__":
    update_master_with_new_records()
