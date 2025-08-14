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

Created by: Alex Wcislo and Riley Herbst
'''

import pandas as pd
import unicodedata
import argparse
import os

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

# New: weighted scoring for rigorous IRN selection

def _compute_match_score(match: dict) -> tuple[int, list[str]]:
    """Compute a weighted score and score labels based on all match facets.
    Returns (score_value, labels). Labels follow existing 'Name|ID|Country|Date|Team' convention."""
    score = 0
    labels: list[str] = []

    # Name
    if str(match.get('name_match', '')).startswith('True'):
        score += 10
        labels.append('Name')

    # ID (strongest signal)
    id_val = str(match.get('id_match', ''))
    if id_val.startswith('True'):
        score += 100
        labels.append('ID')

    # Country
    fm_country = str(match.get('FM_Country_match', ''))
    huh_country = str(match.get('HUH_Country_match', ''))
    fm_true = fm_country.startswith('True')
    huh_true = huh_country.startswith('True')
    if fm_true and huh_true:
        score += 25
        if 'Country' not in labels:
            labels.append('Country')
    elif fm_true or huh_true:
        score += 15
        if 'Country' not in labels:
            labels.append('Country')

    # Date
    fm_date = str(match.get('FM_Date_match', ''))
    huh_date = str(match.get('HUH_Date_match', ''))
    fm_d_true = fm_date.startswith('True')
    huh_d_true = huh_date.startswith('True')
    if fm_d_true and huh_d_true:
        score += 30
        if 'Date' not in labels:
            labels.append('Date')
    elif fm_d_true:
        score += 20
        if 'Date' not in labels:
            labels.append('Date')
    elif huh_d_true:
        score += 15
        if 'Date' not in labels:
            labels.append('Date')

    # Team
    team = str(match.get('collector_team_match', ''))
    if team.startswith('True'):
        # reward number of team name hits when available (True|<count>)
        try:
            parts = team.split('|')
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        except Exception:
            count = 1
        score += 5 + 2 * max(1, count)
        labels.append('Team')

    return score, labels

def get_master_display_name(master_row: pd.Series) -> str:
    """Return the best available display name for a master row using a fallback chain."""
    def _clean(v):
        return str(v).strip() if pd.notna(v) else ''

    # 1) Preferred labeled names
    for col in ['Standard_Label_Name', 'nam_NamFullName', 'nam_NamBriefName']:
        val = _clean(master_row.get(col))
        if val:
            return val

    # 2) Construct First Last when available
    first = _clean(master_row.get('nam_NamFirst'))
    last = _clean(master_row.get('nam_NamLast'))
    if first and last:
        return f"{first} {last}"

    # 3) Try variants and OtherNames (take the first token if delimited)
    variant_cols = ['Variant_name'] + [f'Variant_name_{i}' for i in range(2, 12)] + ['OtherNames']
    for col in variant_cols:
        val = _clean(master_row.get(col))
        if val:
            if col == 'OtherNames':
                for sep in [';', '|', ',']:
                    if sep in val:
                        token = val.split(sep)[0].strip()
                        if token:
                            return token
            return val

    # 4) Last resort: GUID (if present) or empty
    guid = _clean(master_row.get('GUID'))
    return guid

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
            country = row.get('CountryName', '')
            min_date = row.get('MinimumDate', '')
            max_date = row.get('MaximumDate', '')
            
            # Get year from dates
            min_year = extract_year(str(min_date)) if pd.notna(min_date) else None
            max_year = extract_year(str(max_date)) if pd.notna(max_date) else None
            years = [y for y in [min_year, max_year] if y is not None]
            avg_year = sum(years) / len(years) if years else None
            
            # Build list of other co-collectors (exclude current)
            other_collectors = []
            for j in range(1, 7):
                if j != i:
                    col_name = f'verbatimCollector{j}'
                    if col_name in row and pd.notna(row[col_name]):
                        other_collectors.append(row[col_name])
            
            # Find matches in master
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
                
                # Name and ID matching
                name_to_match = verbatim_name if verbatim_name and not pd.isna(verbatim_name) else collector_name
                name_bool = process_name_match('', name_to_match, name_variants) if name_to_match else False
                
                # ID match if exists for this collector
                id_match_status = "False"
                huh_id = row.get(f'HUH_BotanistID_{i}', '')
                if pd.isna(huh_id) or str(huh_id) == '' or str(huh_id) == 'nan':
                    id_match_status = "False|Unlisted"
                else:
                    # Extract numeric part if possible, otherwise use as is
                    huh_id_str = str(huh_id)
                    try:
                        if '.' in huh_id_str:
                            huh_id_display = int(float(huh_id_str))
                        else:
                            import re
                            numeric_match = re.search(r'\d+', huh_id_str)
                            if numeric_match:
                                huh_id_display = int(numeric_match.group())
                            else:
                                huh_id_display = huh_id_str
                    except ValueError:
                        huh_id_display = huh_id_str
                    
                    id_cols = ['ASA_Botanist_ID', 'ASA_Botanist_ID_2', 'ASA_Botanist_ID_3', 'ASA_Botanist_ID_4']
                    master_ids = []
                    for col in id_cols:
                        if col in master_row and pd.notna(master_row[col]):
                            mid = str(master_row[col])
                            if '.' in mid and all(c.isdigit() or c == '.' for c in mid):
                                try:
                                    mid = str(int(float(mid)))
                                except ValueError:
                                    pass
                            master_ids.append(mid)
                    
                    # Compare after collecting master ids
                    if 'huh_id_display' in locals() and not isinstance(huh_id_display, float):
                        hid = str(huh_id_display)
                        for mid in master_ids:
                            if hid == mid or hid in mid or mid in hid:
                                id_match_status = f"True|{huh_id_display}"
                                break
                    
                    if id_match_status == "False" and master_ids:
                        id_match_status = "False"
                    elif id_match_status == "False":
                        id_match_status = "False|Unlisted_M"

                # Country and date matches
                country_matches = get_country_matches(country, master_row) if country else {'FM_Country_match': "False", 'HUH_Country_match': "False"}
                date_matches = get_date_matches(avg_year, master_row) if avg_year else {'FM_Date_match': "False", 'HUH_Date_match': "False"}
                
                # Team matching using other co-collectors
                collector_team_match = check_collector_team_match(
                    other_collectors,
                    master_row.get('Collector_Team'),
                    master_row.get('FM_Collector_Teams'),
                )
                
                # Only include if name OR ID matches
                if name_bool or str(id_match_status).startswith('True'):
                    m = {
                        'master_name': get_master_display_name(master_row),
                        'master_irn': int(master_row.get('Collector_irn', '0')) if pd.notna(master_row.get('Collector_irn', '')) else '',
                        'id_match': id_match_status,
                        'name_match': 'True' if name_bool else 'False',
                        'FM_Country_match': country_matches['FM_Country_match'],
                        'HUH_Country_match': country_matches['HUH_Country_match'],
                        'FM_Date_match': date_matches['FM_Date_match'],
                        'HUH_Date_match': date_matches['HUH_Date_match'],
                        'collector_team_match': collector_team_match,
                        'name_variants': ", ".join(name_variants[:3]) + ("..." if len(name_variants) > 3 else "")
                    }
                    score_value, score_labels = _compute_match_score(m)
                    m['__score_value'] = score_value
                    m['__score_labels'] = score_labels
                    matches.append(m)
            
            if not matches:
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
                # Sort using weighted score
                matches.sort(key=lambda x: x.get('__score_value', 0), reverse=True)
                
                # Add all matches to results
                for match in matches:
                    secondary_results.append({
                        'Image_URL': image_url,
                        'barcode': barcode,
                        'collector_number': i,
                        'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbbatim_name or collector_name,
                        'master_name': match['master_name'],
                        'master_irn': int(match['master_irn']) if pd.notna(match['master_irn']) and match['master_irn'] != '' else '',
                        'master_name_variants': match['name_variants'],
                        'id_match': match['id_match'],
                        'name_match': match['name_match'],
                        'FM_Country_match': match['FM_Country_match'],
                        'HUH_Country_match': match['HUH_Country_match'],
                        'FM_Date_match': match['FM_Date_match'],
                        'HUH_Date_match': match['HUH_Date_match'],
                        'collector_team_match': match['collector_team_match'],
                        'score': '|'.join(match.get('__score_labels', [])) or 'Name'
                    })

    # Create results dataframe
    results_df = pd.DataFrame(secondary_results)
    
    #Reorder columns
    cols = ['Image_URL', 'barcode', 'collector_number', 'tested_name', 'master_name', 'master_irn', 'master_name_variants',
            'id_match', 'name_match', 'FM_Country_match', 'HUH_Country_match', 
            'FM_Date_match', 'HUH_Date_match', 'collector_team_match', 'score']

    return results_df[cols]

def process_data(example_file, master_file, output_dir):
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
        country = row.get('CountryName', '')
        min_date = row.get('MinimumDate', '')
        max_date = row.get('MaximumDate', '')
        
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
            
            # Name check
            name_bool = process_name_match(collector_name, verbatim_name, name_variants)

            # ID check (more flexible)
            id_match_status = "False"
            if pd.isna(huh_id) or str(huh_id) == '' or str(huh_id) == 'nan':
                id_match_status = "False|Unlisted"
            else:
                huh_id_str = str(huh_id)
                try:
                    if '.' in huh_id_str:
                        huh_id_display = int(float(huh_id_str))
                    else:
                        import re
                        numeric_match = re.search(r'\d+', huh_id_str)
                        if numeric_match:
                            huh_id_display = int(numeric_match.group())
                        else:
                            huh_id_display = huh_id_str
                except ValueError:
                    huh_id_display = huh_id_str
                
                master_ids = []
                id_cols = ['ASA_Botanist_ID', 'ASA_Botanist_ID_2', 'ASA_Botanist_ID_3', 'ASA_Botanist_ID_4']
                for col in id_cols:
                    if col in master_row and pd.notna(master_row[col]):
                        mid = str(master_row[col])
                        if '.' in mid and all(c.isdigit() or c == '.' for c in mid):
                            try:
                                mid = str(int(float(mid)))
                            except ValueError:
                                pass
                        master_ids.append(mid)
                if 'huh_id_display' in locals() and not isinstance(huh_id_display, float):
                    hid = str(huh_id_display)
                    for mid in master_ids:
                        if hid == mid or hid in mid or mid in hid:
                            id_match_status = f"True|{huh_id_display}"
                            break
                if id_match_status == "False" and master_ids:
                    id_match_status = "False"
                elif id_match_status == "False":
                    id_match_status = "False|Unlisted_M"

            # Country and date
            country_matches = get_country_matches(country, master_row) if country else {'FM_Country_match': "False", 'HUH_Country_match': "False"}
            date_matches = get_date_matches(avg_year, master_row) if avg_year else {'FM_Date_match': "False", 'HUH_Date_match': "False"}
            
            collector_team_match = check_collector_team_match(
                other_collectors,
                master_row.get('Collector_Team'),
                master_row.get('FM_Collector_Teams'),
            )
            
            # Only include if name OR ID matches
            if name_bool or str(id_match_status).startswith('True'):
                m = {
                    'master_name': get_master_display_name(master_row),
                    'master_irn': int(master_row.get('Collector_irn', '0')) if pd.notna(master_row.get('Collector_irn', '')) else '',
                    'id_match': id_match_status,
                    'name_match': 'True' if name_bool else 'False',
                    'FM_Country_match': country_matches['FM_Country_match'],
                    'HUH_Country_match': country_matches['HUH_Country_match'],
                    'FM_Date_match': date_matches['FM_Date_match'],
                    'HUH_Date_match': date_matches['HUH_Date_match'],
                    'collector_team_match': collector_team_match,
                    'name_variants': ", ".join(name_variants[:3]) + ("..." if len(name_variants) > 3 else "")
                }
                score_value, score_labels = _compute_match_score(m)
                m['__score_value'] = score_value
                m['__score_labels'] = score_labels
                matches.append(m)
        
        #if no matches found but we have a name, add a single "no match" row
        if not matches and (pd.notna(collector_name) or pd.notna(verbatim_name)):
            primary_results.append({
                'Image_URL': image_url,
                'barcode': barcode,
                'collector_number': 1,
                'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbbatim_name or collector_name,
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
            # Sort using weighted score
            matches.sort(key=lambda x: x.get('__score_value', 0), reverse=True)
            
            # Add all name/ID matches to results
            for i, match in enumerate(matches):
                primary_results.append({
                    'Image_URL': image_url,
                    'barcode': barcode,
                    'collector_number': 1,
                    'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbbatim_name or collector_name,
                    'match_rank': i+1,
                    'master_name': match['master_name'],
                    'master_irn': int(match['master_irn']) if pd.notna(match['master_irn']) and match['master_irn'] != '' else '',
                    'master_name_variants': match['name_variants'],
                    'id_match': match['id_match'],
                    'name_match': match['name_match'],
                    'FM_Country_match': match['FM_Country_match'],
                    'HUH_Country_match': match['HUH_Country_match'],
                    'FM_Date_match': match['FM_Date_match'],
                    'HUH_Date_match': match['HUH_Date_match'],
                    'collector_team_match': match['collector_team_match'],
                    'score': '|'.join(match.get('__score_labels', [])) or 'Name'
                })
    
    # Create primary results dataframe
    primary_results_df = pd.DataFrame(primary_results)
    
    # Reorder columns
    cols = ['Image_URL', 'barcode', 'collector_number', 'tested_name', 'match_rank', 'master_name', 'master_irn', 'master_name_variants',
            'id_match', 'name_match', 'FM_Country_match', 'HUH_Country_match', 
            'FM_Date_match', 'HUH_Date_match', 'collector_team_match', 'score']

    primary_results_df = primary_results_df[cols]
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # File paths inside output directory
    primary_output_path = os.path.join(output_dir, 'validation_results(Primary).csv')
    secondary_output_path = os.path.join(output_dir, 'validation_results(Secondary).csv')
    modified_output_path = os.path.join(output_dir, 'Modified_Max_Sheet_with_Top_Results.csv')

    # Save primary results
    primary_results_df.to_csv(primary_output_path, index=False)
    
    # Process secondary collectors (needed for modified sheet as well)
    secondary_results_df = process_secondary_collectors(example_df, master_df)
    
    # Always save secondary results
    secondary_results_df.to_csv(secondary_output_path, index=False)

    # Build modified input sheet with top validated results
    modified_df = example_df.copy()

    # Top primary per barcode
    if not primary_results_df.empty:
        top_primary = (
            primary_results_df.sort_values(['barcode', 'match_rank'])
            .groupby('barcode', as_index=False)
            .first()
        )
        pcols = ['barcode','tested_name','master_name','master_irn','id_match','name_match',
                 'FM_Country_match','HUH_Country_match','FM_Date_match','HUH_Date_match','collector_team_match','score']
        top_primary = top_primary[pcols].copy()
        top_primary.rename(columns={
            'barcode':'Barcode',
            'tested_name':'Top_Primary_tested_name',
            'master_name':'Top_Primary_master_name',
            'master_irn':'Top_Primary_master_irn',
            'id_match':'Top_Primary_id_match',
            'name_match':'Top_Primary_name_match',
            'FM_Country_match':'Top_Primary_FM_Country_match',
            'HUH_Country_match':'Top_Primary_HUH_Country_match',
            'FM_Date_match':'Top_Primary_FM_Date_match',
            'HUH_Date_match':'Top_Primary_HUH_Date_match',
            'collector_team_match':'Top_Primary_collector_team_match',
            'score':'Top_Primary_score'
        }, inplace=True)
        modified_df = modified_df.merge(top_primary, on='Barcode', how='left')

    # Top secondary per barcode and collector_number, pivot to wide
    if not secondary_results_df.empty:
        top_sec = secondary_results_df.groupby(['barcode','collector_number'], as_index=False).first()
        for cn in sorted(top_sec['collector_number'].unique()):
            sec_n = top_sec[top_sec['collector_number']==cn].copy()
            scols = ['barcode','tested_name','master_name','master_irn','id_match','name_match',
                     'FM_Country_match','HUH_Country_match','FM_Date_match','HUH_Date_match','collector_team_match','score']
            sec_n = sec_n[scols]
            rename_map = {
                'barcode':'Barcode',
                'tested_name':f'Top_Sec{cn}_tested_name',
                'master_name':f'Top_Sec{cn}_master_name',
                'master_irn':f'Top_Sec{cn}_master_irn',
                'id_match':f'Top_Sec{cn}_id_match',
                'name_match':f'Top_Sec{cn}_name_match',
                'FM_Country_match':f'Top_Sec{cn}_FM_Country_match',
                'HUH_Country_match':f'Top_Sec{cn}_HUH_Country_match',
                'FM_Date_match':f'Top_Sec{cn}_FM_Date_match',
                'HUH_Date_match':f'Top_Sec{cn}_HUH_Date_match',
                'collector_team_match':f'Top_Sec{cn}_collector_team_match',
                'score':f'Top_Sec{cn}_score',
            }
            sec_n.rename(columns=rename_map, inplace=True)
            modified_df = modified_df.merge(sec_n, on='Barcode', how='left')

    # Clean and organize the modified sheet
    mod_clean = modified_df.copy()

    # 1) Treat empty strings as NaN and drop columns that are entirely empty
    mod_clean = mod_clean.replace('', pd.NA)
    mod_clean.dropna(axis=1, how='all', inplace=True)

    # 2) Build an ordered column list: base info -> primary top -> secondary tops -> remaining
    def _present(cols):
        return [c for c in cols if c in mod_clean.columns]

    base_cols = _present([
        'Image_URL', 'Barcode', 'CountryName', 'MinimumDate', 'MaximumDate',
        'collectorName1', 'verbatimCollector1', 'HUH_BotanistID_1'
    ])

    primary_cols = _present([
        'Top_Primary_tested_name', 'Top_Primary_master_name', 'Top_Primary_master_irn',
        'Top_Primary_id_match', 'Top_Primary_name_match',
        'Top_Primary_FM_Country_match', 'Top_Primary_HUH_Country_match',
        'Top_Primary_FM_Date_match', 'Top_Primary_HUH_Date_match',
        'Top_Primary_collector_team_match', 'Top_Primary_score'
    ])

    secondary_cols = []
    for cn in range(2, 7):
        secondary_cols.extend(_present([
            f'collectorName{cn}', f'verbatimCollector{cn}', f'HUH_BotanistID_{cn}',
            f'Top_Sec{cn}_tested_name', f'Top_Sec{cn}_master_name', f'Top_Sec{cn}_master_irn',
            f'Top_Sec{cn}_id_match', f'Top_Sec{cn}_name_match',
            f'Top_Sec{cn}_FM_Country_match', f'Top_Sec{cn}_HUH_Country_match',
            f'Top_Sec{cn}_FM_Date_match', f'Top_Sec{cn}_HUH_Date_match',
            f'Top_Sec{cn}_collector_team_match', f'Top_Sec{cn}_score'
        ]))

    selected_order = base_cols + primary_cols + secondary_cols
    remaining_cols = [c for c in mod_clean.columns if c not in selected_order]
    ordered_cols = selected_order + remaining_cols

    mod_clean = mod_clean[ordered_cols]

    # Write modified sheet
    mod_clean.to_csv(modified_output_path, index=False)

    return {
        'primary': primary_output_path,
        'secondary': secondary_output_path,
        'modified': modified_output_path,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate collector records against the master collector sheet and output results."
    )
    parser.add_argument(
        "-i", "--input", dest="example_file", required=True,
        help="Path to the input (example) file to validate (.csv or .xlsx)"
    )
    parser.add_argument(
        "-m", "--master", dest="master_file", required=True,
        help="Path to the master collector file (.csv or .xlsx)"
    )
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", required=True,
        help="Directory to write all outputs (Primary, Secondary, Modified). Will be created if it does not exist."
    )

    args = parser.parse_args()

    paths = process_data(
        example_file=args.example_file,
        master_file=args.master_file,
        output_dir=args.output_dir,
    )

    print(f"Validation completed. Primary -> {paths['primary']}; Secondary -> {paths['secondary']}; Modified -> {paths['modified']}")