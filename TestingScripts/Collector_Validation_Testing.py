'''
Field Museum Validation Script

Purpose:
Validates primary and co-collector records against the master collector spreadsheet,
checking for name matches, ID matches, country matches, date matches, and team association matches. 
Generates detailed validation reports for both primary and co-collectors with separate validation
results for Field Museum (FM) and Harvard University Herbaria (HUH) sources.

All master names in output are labeled with their source (FM or HUH) to indicate data origin.

FIELD ORGANIZATION:
This script processes and validates data from two main sources with separate result columns:

=== FIELD MUSEUM (FM) FIELDS ===
- Name fields: Standard_Label_Name, Variant_name, Variant_name_2-11
- Country validation: FM_Countries → FM_Country_match
- Date validation: date_range_FM → FM_Date_match
- Team fields: FM_Collector_Teams → FM_Team_match

=== HARVARD UNIVERSITY HERBARIA (HUH) FIELDS ===
- Name fields: nam_NamFullName, nam_NamBriefName, nam_NamFirst, nam_NamLast, OtherNames
- ID fields: ASA_Botanist_ID, ASA_Botanist_ID_2, ASA_Botanist_ID_3, ASA_Botanist_ID_4
- Country validation: Geography_Collector, Geography_Author → HUH_Country_match
- Date validation: Lifespan, HUH_Collections_in → HUH_Date_match
- Team fields: Collector_Team → HUH_Team_match

Inputs:
- Example CSV for Max - Sheet1.csv (new records to validate)
- Master_Collector(newmain).csv (reference database)

Outputs:
- validation_results(Primary).csv (primary collector validation)
- validation_results(Secondary).csv (co-collector validation)
- Modified_Max_Sheet_with_Top_Results.csv (enhanced input sheet with validation results)
- Master names in all outputs include source labels: "(FM)" or "(HUH)"

Output Columns Include Separate FM and HUH Validation Results:
- FM_Country_match, FM_Date_match, FM_Team_match (Field Museum validation)
- HUH_Country_match, HUH_Date_match, HUH_Team_match (Harvard validation)
- score (Combined validation score using Name|ID|Country|Date|Team labels)
- fm_score (Field Museum-specific validation score using applicable field labels)  
- huh_score (Harvard-specific validation score using applicable field labels)

Functions:
1. Name Matching: Handles variants, initials, and name order (Last, First vs First Last)
2. ID Validation: Cross-checks HUH_BotanistID against master IDs
3. Country Checks: 
   - FM: Country matching against FM_Countries field
   - HUH: Country matching against Geography_Collector, Geography_Author fields  
   - Date validation against FM date_range_FM and HUH Lifespan/HUH_Collections_in periods
4. Team Analysis: Verifies co-collector relationships separately for FM and HUH sources

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

def check_collector_team_matches(collector_names, master_team_str, master_fm_team_str):
    """Check if any of the collector team members match the master team columns
    
    Args:
        collector_names: List of collector names to check
        master_team_str: HUH Collector_Team field value  
        master_fm_team_str: FM Collector_Teams field value
    
    Returns:
        Dictionary with separate FM and HUH team match results
    """
    if not collector_names:
        return {"FM_Team_match": "False|No-co-collectors", "HUH_Team_match": "False|No-co-collectors"}
    
    # Extract last names from all collector names
    all_last_names = []
    for name in collector_names:
        all_last_names.extend(extract_last_names(name))
    
    if not all_last_names:
        return {"FM_Team_match": "False|No-valid-names", "HUH_Team_match": "False|No-valid-names"}
    
    results = {"FM_Team_match": "False", "HUH_Team_match": "False"}
    
    # === FIELD MUSEUM (FM) TEAM MATCHING ===
    if pd.notna(master_fm_team_str) and isinstance(master_fm_team_str, str):
        fm_team_lower = remove_accents(master_fm_team_str).lower()
        fm_match_count = 0
        for last_name in all_last_names:
            last_name_lower = last_name.lower()
            # Look for the last name as a whole word in the team string
            if f' {last_name_lower} ' in f' {fm_team_lower} ':
                fm_match_count += 1
        
        if fm_match_count > 0:
            results["FM_Team_match"] = f"True|{fm_match_count}"
    else:
        results["FM_Team_match"] = "False|No-team-data"
    
    # === HARVARD UNIVERSITY HERBARIA (HUH) TEAM MATCHING ===
    if pd.notna(master_team_str) and isinstance(master_team_str, str):
        huh_team_lower = remove_accents(master_team_str).lower()
        huh_match_count = 0
        for last_name in all_last_names:
            last_name_lower = last_name.lower()
            # Look for the last name as a whole word in the team string
            if f' {last_name_lower} ' in f' {huh_team_lower} ':
                huh_match_count += 1
        
        if huh_match_count > 0:
            results["HUH_Team_match"] = f"True|{huh_match_count}"
    else:
        results["HUH_Team_match"] = "False|No-team-data"
    
    return results

def get_country_matches(country, master_row):
    """Check country match against separate FM and HUH columns and return separate match results"""
    if not country:
        return {'FM_Country_match': "False", 'HUH_Country_match': "False"}
    
    country_lower = remove_country_accents(country)
    results = {'FM_Country_match': "False", 'HUH_Country_match': "False"}
    
    # === FIELD MUSEUM (FM) COUNTRY MATCHING ===
    fm_countries = str(master_row.get('FM_Countries', ''))
    if fm_countries and country_lower in remove_country_accents(fm_countries):
        results['FM_Country_match'] = f"True|{country}"
    
    # === HARVARD UNIVERSITY HERBARIA (HUH) COUNTRY MATCHING ===
    huh_sources = []
    huh_columns = ['Geography_Collector', 'Geography_Author']
    for col in huh_columns:
        if col in master_row and pd.notna(master_row[col]):
            huh_country = str(master_row[col])
            if country_lower in remove_country_accents(huh_country):
                huh_sources.append(col.replace('Geography_', ''))
    
    if huh_sources:
        results['HUH_Country_match'] = f"True|{country}"
    
    return results

def get_date_matches(avg_year, master_row):
    """Check date match against separate FM and HUH columns and return separate match results"""
    if not avg_year:
        return {'FM_Date_match': "False", 'HUH_Date_match': "False"}
    
    results = {'FM_Date_match': "False", 'HUH_Date_match': "False"}
    
    # === FIELD MUSEUM (FM) DATE MATCHING ===
    fm_date_range = master_row.get('date_range_FM')
    if fm_date_range and check_date_in_range(avg_year, str(fm_date_range)):
        results['FM_Date_match'] = "True"
    
    # === HARVARD UNIVERSITY HERBARIA (HUH) DATE MATCHING ===
    huh_matches = []
    
    # Check HUH Lifespan
    lifespan = master_row.get('Lifespan')
    if lifespan and check_date_in_range(avg_year, str(lifespan)):
        huh_matches.append("Lifespan")
    
    # Check HUH Collections
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

def _compute_match_score(match: dict) -> tuple[int, list[str], dict]:
    """Compute a weighted score and score labels based on all match facets.
    Returns (score_value, labels, separate_scores). 
    Labels follow existing 'Name|ID|Country|Date|Team' convention.
    separate_scores contains FM and HUH specific scoring details."""
    score = 0
    labels: list[str] = []
    
    # Initialize separate scoring tracking
    fm_score = 0
    huh_score = 0
    fm_labels = []
    huh_labels = []

    # Name
    if str(match.get('name_match', '')).startswith('True'):
        score += 10
        fm_score += 10  # Name match applies to both since we don't separate name sources in scoring
        huh_score += 10
        labels.append('Name')
        fm_labels.append('Name')
        huh_labels.append('Name')

    # ID (strongest signal) - HUH specific
    id_val = str(match.get('id_match', ''))
    if id_val.startswith('True'):
        score += 100
        huh_score += 100  # ID is HUH-specific
        labels.append('ID')
        huh_labels.append('ID')

    # Country - Separate FM and HUH scoring
    fm_country = str(match.get('FM_Country_match', ''))
    huh_country = str(match.get('HUH_Country_match', ''))
    fm_c_true = fm_country.startswith('True')
    huh_c_true = huh_country.startswith('True')
    
    if fm_c_true and huh_c_true:
        score += 25
        fm_score += 25
        huh_score += 25
        if 'Country' not in labels:
            labels.append('Country')
        fm_labels.append('Country')
        huh_labels.append('Country')
    elif fm_c_true:
        score += 15
        fm_score += 20  # Full FM country score when only FM matches
        if 'Country' not in labels:
            labels.append('Country')
        fm_labels.append('Country')
    elif huh_c_true:
        score += 15
        huh_score += 20  # Full HUH country score when only HUH matches
        if 'Country' not in labels:
            labels.append('Country')
        huh_labels.append('Country')

    # Date - Separate FM and HUH scoring
    fm_date = str(match.get('FM_Date_match', ''))
    huh_date = str(match.get('HUH_Date_match', ''))
    fm_d_true = fm_date.startswith('True')
    huh_d_true = huh_date.startswith('True')
    
    if fm_d_true and huh_d_true:
        score += 30
        fm_score += 30
        huh_score += 30
        if 'Date' not in labels:
            labels.append('Date')
        fm_labels.append('Date')
        huh_labels.append('Date')
    elif fm_d_true:
        score += 20
        fm_score += 25  # Full FM date score when only FM matches
        if 'Date' not in labels:
            labels.append('Date')
        fm_labels.append('Date')
    elif huh_d_true:
        score += 15
        huh_score += 20  # Full HUH date score when only HUH matches
        if 'Date' not in labels:
            labels.append('Date')
        huh_labels.append('Date')

    # Team - Separate FM and HUH scoring
    fm_team = str(match.get('FM_Team_match', ''))
    huh_team = str(match.get('HUH_Team_match', ''))
    fm_t_true = fm_team.startswith('True')
    huh_t_true = huh_team.startswith('True')
    
    fm_team_score = 0
    huh_team_score = 0
    
    if fm_t_true:
        try:
            parts = fm_team.split('|')
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            fm_team_score = 10 + 3 * count
        except Exception:
            fm_team_score = 12
        fm_labels.append('Team')
    
    if huh_t_true:
        try:
            parts = huh_team.split('|')
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            huh_team_score = 8 + 2 * count
        except Exception:
            huh_team_score = 10
        huh_labels.append('Team')
    
    # Add team scores
    if fm_t_true or huh_t_true:
        if 'Team' not in labels:
            labels.append('Team')
    
    team_score = max(fm_team_score, huh_team_score)
    if fm_t_true and huh_t_true:
        team_score = fm_team_score + huh_team_score // 2  # Bonus for both sources
    
    score += team_score
    fm_score += fm_team_score
    huh_score += huh_team_score

    # Create separate scores dictionary
    separate_scores = {
        'fm_score': fm_score,
        'huh_score': huh_score,
        'fm_labels': fm_labels,
        'huh_labels': huh_labels
    }

    return score, labels, separate_scores

def get_name_variants_from_master(master_row):
    """Extract all name variants from master row, organized by source"""
    name_variants = []
    
    # === FIELD MUSEUM (FM) NAME FIELDS ===
    fm_name_columns = [
        'Standard_Label_Name',  # FM standard label
    ]
    # Add FM variant names  
    fm_name_columns.extend([f'Variant_name_{i}' for i in range(2, 12)])
    fm_name_columns.append('Variant_name')
    
    # === HARVARD UNIVERSITY HERBARIA (HUH) NAME FIELDS ===
    huh_name_columns = [
        'nam_NamFullName',     # HUH full name
        'nam_NamBriefName',    # HUH brief name  
        'OtherNames'           # HUH other names
    ]
    
    # Collect all name variants
    all_name_columns = fm_name_columns + huh_name_columns
    for col in all_name_columns:
        if col in master_row.index:
            val = master_row.get(col, '')
            if pd.notna(val) and val != '':
                if isinstance(val, str):
                    name_variants.append(val)
    
    return name_variants

def format_name_variants_display(master_row):
    """Format name variants for display according to source (FM vs HUH) and user requirements"""
    def _clean(v):
        return str(v).strip() if pd.notna(v) else ''
    
    # Check if this is a Field Museum entry (has IRN) or HUH entry (no IRN)
    has_irn = pd.notna(master_row.get('Collector_irn', '')) and str(master_row.get('Collector_irn', '')).strip() != ''
    
    display_variants = []
    
    if has_irn:
        # === FIELD MUSEUM (FM) ENTRIES ===
        # Order: nam_NamFullName, OtherNames
        
        # First: nam_NamFullName
        nam_full = _clean(master_row.get('nam_NamFullName'))
        if nam_full:
            display_variants.append(nam_full)
        
        # Second: OtherNames
        other_names = _clean(master_row.get('OtherNames'))
        if other_names:
            display_variants.append(other_names)
            
    else:
        # === HUH ENTRIES (no IRN) ===
        # Order: nam_NamFullName, Standard_Label_Name
        
        # First: nam_NamFullName
        nam_full = _clean(master_row.get('nam_NamFullName'))
        if nam_full:
            display_variants.append(nam_full)
        
        # Second: Standard_Label_Name
        standard_label = _clean(master_row.get('Standard_Label_Name'))
        if standard_label:
            display_variants.append(standard_label)
    
    # Format the result with limited length
    if not display_variants:
        return ""
    
    # Join up to first 3 variants, add "..." if more exist
    result = ", ".join(display_variants[:3])
    if len(display_variants) > 3:
        result += "..."
    
    return result

def get_master_display_name(master_row: pd.Series) -> str:
    """Return the best available display name for a master row using a fallback chain.
    Prioritizes FM fields, then falls back to HUH fields. Includes source labels (FM/HUH)."""
    def _clean(v):
        return str(v).strip() if pd.notna(v) else ''

    # === FIELD MUSEUM (FM) PREFERRED NAMES (PRIORITY 1) ===
    fm_preferred_cols = ['Standard_Label_Name']
    for col in fm_preferred_cols:
        val = _clean(master_row.get(col))
        if val:
            return f"{val} (FM)"

    # === HARVARD UNIVERSITY HERBARIA (HUH) NAMES (PRIORITY 2) ===
    huh_name_cols = ['nam_NamFullName', 'nam_NamBriefName']
    for col in huh_name_cols:
        val = _clean(master_row.get(col))
        if val:
            return f"{val} (HUH)"

    # === CONSTRUCT NAME FROM COMPONENTS (PRIORITY 3) ===
    # Try HUH first/last name components
    first = _clean(master_row.get('nam_NamFirst'))
    last = _clean(master_row.get('nam_NamLast'))
    if first and last:
        return f"{first} {last} (HUH)"

    # === FM AND HUH VARIANT NAMES (PRIORITY 4) ===
    # Check FM variant names first
    fm_variant_cols = ['Variant_name'] + [f'Variant_name_{i}' for i in range(2, 12)]
    for col in fm_variant_cols:
        val = _clean(master_row.get(col))
        if val:
            return f"{val} (FM)"
    
    # Then check HUH other names
    huh_other_cols = ['OtherNames']
    for col in huh_other_cols:
        val = _clean(master_row.get(col))
        if val:
            if col == 'OtherNames':
                for sep in [';', '|', ',']:
                    if sep in val:
                        token = val.split(sep)[0].strip()
                        if token:
                            return f"{token} (HUH)"
            return f"{val} (HUH)"

    # === LAST RESORT: GUID (PRIORITY 5) ===
    guid = _clean(master_row.get('GUID'))
    return f"{guid} (Unknown)" if guid else "Unknown"

def process_secondary_collectors(example_df, master_df):
    """
    Process all secondary collectors (collectorName2+, verbatimCollector2+)
    
    Validates secondary collectors against master database using both FM and HUH fields:
    
    === FIELD MUSEUM (FM) VALIDATION ===
    - Names: Standard_Label_Name, Variant_name fields
    - Geography: FM_Countries
    - Dates: date_range_FM
    - Teams: FM_Collector_Teams
    
    === HARVARD UNIVERSITY HERBARIA (HUH) VALIDATION ===
    - Names: nam_NamFullName, nam_NamBriefName, nam_NamFirst, nam_NamLast, OtherNames
    - IDs: ASA_Botanist_ID, ASA_Botanist_ID_2, ASA_Botanist_ID_3, ASA_Botanist_ID_4
    - Geography: Geography_Collector, Geography_Author
    - Dates: Lifespan, HUH_Collections_in
    - Teams: Collector_Team
    """
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
                    'FM_Team_match': 'False|Brackets',
                    'HUH_Team_match': 'False|Brackets',
                    'score': 'BRACKETS',
                    'fm_score': 'BRACKETS',
                    'huh_score': 'BRACKETS'
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
                # === NAME VARIANT COLLECTION ===
                # Get all name variants from master (both FM and HUH sources)
                name_variants = get_name_variants_from_master(master_row)
                
                # Name and ID matching
                name_to_match = verbatim_name if verbatim_name and not pd.isna(verbatim_name) else collector_name
                name_bool = process_name_match('', name_to_match, name_variants) if name_to_match else False
                
                # === HUH ID MATCHING ===
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
                    
                    # Check against multiple HUH ID columns in master
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

                # === COUNTRY AND DATE VALIDATION ===
                # Country and date matches against both FM and HUH sources
                country_matches = get_country_matches(country, master_row) if country else {'FM_Country_match': "False", 'HUH_Country_match': "False"}
                date_matches = get_date_matches(avg_year, master_row) if avg_year else {'FM_Date_match': "False", 'HUH_Date_match': "False"}
                
                # === TEAM VALIDATION ===
                # Team matching using other co-collectors against both FM and HUH team fields
                team_matches = check_collector_team_matches(
                    other_collectors,
                    master_row.get('Collector_Team'),        # HUH team field
                    master_row.get('FM_Collector_Teams'),    # FM team field
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
                        'FM_Team_match': team_matches['FM_Team_match'],
                        'HUH_Team_match': team_matches['HUH_Team_match'],
                        'name_variants': format_name_variants_display(master_row)
                    }
                    score_value, score_labels, separate_scores = _compute_match_score(m)
                    m['__score_value'] = score_value
                    m['__score_labels'] = score_labels
                    m['__separate_scores'] = separate_scores
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
                    'FM_Team_match': 'False|NoMatch',
                    'HUH_Team_match': 'False|NoMatch',
                    'score': 'NoMatch',
                    'fm_score': 'NoMatch',
                    'huh_score': 'NoMatch'
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
                        'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
                        'master_name': match['master_name'],
                        'master_irn': int(match['master_irn']) if pd.notna(match['master_irn']) and match['master_irn'] != '' else '',
                        'master_name_variants': match['name_variants'],
                        'id_match': match['id_match'],
                        'name_match': match['name_match'],
                        'FM_Country_match': match['FM_Country_match'],
                        'HUH_Country_match': match['HUH_Country_match'],
                        'FM_Date_match': match['FM_Date_match'],
                        'HUH_Date_match': match['HUH_Date_match'],
                        'FM_Team_match': match['FM_Team_match'],
                        'HUH_Team_match': match['HUH_Team_match'],
                        'score': '|'.join(match.get('__score_labels', [])) or 'Name',
                        'fm_score': '|'.join(match.get('__separate_scores', {}).get('fm_labels', [])) or 'None',
                        'huh_score': '|'.join(match.get('__separate_scores', {}).get('huh_labels', [])) or 'None'
                    })

    # Create results dataframe
    results_df = pd.DataFrame(secondary_results)
    
    #Reorder columns - Group FM and HUH fields separately for clarity
    cols = ['Image_URL', 'barcode', 'collector_number', 'tested_name', 'master_name', 'master_irn', 'master_name_variants',
            'id_match', 'name_match', 
            # === FIELD MUSEUM (FM) VALIDATION FIELDS ===
            'FM_Country_match', 'FM_Date_match', 'FM_Team_match',
            # === HARVARD UNIVERSITY HERBARIA (HUH) VALIDATION FIELDS ===
            'HUH_Country_match', 'HUH_Date_match', 'HUH_Team_match',
            # === OVERALL SCORE ===
            'score', 'fm_score', 'huh_score']

    return results_df[cols]

def process_data(example_file, master_file, output_dir):
    """
    Main processing function that validates collectors against master database.
    
    Processes both primary and secondary collectors using organized FM and HUH field validation:
    
    === FIELD MUSEUM (FM) VALIDATION ===
    - Names: Standard_Label_Name, Variant_name fields
    - Geography: FM_Countries  
    - Dates: date_range_FM
    - Teams: FM_Collector_Teams
    
    === HARVARD UNIVERSITY HERBARIA (HUH) VALIDATION ===
    - Names: nam_NamFullName, nam_NamBriefName, nam_NamFirst, nam_NamLast, OtherNames
    - IDs: ASA_Botanist_ID, ASA_Botanist_ID_2, ASA_Botanist_ID_3, ASA_Botanist_ID_4
    - Geography: Geography_Collector, Geography_Author
    - Dates: Lifespan, HUH_Collections_in  
    - Teams: Collector_Team
    """
    #Load the data
    example_df = pd.read_csv(example_file) if example_file.endswith('.csv') else pd.read_excel(example_file)
    master_df = pd.read_csv(master_file) if master_file.endswith('.csv') else pd.read_excel(master_file)
    
    #Prepare dataframe for primary collectors
    primary_results = []
    
    # === PRIMARY COLLECTOR VALIDATION LOOP ===
    # Process each row and validate primary collector against master database
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
                'FM_Team_match': 'False|NoName',
                'HUH_Team_match': 'False|NoName',
                'score': 'NONAME',
                'fm_score': 'NONAME',
                'huh_score': 'NONAME'
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
                'FM_Team_match': 'False|Brackets',
                'HUH_Team_match': 'False|Brackets',
                'score': 'BRACKETS',
                'fm_score': 'BRACKETS',
                'huh_score': 'BRACKETS'
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
            # === NAME VARIANT COLLECTION ===
            # Get all name variants from master (both FM and HUH sources)
            name_variants = get_name_variants_from_master(master_row)
            
            # Name check
            name_bool = process_name_match(collector_name, verbatim_name, name_variants)

            # === HUH ID MATCHING ===
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
                
                # Check against multiple HUH ID columns in master
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

            # === COUNTRY AND DATE VALIDATION ===
            # Country and date validation against both FM and HUH sources
            country_matches = get_country_matches(country, master_row) if country else {'FM_Country_match': "False", 'HUH_Country_match': "False"}
            date_matches = get_date_matches(avg_year, master_row) if avg_year else {'FM_Date_match': "False", 'HUH_Date_match': "False"}
            
            # === TEAM VALIDATION ===
            # Team matching against both FM and HUH team fields
            team_matches = check_collector_team_matches(
                other_collectors,
                master_row.get('Collector_Team'),        # HUH team field
                master_row.get('FM_Collector_Teams'),    # FM team field
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
                    'FM_Team_match': team_matches['FM_Team_match'],
                    'HUH_Team_match': team_matches['HUH_Team_match'],
                    'name_variants': format_name_variants_display(master_row)
                }
                score_value, score_labels, separate_scores = _compute_match_score(m)
                m['__score_value'] = score_value
                m['__score_labels'] = score_labels
                m['__separate_scores'] = separate_scores
                matches.append(m)
        
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
                'FM_Team_match': 'False|NoMatch',
                'HUH_Team_match': 'False|NoMatch',
                'score': 'NoMatch',
                'fm_score': 'NoMatch',
                'huh_score': 'NoMatch'
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
                        'tested_name': f"{verbatim_name} ({collector_name})" if verbatim_name and collector_name else verbatim_name or collector_name,
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
                        'FM_Team_match': match['FM_Team_match'],
                        'HUH_Team_match': match['HUH_Team_match'],
                        'score': '|'.join(match.get('__score_labels', [])) or 'Name',
                        'fm_score': '|'.join(match.get('__separate_scores', {}).get('fm_labels', [])) or 'None',
                        'huh_score': '|'.join(match.get('__separate_scores', {}).get('huh_labels', [])) or 'None'
                    })    # Create primary results dataframe
    primary_results_df = pd.DataFrame(primary_results)
    
    # Reorder columns - Group FM and HUH fields separately for clarity
    cols = ['Image_URL', 'barcode', 'collector_number', 'tested_name', 'match_rank', 'master_name', 'master_irn', 'master_name_variants',
            'id_match', 'name_match',
            # === FIELD MUSEUM (FM) VALIDATION FIELDS ===
            'FM_Country_match', 'FM_Date_match', 'FM_Team_match',
            # === HARVARD UNIVERSITY HERBARIA (HUH) VALIDATION FIELDS ===  
            'HUH_Country_match', 'HUH_Date_match', 'HUH_Team_match',
            # === OVERALL SCORE ===
            'score', 'fm_score', 'huh_score']

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
                 'FM_Country_match','HUH_Country_match','FM_Date_match','HUH_Date_match',
                 'FM_Team_match','HUH_Team_match','score','fm_score','huh_score']
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
            'FM_Team_match':'Top_Primary_FM_Team_match',
            'HUH_Team_match':'Top_Primary_HUH_Team_match',
            'score':'Top_Primary_score',
            'fm_score':'Top_Primary_FM_score',
            'huh_score':'Top_Primary_HUH_score'
        }, inplace=True)
        modified_df = modified_df.merge(top_primary, on='Barcode', how='left')

    # Top secondary per barcode and collector_number, pivot to wide
    if not secondary_results_df.empty:
        top_sec = secondary_results_df.groupby(['barcode','collector_number'], as_index=False).first()
        for cn in sorted(top_sec['collector_number'].unique()):
            sec_n = top_sec[top_sec['collector_number']==cn].copy()
            scols = ['barcode','tested_name','master_name','master_irn','id_match','name_match',
                     'FM_Country_match','HUH_Country_match','FM_Date_match','HUH_Date_match',
                     'FM_Team_match','HUH_Team_match','score','fm_score','huh_score']
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
                'FM_Team_match':f'Top_Sec{cn}_FM_Team_match',
                'HUH_Team_match':f'Top_Sec{cn}_HUH_Team_match',
                'score':f'Top_Sec{cn}_score',
                'fm_score':f'Top_Sec{cn}_FM_score',
                'huh_score':f'Top_Sec{cn}_HUH_score',
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
        # === FIELD MUSEUM (FM) PRIMARY VALIDATION FIELDS ===
        'Top_Primary_FM_Country_match', 'Top_Primary_FM_Date_match', 'Top_Primary_FM_Team_match',
        # === HARVARD UNIVERSITY HERBARIA (HUH) PRIMARY VALIDATION FIELDS ===
        'Top_Primary_HUH_Country_match', 'Top_Primary_HUH_Date_match', 'Top_Primary_HUH_Team_match',
        # === PRIMARY SCORES ===
        'Top_Primary_score', 'Top_Primary_FM_score', 'Top_Primary_HUH_score'
    ])

    secondary_cols = []
    for cn in range(2, 7):
        secondary_cols.extend(_present([
            f'collectorName{cn}', f'verbatimCollector{cn}', f'HUH_BotanistID_{cn}',
            f'Top_Sec{cn}_tested_name', f'Top_Sec{cn}_master_name', f'Top_Sec{cn}_master_irn',
            f'Top_Sec{cn}_id_match', f'Top_Sec{cn}_name_match',
            # === FIELD MUSEUM (FM) SECONDARY VALIDATION FIELDS ===
            f'Top_Sec{cn}_FM_Country_match', f'Top_Sec{cn}_FM_Date_match', f'Top_Sec{cn}_FM_Team_match',
            # === HARVARD UNIVERSITY HERBARIA (HUH) SECONDARY VALIDATION FIELDS ===
            f'Top_Sec{cn}_HUH_Country_match', f'Top_Sec{cn}_HUH_Date_match', f'Top_Sec{cn}_HUH_Team_match',
            # === SECONDARY SCORES ===
            f'Top_Sec{cn}_score', f'Top_Sec{cn}_FM_score', f'Top_Sec{cn}_HUH_score'
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