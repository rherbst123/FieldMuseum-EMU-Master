'''
Field Museum Validation Script

Purpose:
Validates primary and co-collector records against the master collector spreadsheet,
checking for name matches, ID matches, country matches, date matches, and team association matchs. Generates
detailed validation reports for both primary and co-collectors.

Inputs:
- Example CSV for Max - Sheet1.csv (new records to validate)
- Master_Collector(newmain).csv (reference database)

Outputs:
- validation_results(Primary).csv (primary collector validation)
- validation_results(Secondary).csv (co-collector validation)

Functions:
1. Name Matching: Handles variants, initials, and name order (Last, First vs First Last)
2. ID Validation: Cross-checks HUH_BotanistID against master IDs
3. Country and date Checks: 
   - Country matching against FM/HUH geography fields
   - Date validation against collector lifespans/activity periods
4. Team Analysis: Verifies co-collector relationships

Usage:
1. Place new collector data in CSV format (matching Example CSV for Max - Sheet1.csv)
    -Change New data sheet from max to match the name above:
    - Or change the path in Line 771 {example_file = "../Examples/Example CSV for Max - Sheet1.csv"} to match new file
2. Run script; outputs will generate in the same directory
3. Review validation reports for errors

Created by: Alex Wcislo
'''

import pandas as pd
import unicodedata

def remove_accents(text):
    '''Helper function that helps clean up names'''
    if not isinstance(text, str):
        return text
    return ''.join(c for c in unicodedata.normalize('NFD', text) 
                  if unicodedata.category(c) != 'Mn')

def extract_year(date_str):
    '''Helper function that extracts 4 digit year'''
    if not isinstance(date_str, str):
        return None
    for i in range(len(date_str) - 3):
        if date_str[i:i+4].isdigit():
            return int(date_str[i:i+4])
    return None

def check_date_in_range(year, date_range_str):
    if pd.isna(date_range_str) or not date_range_str or year is None:
        return False
    
    # Split the date range string into components
    parts = date_range_str.split(' - ')
    if len(parts) == 1:
        # Single year or range like "1844-1903"
        if '-' in parts[0]:
            start, end = parts[0].split('-')[:2]
            try:
                start_year = int(start)
                end_year = int(end)
                return start_year <= year <= end_year
            except ValueError:
                return False
        else:
            try:
                return year == int(parts[0])
            except ValueError:
                return False
    else:
        #Range like "1876 - 1931"
        try:
            start_year = int(parts[0])
            end_year = int(parts[1])
            return start_year <= year <= end_year
        except ValueError:
            return False

def has_brackets(text):
    if not isinstance(text, str):
        return False
    return '[' in text or ']' in text

def normalize_initials(name):
    """Normalize spacing around initials (D.B. -> D. B.)"""
    if not isinstance(name, str):
        return name

    name = name.replace('.', '. ')  #add space after all periods
    name = ' '.join(name.split())  #Remove extra spaces

    name = name.rstrip()
    return name

def process_name_match(collector_name, verbatim_name, name_variants):
    """Enhanced name matching that handles both full and abbreviated names"""
    #Get all name variants from master
    cleaned_variants = []
    for v in name_variants:
        if pd.notna(v) and isinstance(v, str):
            cleaned = remove_accents(v).lower().strip()
            cleaned = normalize_initials(cleaned)
            cleaned_variants.append(cleaned)

    all_master_names = cleaned_variants

    #Get names to check from example sheet
    names_to_check = []
    if pd.notna(collector_name) and collector_name != '':
        names_to_check.append(collector_name)
    if pd.notna(verbatim_name) and verbatim_name != '':
        names_to_check.append(verbatim_name)
    
    for name in names_to_check:
        if not isinstance(name, str):
            continue
            
        #Clean te name to check
        cleaned_name = remove_accents(name).lower().strip()
        cleaned_name = normalize_initials(cleaned_name)

        #Check exact matches
        if cleaned_name in all_master_names:
            return True
        
        #Check flipped formats ("Lastname, Firstname" format (e.g. "Díaz, Camilo"))
        if ',' in cleaned_name:
            last, first = cleaned_name.split(',', 1)
            last = last.strip()
            first = first.strip()

            #Try "Firstname Lastname" 
            normalized = f"{first} {last}"
            if normalized in all_master_names:
                return True
            
            #Try abbreviated name (ex. "C. Lastname")
            if first:
                first_parts = first.split()
                abbreviated_first = ' '.join([p[0] + '.' for p in first_parts])
                abbreviated = f"{abbreviated_first} {last}"
                if abbreviated in all_master_names:
                    return True
        
        #Check abbreviated names (e.g. "C. Díaz")
        if '.' in cleaned_name and ' ' in cleaned_name:
            parts = cleaned_name.split()
            if all(len(p) == 2 and p.endswith('.') for p in parts[:-1]):  #All except last are initials

                initials = [p[0] for p in parts[:-1]]
                lastname = parts[-1]
                
                #check against all master names
                for master_name in all_master_names:
                    master_parts = master_name.split()
                    if (len(master_parts) == len(parts) and  #Same number of components
                        master_parts[-1] == lastname and   #Same last name
                        all(mp[0] == init for mp, init in zip(master_parts[:-1], initials))):  # ame initials
                        return True
        
        if any(cleaned_name in variant for variant in all_master_names):
            return True
    
    return False

def remove_country_accents(text):
    """Remove accents from country names for matching"""
    if not isinstance(text, str):
        return text
    return remove_accents(text).lower().strip()

def get_country_match_source(country, master_row):
    """Check country match against all possible columns and return match source"""
    country_lower = remove_country_accents(country)
    
    # Check all possible country columns in master
    country_columns = [
        ('FM_Countries', 'FM'),
        ('Geography_Collector', 'HUH_Geo_Collector'),
        ('Geography_Author', 'HUH_Geo_Author')
    ]

    for col, source in country_columns:
        if col in master_row and pd.notna(master_row[col]):
            master_country = str(master_row[col])
            if country_lower in remove_country_accents(master_country):
                return f"True|{country}|{source}"
    
    return "False"

def extract_last_names(name):
    """Extract last names from a name string, handling various formats"""
    if not isinstance(name, str) or not name.strip():
        return []

    name = remove_accents(name).strip()
    
    #Handle "Lastname, Firstname" or "Lastname, F." formats
    if ',' in name:
        last_part = name.split(',')[0].strip()
        return [last_part]
    
    #Handle "F. Lastname" or "Firstname Lastname" formats
    parts = name.split()
    last_names = []
    
    #If we have initials (parts with '.'), take the next word
    i = 0
    while i < len(parts):
        if parts[i].endswith('.'):
            if i + 1 < len(parts):
                last_names.append(parts[i+1])
                i += 2
            else:
                i += 1
        else:
            # For "Firstname Lastname" format, take the last part
            if i == len(parts) - 1:
                last_names.append(parts[i])
            i += 1
    
    return last_names

def check_collector_team_match(collector_names, master_team_str, master_fm_team_str):
    """Check if any of the collector team members match the master team columns"""
    if not collector_names:
        return "False|No-co-collectors"
    
    #Extract last names from all collector names
    all_last_names = []
    for name in collector_names:
        all_last_names.extend(extract_last_names(name))
    
    if not all_last_names:
        return "False|No-valid-names"
    
    # master collector team strings
    master_teams = []
    if pd.notna(master_team_str) and isinstance(master_team_str, str):
        master_teams.append(remove_accents(master_team_str).lower())
    if pd.notna(master_fm_team_str) and isinstance(master_fm_team_str, str):
        master_teams.append(remove_accents(master_fm_team_str).lower())
    
    if not master_teams:
        return "False|No-team-data"
    
    #Check each last name against all master team strings
    match_count = 0
    for last_name in all_last_names:
        last_name_lower = last_name.lower()
        for team_str in master_teams:
            # Look for the last name as a whole word in the team string
            if f' {last_name_lower} ' in f' {team_str} ':
                match_count += 1
                break
    if match_count < 0:
        return last_name_lower
    
    if match_count > 0:
        return f"True|{match_count}"
    else:
        return "False"

def get_country_matches(country, master_row):
    """Check country match against separate columns and return separate match results"""
    if not country:
        return {'FM_Country_match': "False", 'HUH_Country_match': "False"}
    
    country_lower = remove_country_accents(country)
    results = {'FM_Country_match': "False", 'HUH_Country_match': "False"}
    
    # Check FM country match
    fm_countries = str(master_row.get('FM_Countries', ''))
    if fm_countries and country_lower in remove_country_accents(fm_countries):
        results['FM_Country_match'] = f"True|{country}"
    
    # Check HUH country matches (Geography_Collector and Geography_Author)
    huh_sources = []
    for col in ['Geography_Collector', 'Geography_Author']:
        if col in master_row and pd.notna(master_row[col]):
            huh_country = str(master_row[col])
            if country_lower in remove_country_accents(huh_country):
                huh_sources.append(col.replace('Geography_', ''))
    
    if huh_sources:
        results['HUH_Country_match'] = f"True|{country}"
    
    return results

def get_date_matches(avg_year, master_row):
    """Check date match against separate columns and return separate match results"""
    if not avg_year:
        return {'FM_Date_match': "False", 'HUH_Date_match': "False"}
    
    results = {'FM_Date_match': "False", 'HUH_Date_match': "False"}
    huh_matches = []
    
    # Check FM date range
    fm_date_range = master_row.get('date_range_FM')
    if fm_date_range and check_date_in_range(avg_year, str(fm_date_range)):
        results['FM_Date_match'] = "True"
    
    # Check HUH lifespan
    lifespan = master_row.get('Lifespan')
    if lifespan and check_date_in_range(avg_year, str(lifespan)):
        huh_matches.append("Lifespan")
    
    # Check HUH collections
    huh_collections = master_row.get('HUH_Collections_in')
    if huh_collections and check_date_in_range(avg_year, str(huh_collections)):
        huh_matches.append("Collections_in")
    
    # Format HUH date matches
    if huh_matches:
        if len(huh_matches) == 2:
            results['HUH_Date_match'] = "True|Both"
        else:
            results['HUH_Date_match'] = f"True|{huh_matches[0]}"
    
    return results

def process_secondary_collectors(example_df, master_df):
    """Process all secondary collectors (collectorName2+, verbatimCollector2+)"""
    secondary_results = []
    
    # Process each row in the example file
    for _, row in example_df.iterrows():
        image_url = row.get('Image_URL', '')
        barcode = row['Barcode']
        
        # Find all existing secondary collectors in this row
        existing_collectors = []
        for i in range(2, 6):  # Check collector numbers 2-6
            verbatim_name = row.get(f'verbatimCollector{i}', '')
            collector_name = row.get(f'collectorName{i}', '')
            
            # Only process if we have a name (either verbatim or collector name)
            if not (pd.isna(verbatim_name) and pd.isna(collector_name)):
                existing_collectors.append(i)
        
        # Now process only the existing collectors
        for i in existing_collectors:
            verbatim_name = row.get(f'verbatimCollector{i}', '')
            collector_name = row.get(f'collectorName{i}', '')
                
            # Check for brackets in verbatim name
            brackets_present = has_brackets(verbatim_name)
            
            # If brackets are present, create a special result row
            if brackets_present:
                secondary_results.append({
                    'Image_URL': image_url,
                    'barcode': barcode,
                    'collector_number': i,
                    'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                    'master_name': '',
                    'master_irn': '',
                    'master_name_variants': '',
                    'id_match': 'False|Brackets',
                    'name_match': 'False|Brackets',
                    'FM_Country_match': 'False|Brackets',
                    'HUH_Country_match': 'False|Brackets',
                    'FM_Date_match': 'False|Brackets',
                    'HUH_Date_match': 'False|Brackets',
                    'collector_team_match': 'False|Brackets',
                    'score': 'BRACKETS'
                })
                continue
            
            # Get country and dates from primary record
            country = row.get('countryName', '')
            min_date = row.get('minimumDate', '')
            max_date = row.get('maximumDate', '')
            
            # Get year from dates
            min_year = extract_year(str(min_date)) if pd.notna(min_date) else None
            max_year = extract_year(str(max_date)) if pd.notna(max_date) else None
            years = [y for y in [min_year, max_year] if y is not None]
            avg_year = sum(years) / len(years) if years else None
            
            # Find matches in master
            matches = []
            has_match = False
            
            for _, master_row in master_df.iterrows():
                # Get all name variants from master
                name_variants = []
                for col in master_row.index:
                    if col.startswith('Variant_name') or col in ['Standard_Label_Name', 'nam_NamFullName', 'nam_NamBriefName', 'OtherNames']:
                        val = master_row.get(col, '')
                        if pd.notna(val) and val != '':
                            if isinstance(val, str):
                                name_variants.append(val)
                
                # First check name match - prioritize verbatim name if exists
                name_to_match = verbatim_name if verbatim_name and not pd.isna(verbatim_name) else collector_name
                name_match = process_name_match('', name_to_match, name_variants) if name_to_match else False
                
                # Check ID match if exists for this collector
                id_match_status = "False"
                huh_id = row.get(f'HUH_BotanistID_{i}', '')

                if pd.isna(huh_id) or str(huh_id) == '' or str(huh_id) == 'nan':
                    id_match_status = "False|Unlisted"

                if pd.notna(huh_id) and str(huh_id) != '' and str(huh_id) != 'nan':
                    try:
                        huh_id_display = int(float(huh_id)) if '.' in str(huh_id) else int(huh_id)
                    except ValueError:
                        id_match_status = "False|Invalid_ID"
                        continue
                    id_cols = ['ASA_Botanist_ID', 'ASA_Botanist_ID_2', 'ASA_Botanist_ID_3', 'ASA_Botanist_ID_4']
                    master_ids = []
                    for col in id_cols:
                        if col in master_row and pd.notna(master_row[col]):
                            master_id = str(master_row[col])
                            if '.' in master_id:
                                master_id = str(int(float(master_id)))
                            master_ids.append(master_id)
                            if str(huh_id_display) == master_id:
                                id_match_status = f"True|{huh_id_display}"
                                break

                        if id_match_status == "False" and master_ids:
                            id_match_status = "False"  # IDs exist but don't match
                        elif id_match_status == "False":
                            id_match_status = "False|Unlisted_M"  # No IDs in master

                # Check country matches
                country_matches = get_country_matches(country, master_row) if country else {'FM_Country_match': "False", 'HUH_Country_match': "False"}
                
                # Check date matches
                date_matches = get_date_matches(avg_year, master_row) if avg_year else {'FM_Date_match': "False", 'HUH_Date_match': "False"}
                
                #For team matching, we need to exclude the current collector from the team check
                other_collectors = []
                for j in range(1, 7):
                    if j != i:
                        col_name = f'verbatimCollector{j}'
                        if col_name in row and pd.notna(row[col_name]):
                            other_collectors.append(row[col_name])
                
                collector_team_match = check_collector_team_match(
                    other_collectors,
                    master_row.get('Collector_Team'),
                    master_row.get('FM_Collector_Teams'),
                )
                
                if name_match:
                    # Handle NaN values in Collector_irn
                    collector_irn = master_row.get('Collector_irn', '')
                    if pd.isna(collector_irn) or collector_irn == '':
                        master_irn = ''
                    else:
                        master_irn = int(float(collector_irn))
                    
                    matches.append({
                        'master_name': master_row.get('Standard_Label_Name', ''),
                        'master_irn': master_irn,
                        'id_match': id_match_status,
                        'name_match': 'True',
                        'FM_Country_match': country_matches['FM_Country_match'],
                        'HUH_Country_match': country_matches['HUH_Country_match'],
                        'FM_Date_match': date_matches['FM_Date_match'],
                        'HUH_Date_match': date_matches['HUH_Date_match'],
                        'collector_team_match': collector_team_match,
                        'name_variants': ", ".join(name_variants[:3]) + ("..." if len(name_variants) > 3 else ""),
                        'is_match': True
                    })
                    has_match = True
            
            #if no match, create a single "no match" result
            if not has_match:
                secondary_results.append({
                    'Image_URL': image_url,
                    'barcode': barcode,
                    'collector_number': i,
                    'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                    'master_name': '',
                    'master_irn': '',
                    'master_name_variants': '',
                    'id_match': 'False|NoMatch',
                    'name_match': 'False|NoMatch',
                    'FM_Country_match': 'False|NoMatch',
                    'HUH_Country_match': 'False|NoMatch',
                    'FM_Date_match': 'False|NoMatch',
                    'HUH_Date_match': 'False|NoMatch',
                    'collector_team_match': 'False|NoMatch',
                    'score': 'NoMatch'
                })
            else:
                #Sort matches
                matches.sort(key=lambda x: (
                    x['id_match'].startswith('True'),
                    x['FM_Country_match'].startswith('True') or x['HUH_Country_match'].startswith('True'),
                    x['FM_Date_match'].startswith('True') or x['HUH_Date_match'].startswith('True'),
                    x['collector_team_match'].startswith('True')
                ), reverse=True)
                
                # Add all matches to results
                for match in matches:
                    # Calculate score
                    score_parts = ['Name']
                    if match['id_match'].startswith('True'):
                        score_parts.append('ID')
                    if match['FM_Country_match'].startswith('True') or match['HUH_Country_match'].startswith('True'):
                        score_parts.append('Country')
                    if match['FM_Date_match'].startswith('True') or match['HUH_Date_match'].startswith('True'):
                        score_parts.append('Date')
                    if match['collector_team_match'].startswith('True'):
                        score_parts.append('Team')
                    
                    secondary_results.append({
                        'Image_URL': image_url,
                        'barcode': barcode,
                        'collector_number': i,
                        'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                        'master_name': match['master_name'],
                        'master_irn': match['master_irn'],
                        'master_name_variants': match['name_variants'],
                        'id_match': match['id_match'],
                        'name_match': match['name_match'],
                        'FM_Country_match': match['FM_Country_match'],
                        'HUH_Country_match': match['HUH_Country_match'],
                        'FM_Date_match': match['FM_Date_match'],
                        'HUH_Date_match': match['HUH_Date_match'],
                        'collector_team_match': match['collector_team_match'],
                        'score': '|'.join(score_parts)
                    })
    
    # Create results dataframe
    results_df = pd.DataFrame(secondary_results)
    
    #Reorder columns
    cols = ['Image_URL', 'barcode', 'collector_number', 'tested_name', 'master_name', 'master_irn', 'master_name_variants',
            'id_match', 'name_match', 'FM_Country_match', 'HUH_Country_match', 
            'FM_Date_match', 'HUH_Date_match', 'collector_team_match', 'score']

    return results_df[cols]

def process_data(example_file, master_file, primary_output_file, secondary_output_file=None):
    #Load the data
    example_df = pd.read_csv(example_file) if example_file.endswith('.csv') else pd.read_excel(example_file)
    master_df = pd.read_csv(master_file) if master_file.endswith('.csv') else pd.read_excel(master_file)
    
    #Prepare dataframe for primary collectors
    primary_results = []
    
    # Run Through each row in the example file
    for _, row in example_df.iterrows():
        image_url = row.get('Image_URL', '')
        barcode = row['Barcode']
        collector_name = row.get('collectorName1', '')
        verbatim_name = row.get('verbatimCollector1', '')
        huh_id = row.get('HUH_BotanistID_1', '')
        country = row.get('countryName', '')
        min_date = row.get('minimumDate', '')
        max_date = row.get('maximumDate', '')
        
        #Look for brackets
        brackets_present = has_brackets(verbatim_name)
        
        #If no name present, create special result row and skip matching
        if pd.isna(collector_name) and pd.isna(verbatim_name):
            primary_results.append({
                'Image_URL': image_url,
                'barcode': barcode,
                'collector_number': 1,
                'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                'match_rank': 1,
                'master_name': '',
                'master_irn': '',
                'master_name_variants': '',
                'id_match': 'False|NoName',
                'name_match': 'False|NoName',
                'FM_Country_match': 'False|NoName',
                'HUH_Country_match': 'False|NoName',
                'FM_Date_match': 'False|NoName',
                'HUH_Date_match': 'False|NoName',
                'collector_team_match': 'False|NoName',
                'score': 'NONAME'
            })
            continue            

        # If brackets present, create a special result row and skip matching
        if brackets_present:
            primary_results.append({
                'Image_URL': image_url,                
                'barcode': barcode,
                'collector_number': 1,
                'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                'match_rank': 1,
                'master_name': '',
                'master_irn': '',
                'master_name_variants': '',
                'id_match': 'False|Brackets',
                'name_match': 'False|Brackets',
                'FM_Country_match': 'False|Brackets',
                'HUH_Country_match': 'False|Brackets',
                'FM_Date_match': 'False|Brackets',
                'HUH_Date_match': 'False|Brackets',
                'collector_team_match': 'False|Brackets',
                             'score': 'BRACKETS'
            })
            continue
        
        # Get other collector names for team matching
        other_collectors = []
        for i in range(2, 7):
            col_name = f'verbatimCollector{i}'
            if col_name in row and pd.notna(row[col_name]):
                other_collectors.append(row[col_name])
        
        #Get year from dates
        min_year = extract_year(str(min_date)) if pd.notna(min_date) else None
        max_year = extract_year(str(max_date)) if pd.notna(max_date) else None
        years = [y for y in [min_year, max_year] if y is not None]
        avg_year = sum(years) / len(years) if years else None
        
        #Find matches in master
        matches = []
        
        for _, master_row in master_df.iterrows():
            # Get all name variants from master
            name_variants = []
            for col in master_row.index:
                if col.startswith('Variant_name') or col in ['Standard_Label_Name', 'nam_NamFullName', 'nam_NamBriefName', 'OtherNames']:
                    val = master_row.get(col, '')
                    if pd.notna(val) and val != '':
                        if isinstance(val, str):
                            name_variants.append(val)
            
            # First check name match. If no match skip to next row
            name_match = process_name_match(collector_name, verbatim_name, name_variants)
            if not name_match:
                continue
            
            #Only proceed with other checks if name matches
            id_match_status = "False"
            if pd.isna(huh_id) or str(huh_id) == '' or str(huh_id) == 'nan':
                id_match_status = "False|Unlisted"
            else:
                # Convert huh_id
                try:
                    huh_id_display = int(float(huh_id)) if '.' in str(huh_id) else int(huh_id)
                except ValueError:
                    id_match_status = "False|Invalid_ID"
                master_ids = []
                id_cols = ['ASA_Botanist_ID', 'ASA_Botanist_ID_2', 'ASA_Botanist_ID_3', 'ASA_Botanist_ID_4']

                for col in id_cols:
                    if col in master_row and pd.notna(master_row[col]):
                        #Convert master IDs to int
                        master_id = str(master_row[col])
                        if '.' in master_id:
                            master_id = str(int(float(master_id)))
                        master_ids.append(master_id)
                        if str(huh_id_display) == master_id:
                            id_match_status = f"True|{huh_id_display}"
                            break
                
                if id_match_status == "False" and master_ids:
                    id_match_status = "False"  # IDs exist but don't match
                elif id_match_status == "False":
                    id_match_status = "False|Unlisted_M"  # No IDs in master

            # Check country matches
            country_matches = get_country_matches(country, master_row) if country else {'FM_Country_match': "False", 'HUH_Country_match': "False"}
            
            # Check date matches
            date_matches = get_date_matches(avg_year, master_row) if avg_year else {'FM_Date_match': "False", 'HUH_Date_match': "False"}
            
            collector_team_match = check_collector_team_match(
                other_collectors,
                master_row.get('Collector_Team'),
                master_row.get('FM_Collector_Teams'),
            )
            
            # Handle NaN values in Collector_irn
            collector_irn = master_row.get('Collector_irn', '')
            if pd.isna(collector_irn) or collector_irn == '':
                master_irn = ''
            else:
                master_irn = int(float(collector_irn))
            
            matches.append({
                'master_name': master_row.get('Standard_Label_Name', ''),
                'master_irn': master_irn,
                'id_match': id_match_status,
                'name_match': 'True',
                'FM_Country_match': country_matches['FM_Country_match'],
                'HUH_Country_match': country_matches['HUH_Country_match'],
                'FM_Date_match': date_matches['FM_Date_match'],
                'HUH_Date_match': date_matches['HUH_Date_match'],
                'collector_team_match': collector_team_match,
                'name_variants': ", ".join(name_variants[:3]) + ("..." if len(name_variants) > 3 else "")
            })
        
        #if no matches found but we have a name, add a single "no match" row
        if not matches and (pd.notna(collector_name) or pd.notna(verbatim_name)):
            primary_results.append({
                'Image_URL': image_url,
                'barcode': barcode,
                'collector_number': 1,
                'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                'match_rank': 1,
                'master_name': '',
                'master_irn': '',
                'master_name_variants': '',
                'id_match': 'False|NoMatch',
                'name_match': 'False|NoMatch',
                'FM_Country_match': 'False|NoMatch',
                'HUH_Country_match': 'False|NoMatch',
                'FM_Date_match': 'False|NoMatch',
                'HUH_Date_match': 'False|NoMatch',
                'collector_team_match': 'False|NoMatch',
                'score': 'NoMatch'
            })
        else:
            # Sort matches
            matches.sort(key=lambda x: (
                x['id_match'].startswith('True'),
                x['FM_Country_match'].startswith('True') or x['HUH_Country_match'].startswith('True'),
                x['FM_Date_match'].startswith('True') or x['HUH_Date_match'].startswith('True'),
                x['collector_team_match'].startswith('True')
            ), reverse=True)
            
            # Add all name matches to results
            for i, match in enumerate(matches):
                score_parts = ['Name']
                if match['id_match'].startswith('True'):
                    score_parts.append('ID')
                if match['FM_Country_match'].startswith('True') or match['HUH_Country_match'].startswith('True'):
                    score_parts.append('Country')
                if match['FM_Date_match'].startswith('True') or match['HUH_Date_match'].startswith('True'):
                    score_parts.append('Date')
                if match['collector_team_match'].startswith('True'):
                    score_parts.append('Team')
                
                primary_results.append({
                    'Image_URL': image_url,
                    'barcode': barcode,
                    'collector_number': 1,
                    'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                    'match_rank': i+1,
                    'master_name': match['master_name'],
                    'master_irn': match['master_irn'],
                    'master_name_variants': match['name_variants'],
                    'id_match': match['id_match'],
                    'name_match': match['name_match'],
                    'FM_Country_match': match['FM_Country_match'],
                    'HUH_Country_match': match['HUH_Country_match'],
                    'FM_Date_match': match['FM_Date_match'],
                    'HUH_Date_match': match['HUH_Date_match'],
                    'collector_team_match': match['collector_team_match'],
                    'score': '|'.join(score_parts)
                })
    
    # Create primary results dataframe
    primary_results_df = pd.DataFrame(primary_results)
    
    # Reorder columns
    cols = ['Image_URL', 'barcode', 'collector_number', 'tested_name', 'match_rank', 'master_name', 'master_irn', 'master_name_variants',
            'id_match', 'name_match', 'FM_Country_match', 'HUH_Country_match', 
            'FM_Date_match', 'HUH_Date_match', 'collector_team_match', 'score']

    primary_results_df = primary_results_df[cols]
    
    # Save primary results
    if primary_output_file.endswith('.csv'):
        primary_results_df.to_csv(primary_output_file, index=False)
    else:
        primary_results_df.to_excel(primary_output_file, index=False)
    
    # Process secondary collectors if output file specified
    if secondary_output_file:
        secondary_results_df = process_secondary_collectors(example_df, master_df)
        
        # Save secondary results
        if secondary_output_file.endswith('.csv'):
            secondary_results_df.to_csv(secondary_output_file, index=False)
        else:
            secondary_results_df.to_excel(secondary_output_file, index=False)
            

def create_modified_max_sheet(example_file, primary_results_file, secondary_results_file, output_file):
    """Create a modified version of the example Max sheet with top validation results."""
    
    # Read input files
    example_df = pd.read_csv(example_file)
    primary_df = pd.read_csv(primary_results_file)
    secondary_df = pd.read_csv(secondary_results_file)
    
    # Get top results (rank 1) for primary collectors
    top_primary = primary_df[primary_df['match_rank'] == 1].copy()
    
    # Get top results for secondary collectors (they don't have match_rank, so get first occurrence per barcode/collector_number)
    top_secondary = secondary_df.drop_duplicates(subset=['barcode', 'collector_number'], keep='first').copy()
    
    # Create modified dataframe starting with original
    modified_df = example_df.copy()
    
    # Format HUH Botanist IDs to remove .0
    for i in range(1, 6):
        col_name = f'HUH_BotanistID_{i}'
        if col_name in modified_df.columns:
            modified_df[col_name] = modified_df[col_name].apply(format_numeric_id)
    
    # Add primary collector results
    modified_df['primary_master_irn'] = ''
    modified_df['primary_master_name'] = ''
    modified_df['primary_score'] = ''
    
    # Add secondary collector results (up to 4 co-collectors)
    for i in range(2, 6):  # collectors 2-5
        modified_df[f'secondary_{i}_master_irn'] = ''
        modified_df[f'secondary_{i}_master_name'] = ''
        modified_df[f'secondary_{i}_score'] = ''
    
    # Fill in primary collector data
    for idx, row in modified_df.iterrows():
        barcode = row['Barcode']
        
        # Find primary collector match
        primary_match = top_primary[top_primary['barcode'] == barcode]
        if not primary_match.empty:
            match = primary_match.iloc[0]
            modified_df.at[idx, 'primary_master_irn'] = format_numeric_id(match['master_irn'])
            modified_df.at[idx, 'primary_master_name'] = match['master_name']
            modified_df.at[idx, 'primary_score'] = match['score']
        
        # Find secondary collector matches
        secondary_matches = top_secondary[top_secondary['barcode'] == barcode]
        for _, sec_match in secondary_matches.iterrows():
            collector_num = sec_match['collector_number']
            if 2 <= collector_num <= 5:
                modified_df.at[idx, f'secondary_{collector_num}_master_irn'] = format_numeric_id(sec_match['master_irn'])
                modified_df.at[idx, f'secondary_{collector_num}_master_name'] = sec_match['master_name']
                modified_df.at[idx, f'secondary_{collector_num}_score'] = sec_match['score']
    
    # Reorder columns to place IRNs and Botanist IDs before collector names
    cols = list(modified_df.columns)
    new_cols = []
    
    # Add initial columns up to first collector
    for col in cols:
        if col == 'HUH_BotanistID_1':
            break
        new_cols.append(col)
    
    # Add collector 1 data in order: ID, UUID, name, verbatim
    new_cols.extend(['primary_master_irn', 'HUH_BotanistID_1', 'HUH_UUID_1', 'collectorName1', 'verbatimCollector1', 'primary_master_name', 'primary_score'])
    
    # Add collectors 2-5 in order: ID, UUID, name, verbatim, master_irn, master_name, score
    for i in range(2, 6):
        potential_cols = [f'secondary_{i}_master_irn', f'HUH_BotanistID_{i}', f'HUH_GUID_{i}', f'collectorName{i}', f'verbatimCollector{i}', f'secondary_{i}_master_name', f'secondary_{i}_score']
        for col in potential_cols:
            if col in cols:
                new_cols.append(col)
    
    # Add remaining columns
    for col in cols:
        if col not in new_cols:
            new_cols.append(col)
    
    # Reorder the dataframe - only use columns that exist
    existing_cols = [col for col in new_cols if col in modified_df.columns]
    modified_df = modified_df[existing_cols]
    
    # Format other numeric columns that might have .0
    numeric_cols = ['Multimedia_IRN', 'Taxon_IRN', 'CatologueNumber', 'Locality_IRN']
    for col in numeric_cols:
        if col in modified_df.columns:
            modified_df[col] = modified_df[col].apply(format_numeric_id)
    
    # Save the modified sheet
    modified_df.to_csv(output_file, index=False)
    print(f"Modified Max sheet created: {output_file}")

def format_numeric_id(value):
    """Format numeric ID to remove .0 if it's a whole number."""
    if pd.isna(value) or value == '':
        return ''
    try:
        num = float(value)
        if num.is_integer():
            return str(int(num))
        return str(num)
    except:
        return str(value)

def create_collector_results_summary(example_file, primary_results_file, secondary_results_file, output_file):
    """Create a summary CSV with just collectors, IRNs, and Botanist IDs."""
    
    # Read input files
    example_df = pd.read_csv(example_file)
    primary_df = pd.read_csv(primary_results_file)
    secondary_df = pd.read_csv(secondary_results_file)
    
    # Get top results
    top_primary = primary_df[primary_df['match_rank'] == 1].copy()
    top_secondary = secondary_df.drop_duplicates(subset=['barcode', 'collector_number'], keep='first').copy()
    
    summary_data = []
    
    for _, row in example_df.iterrows():
        barcode = row['Barcode']
        
        # Primary collector
        primary_match = top_primary[top_primary['barcode'] == barcode]
        if not primary_match.empty:
            match = primary_match.iloc[0]
            summary_data.append({
                'Barcode': barcode,
                'Collector_Number': 1,
                'Master_IRN': format_numeric_id(match['master_irn']),
                'HUH_BotanistID': format_numeric_id(row.get('HUH_BotanistID_1', '')),
                'CollectorName': row.get('collectorName1', ''),
                'VerbatimCollector': row.get('verbatimCollector1', ''),
                'Master_Name': match['master_name'],
                'Score': match['score']
            })
        
        # Secondary collectors
        secondary_matches = top_secondary[top_secondary['barcode'] == barcode]
        for _, sec_match in secondary_matches.iterrows():
            collector_num = sec_match['collector_number']
            if 2 <= collector_num <= 5:
                summary_data.append({
                    'Barcode': barcode,
                    'Collector_Number': collector_num,
                    'Master_IRN': format_numeric_id(sec_match['master_irn']),
                    'HUH_BotanistID': format_numeric_id(row.get(f'HUH_BotanistID_{collector_num}', '')),
                    'CollectorName': row.get(f'collectorName{collector_num}', ''),
                    'VerbatimCollector': row.get(f'verbatimCollector{collector_num}', ''),
                    'Master_Name': sec_match['master_name'],
                    'Score': sec_match['score']
                })
    
    # Create and save summary dataframe
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(output_file, index=False)
    print(f"Collector results summary created: {output_file}")

# =============================================================================
# FILE PATH CONFIGURATION
# =============================================================================
# Update these paths as needed for your data files

# Input files
EXAMPLE_FILE = r'../Dates/Transcription_FIELD_2025-07-29-09-15_transcriptionTimeStamp_0_25000.csv'  # New data from Max
MASTER_FILE = r'/home/riley/Documents/GitHub/FieldMuseum-EMU-Master/Validations/Master_Collector(newmain).csv'  # Master collector database

# Output files
PRIMARY_OUTPUT_FILE = 'validation_results(Primary).csv'
SECONDARY_OUTPUT_FILE = 'validation_results(Secondary).csv'
MODIFIED_MAX_SHEET = 'Modified_Max_Sheet_with_Top_Results.csv'
COLLECTOR_SUMMARY = 'Collector_Results_Summary.csv'

# =============================================================================

if __name__ == "__main__":
    import os
    
    # Verify input files exist
    if not os.path.exists(EXAMPLE_FILE):
        print(f"Error: Input file not found: {EXAMPLE_FILE}")
        print("Please update EXAMPLE_FILE path in the configuration section.")
        exit(1)
    
    if not os.path.exists(MASTER_FILE):
        print(f"Error: Master collector file not found: {MASTER_FILE}")
        exit(1)
    
    print(f"Processing input file: {EXAMPLE_FILE}")
    print(f"Using master collector file: {MASTER_FILE}")
    
    # Run validation
    process_data(EXAMPLE_FILE, MASTER_FILE, PRIMARY_OUTPUT_FILE, SECONDARY_OUTPUT_FILE)
    
    print(f"\nValidation completed successfully!")
    print(f"Primary results: {PRIMARY_OUTPUT_FILE}")
    print(f"Secondary results: {SECONDARY_OUTPUT_FILE}")
    
    # Create modified Max sheet with top results
    create_modified_max_sheet(EXAMPLE_FILE, PRIMARY_OUTPUT_FILE, SECONDARY_OUTPUT_FILE, MODIFIED_MAX_SHEET)
    print(f"Modified Max sheet: {MODIFIED_MAX_SHEET}")
    
    # Create collector results summary
    create_collector_results_summary(EXAMPLE_FILE, PRIMARY_OUTPUT_FILE, SECONDARY_OUTPUT_FILE, COLLECTOR_SUMMARY)
    print(f"Collector summary: {COLLECTOR_SUMMARY}")