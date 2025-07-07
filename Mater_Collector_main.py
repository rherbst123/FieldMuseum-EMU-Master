import pandas as pd
import re
import os
from collections import defaultdict

#Initialize master dictionary
master_collectors = defaultdict(dict)

def clean_other_names(other_names):
    """Clean and deduplicate the OtherNames field"""
    if pd.isna(other_names) or not other_names:
        return ''
    
    #Split by pipe and clean each name
    names = [name.strip() for name in str(other_names).split('|') if name.strip()]
    
    #Remove duplicates
    seen = set()
    unique_names = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)
    
    return '|'.join(unique_names)

def extract_asa_ids(external_refs):
    """Extract ASA Botanist IDs from external references field"""
    if pd.isna(external_refs):
        return []
    
    external_refs = str(external_refs)
    
    #Handle the pipe-separated format "ASA Botanist ID 999999 | 111111"
    if '|' in external_refs:
        parts = [part.strip() for part in external_refs.split('|')]
        ids = []
        for part in parts:
            if 'ASA Botanist ID' in part:
                id_part = part.split('ASA Botanist ID')[-1].strip()
                if id_part.isdigit():
                    ids.append(id_part)
            elif part.isdigit():
                ids.append(part)
        return ids
    
    return re.findall(r'ASA Botanist ID (\d+)', external_refs)

def name_matches(master_entry, huh_name):
    """Check if HUH name matches any name in master entry"""
    if pd.isna(huh_name) or not str(huh_name).strip():
        return False
        
    huh_name = str(huh_name).strip().lower()
    
    # Check against all name fields
    name_fields = [
        'nam_NamFullName',
        'nam_NamFirst',
        'nam_NamLast',
        'nam_NamBriefName',
        'OtherNames'
    ]
    
    for field in name_fields:
        if field in master_entry:
            field_value = master_entry[field]
            if pd.isna(field_value):
                continue
            if field == 'OtherNames':
                names = str(field_value).split('|')
            else:
                names = [str(field_value)]
            
            for name in names:
                name = name.strip().lower()
                if name and name == huh_name:
                    return True
    return False

def extract_year_from_date_string(date_str):
    """Extract 4-digit year from various date formats"""
    if pd.isna(date_str) or not date_str:
        return None
    
    date_str = str(date_str).strip()

    # Try to find a 4-digit year
    year_match = re.search(r'\b(\d{4})\b', date_str)
    if year_match:
        try:
            return int(year_match.group(1))
        except (ValueError, TypeError):
            return None
    return None

def update_fm_date_ranges(filepath):
    """Update date ranges from countries_combined.csv"""
    df = pd.read_csv(filepath)
    
    # Dictionary to store min/max years per collector
    collector_years = defaultdict(lambda: {'min': None, 'max': None})
    
    #Run through each collector column (col_1 to col_11)
    for n in range(1, 12):
        col_prefix = f'col_{n}_'
        irn_col = f'{col_prefix}Collector_irn'
        
        if irn_col not in df.columns:
            continue
            
        for idx, row in df.iterrows():
            irn = row[irn_col]
            
            if pd.isna(irn):
                continue
                
            irn = str(int(irn)) if isinstance(irn, float) else str(irn)
            
            # Extract years from date columns
            earliest_year = extract_year_from_date_string(row.get('ColEarliestDateCollected'))
            latest_year = extract_year_from_date_string(row.get('ColLatestDateCollected'))
            
            # Update min/max years for this collector
            if earliest_year:
                if collector_years[irn]['min'] is None or earliest_year < collector_years[irn]['min']:
                    collector_years[irn]['min'] = earliest_year
            if latest_year:
                if collector_years[irn]['max'] is None or latest_year > collector_years[irn]['max']:
                    collector_years[irn]['max'] = latest_year
    
    # Update master collectors with date ranges
    for irn, years in collector_years.items():
        if irn in master_collectors:
            if years['min'] is not None and years['max'] is not None:
                date_range = f"{years['min']}-{years['max']}"
                master_collectors[irn]['date_range_FM'] = date_range
            elif years['min'] is not None:
                master_collectors[irn]['date_range_FM'] = str(years['min'])
            elif years['max'] is not None:
                master_collectors[irn]['date_range_FM'] = str(years['max'])


# Function to process countries_combined.csv
def process_countries_combined(filepath):
    df = pd.read_csv(filepath)
    
    #Process each collector
    for n in range(1, 12):
        col_prefix = f'col_{n}_'
        irn_col = f'{col_prefix}Collector_irn'
        
        if irn_col not in df.columns:
            continue
            
        for idx, row in df.iterrows():
            irn = row[irn_col]
            
            # Skip if no IRN
            if pd.isna(irn):
                continue
                
            irn = str(int(irn)) if isinstance(irn, float) else str(irn)
            
            # Get ASA IDs from external references
            external_refs = row.get(f'{col_prefix}NamExternalReferences_tab', '')
            asa_ids = extract_asa_ids(external_refs)
            
            # If collector not in master, add them
            if irn not in master_collectors:
                master_collectors[irn]['Collector_irn'] = irn
                master_collectors[irn]['Source_of_Information'] = 'countries_combined.csv'
                
                # Add name information
                for field in ['NamFullName', 'NamBriefName', 'NamFirst', 'NamMiddle', 'NamLast', 'NamOtherNames_tab']:
                    master_field = f'nam_{field}' if field.startswith('Nam') else field
                    value = row.get(f'{col_prefix}{field}', '')
                    if not pd.isna(value):
                        master_collectors[irn][master_field] = str(value)
                
                #Handle OtherNames
                other_names = []
                for other_field in ['NamOtherNames_tab', 'NamOrganisationOtherNames_tab']:
                    value = row.get(f'{col_prefix}{other_field}', '')
                    if not pd.isna(value):
                        other_names.append(str(value))
                if other_names:
                    master_collectors[irn]['OtherNames'] = '|'.join(other_names)
                
                # Handle ASA IDs
                if asa_ids:
                    for i, asa_id in enumerate(asa_ids, start=1):
                        if i == 1:
                            master_collectors[irn]['ASA_Botanist_ID'] = asa_id
                        else:
                            master_collectors[irn][f'ASA_Botanist_ID_{i}'] = asa_id
            else:
                current_names = set(master_collectors[irn].get('OtherNames', '').split('|'))
                new_names = set()
                
                for field in ['NamFullName', 'NamBriefName', 'NamFirst', 'NamMiddle', 'NamLast', 'NamOtherNames_tab', 'NamOrganisationOtherNames_tab']:
                    value = row.get(f'{col_prefix}{field}', '')
                    if not pd.isna(value):
                        value = str(value)
                        if value not in current_names and value != master_collectors[irn].get(f'nam_{field}', ''):
                            new_names.add(value)
                
                if new_names:
                    existing_other = master_collectors[irn].get('OtherNames', '')
                    if existing_other:
                        master_collectors[irn]['OtherNames'] = existing_other + '|'.join(new_names)
                    else:
                        master_collectors[irn]['OtherNames'] = '|'.join(new_names)

                
                # Handle ASA IDs - add any new ones
                if asa_ids:
                    existing_asa_ids = []
                    # Get all existing ASA ID fields
                    for key in master_collectors[irn]:
                        if key == 'ASA_Botanist_ID':
                            existing_asa_ids.append(master_collectors[irn][key])
                        elif key.startswith('ASA_Botanist_ID_'):
                            existing_asa_ids.append(master_collectors[irn][key])
                    
                    for asa_id in asa_ids:
                        if asa_id not in existing_asa_ids:
                            if 'ASA_Botanist_ID' not in master_collectors[irn] or not master_collectors[irn]['ASA_Botanist_ID']:
                                master_collectors[irn]['ASA_Botanist_ID'] = asa_id
                            else:
                                n = 2
                                while f'ASA_Botanist_ID_{n}' in master_collectors[irn]:
                                    n += 1
                                master_collectors[irn][f'ASA_Botanist_ID_{n}'] = asa_id


def huh_extract_asa_id(asa_field):
    """Extract ASA ID from the ASA_Botanist_ID field in HUH data"""
    if pd.isna(asa_field):
        return None
    asa_str = str(asa_field)
    numbers = re.findall(r'\d+', asa_str)
    return numbers[0] if numbers else None

def find_matching_collector(huh_row, master_collectors):
    """Find matching collector in master list based on ASA ID or name variations"""
    # First try to match by ASA ID
    asa_id = huh_extract_asa_id(huh_row.get('ASA_Botanist_ID'))
    if asa_id:
        # Check if this ASA ID exists in master
        for irn, collector in master_collectors.items():
            # Check main ASA ID field
            if collector.get('ASA_Botanist_ID') == asa_id:
                return irn
            # Check all ASA ID_n fields
            for key in collector:
                if key.startswith('ASA_Botanist_ID_') and collector[key] == asa_id:
                    return irn
    
    # If no ASA ID match, try to match by name
    huh_name_fields = [
        'Name', 'Standard_Label_Name', 'Full_Name', 
        'Variant_name', 'Variant_name_1', 'Variant_name_2',
        'Variant_name_3', 'Variant_name_4', 'Variant_name_5',
        'Variant_name_6', 'Variant_name_7', 'Variant_name_8',
        'Variant_name_9', 'Variant_name_10', 'Variant_name_11'
    ]
    
    # Collect all name variations from HUH row
    huh_names = set()
    for field in huh_name_fields:
        if field in huh_row and not pd.isna(huh_row[field]):
            name = str(huh_row[field]).strip()
            if name:
                huh_names.add(name.lower())
    
    #check against all collectors in master sheet
    for irn, collector in master_collectors.items():

        master_name_fields = [
            'nam_NamFullName', 'nam_NamFirst', 'nam_NamLast',
            'nam_NamBriefName', 'OtherNames'
        ]
        
        for field in master_name_fields:
            if field in collector and not pd.isna(collector[field]):
                if field == 'OtherNames':
                    names = str(collector[field]).split('|')
                else:
                    names = [str(collector[field])]
                
                for name in names:
                    name = name.strip().lower()
                    if name and name in huh_names:
                        return irn
    return None

def extract_years_from_collections(collections_str):
    """Extract years from the Collections_in string"""
    if pd.isna(collections_str) or not collections_str:
        return []
    
    # Example format: "1888 (2), 1889 (3), 1905 (44)"
    year_pattern = re.compile(r'(\d{4})')
    years = year_pattern.findall(str(collections_str))
    return [int(year) for year in years] if years else []

def clean_year(year_val):
    """Clean year value handling both strings and floats, with special cases"""
    if pd.isna(year_val):
        return None
    
    year_str = str(year_val).strip()

    cleaned = re.sub(r'[^\d-]', '', year_str)
    
    try:
        year = int(float(cleaned)) 
    except (ValueError, TypeError):
        return None
    
    # Handle 5-digit years (from float conversion)
    if year > 9999:
        year = year // 10
        
    return year if 1000 <= year <= 9999 else None  # Basic year validation

def calculate_lifespan_start(death_year):
    """Calculate approximate lifespan start (death year - 80 years)"""
    if death_year is None:
        return None
    return death_year - 80

def calculate_lifespan_end(birth_year):
    """Calculate approximate lifespan end (birth year + 100 years)"""
    if birth_year is None:
        return None
    return birth_year + 100

def format_collections_range(collections_str, birth_date=None, death_date=None):
    """Format the collections range with improved year handling"""
    years = extract_years_from_collections(collections_str)
    
    # Clean and validate years
    clean_birth = clean_year(birth_date)
    clean_death = clean_year(death_date)
    
    # Case 1: We have collection years
    if years:
        earliest = min(years)
        latest = max(years)
        return f"{earliest} - {latest}"
    
    #Case2: Both birth and death dates available
    elif clean_birth is not None and clean_death is not None:
        return f"{clean_birth} - {clean_death}"
    
    #case 3: Only death date available
    elif clean_death is not None:
        start_year = calculate_lifespan_start(clean_death)
        return f"{start_year} - {clean_death}"
    
    #Case 4: Only birth date available 
    elif clean_birth is not None:
        end_year = calculate_lifespan_end(clean_birth)
        return f"{clean_birth} - {end_year}"
    
    return None


def add_huh_data_to_collector(irn, huh_row, master_collectors):
    """Add HUH data to an existing collector in master_collectors"""
    collector = master_collectors[irn]
    
    #Add GUID
    if 'GUID' in huh_row and not pd.isna(huh_row['GUID']) and 'GUID' not in collector:
        collector['GUID'] = huh_row['GUID']
    
    #Add geography info
    for field in ['Geography_Collector', 'Geography_Author']:
        if field in huh_row and not pd.isna(huh_row[field]):
            if field not in collector or not collector[field]:
                collector[field] = huh_row[field]

    # HUH_Collections_in column
    if 'Collections_in' in huh_row and not pd.isna(huh_row['Collections_in']):
        collections_years = extract_years_from_collections(huh_row['Collections_in'])
        if collections_years:
            earliest = min(collections_years)
            latest = max(collections_years)
            range_str = f"{earliest} - {latest}"
            if 'HUH_Collections_in' not in collector or not collector['HUH_Collections_in']:
                collector['HUH_Collections_in'] = range_str

    #lifespan column based on birth/death dates
    birth_date = huh_row.get('Date_of_birth')
    death_date = huh_row.get('Date_of_death')
    lifespan_range = format_collections_range(None, birth_date, death_date)

    if lifespan_range and ('Lifespan' not in collector or not collector['Lifespan']):
        collector['Lifespan'] = lifespan_range    
    
    #standard label name
    if 'Standard_Label_Name' in huh_row and not pd.isna(huh_row['Standard_Label_Name']):
        if 'Standard_Label_Name' not in collector or not collector['Standard_Label_Name']:
            collector['Standard_Label_Name'] = huh_row['Standard_Label_Name']
    
    #ollector teams
    if 'Collector_Teams' in huh_row and not pd.isna(huh_row['Collector_Teams']):
        if 'Collector_Team' not in collector or not collector['Collector_Team']:
            collector['Collector_Team'] = huh_row['Collector_Teams']
    
    # Handle variant names
    max_variants = 0
    variant_names = []
    
    for i in range(1, 12):
        variant_field = f'Variant_name_{i}' if i > 1 else 'Variant_name'
        if variant_field in huh_row and not pd.isna(huh_row[variant_field]):
            variant_name = str(huh_row[variant_field]).strip()
            if variant_name:
                variant_names.append((i, variant_name))
                if i > max_variants:
                    max_variants = i
    # Second pass to populate variant_name_n fields
    for i, variant_name in variant_names:
        field_name = f'Variant_name_{i}' if i > 1 else 'Variant_name'
        
        # Only add if the field is empty in the master
        if field_name not in collector or not collector[field_name]:
            collector[field_name] = variant_name


def process_huh_combined(filepath):
    """Process HUH_Combined.csv and merge data with master collectors"""
    df = pd.read_csv(filepath)
    non_matches = 0
    new_entries = 0
    
    for _, row in df.iterrows():
        irn = find_matching_collector(row, master_collectors)
        
        if irn:
            add_huh_data_to_collector(irn, row, master_collectors)
            
            # Update source of information
            if 'Source_of_Information' in master_collectors[irn]:
                sources = master_collectors[irn]['Source_of_Information']
                if 'HUH_Combined.csv' not in sources:
                    master_collectors[irn]['Source_of_Information'] = f"{sources}, HUH_Combined.csv"
            else:
                master_collectors[irn]['Source_of_Information'] = 'HUH_Combined.csv'
        else:
            non_matches += 1
            # Create new entry for non-matching record
            new_irn = f"HUH_{row.name if 'name' in row else len(master_collectors) + 1}"
            
            #reate new collector entry
            master_collectors[new_irn] = {
                'Collector_irn': new_irn,
                'Source_of_Information': 'HUH_Combined.csv',
            }
            
            #Add available information from HUH row
            if 'GUID' in row and not pd.isna(row['GUID']):
                master_collectors[new_irn]['GUID'] = row['GUID']
            
            asa_id = huh_extract_asa_id(row.get('ASA_Botanist_ID'))
            if asa_id:
                master_collectors[new_irn]['ASA_Botanist_ID'] = asa_id
            
            name_fields = {
                'Name': 'nam_NamFullName',
                'Standard_Label_Name': 'Standard_Label_Name',
                'Full_Name': 'nam_NamFullName',
            }
            
            for huh_field, master_field in name_fields.items():
                if huh_field in row and not pd.isna(row[huh_field]):
                    master_collectors[new_irn][master_field] = row[huh_field]
            
            for field in ['Geography_Collector', 'Geography_Author']:
                if field in row and not pd.isna(row[field]):
                    master_collectors[new_irn][field] = row[field]

            if 'Collections_in' in row and not pd.isna(row['Collections_in']):
                collections_years = extract_years_from_collections(row['Collections_in'])
                if collections_years:
                    earliest = min(collections_years)
                    latest = max(collections_years)
                    master_collectors[new_irn]['HUH_Collections_in'] = f"{earliest} - {latest}"
            
            birth_date = row.get('Date_of_birth')
            death_date = row.get('Date_of_death')
            lifespan_range = format_collections_range(None, birth_date, death_date)
            if lifespan_range:
                master_collectors[new_irn]['Lifespan'] = lifespan_range
            
            if 'Collector_Teams' in row and not pd.isna(row['Collector_Teams']):
                master_collectors[new_irn]['Collector_Team'] = row['Collector_Teams']
            
            variant_names = []
            for i in range(1, 12):
                variant_field = f'Variant_name_{i}' if i > 1 else 'Variant_name'
                if variant_field in row and not pd.isna(row[variant_field]):
                    variant_name = str(row[variant_field]).strip()
                    if variant_name:
                        variant_names.append((i, variant_name))

            for i, variant_name in variant_names:
                field_name = f'Variant_name_{i}' if i > 1 else 'Variant_name'
                master_collectors[new_irn][field_name] = variant_name
                if i > 1:
                    master_collectors[new_irn]['Variant_name_n'] = str(i)
            
            new_entries += 1
    
    print(f"Total non-matching records in HUH data: {non_matches}")
    print(f"New entries created from non-matches: {new_entries}")

def process_botany_parties_author_names(filepath):
    """Process Botany_Parties_Author_Names.xlsx to update taxonomic names and variant names"""
    try:
        df = pd.read_excel(filepath)
        source_name = os.path.basename(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return
    
    for _, row in df.iterrows():
        # First try to match by ASA ID if available
        asa_id = None
        if not pd.isna(row['External_refs']):
            asa_ids = extract_asa_ids(row['External_refs'])
            if asa_ids:
                asa_id = asa_ids[0]
        
        # Try to find matching collector
        matching_irn = None
        if asa_id:
            for irn, collector in master_collectors.items():
                if collector.get('ASA_Botanist_ID') == asa_id:
                    matching_irn = irn
                    break
                for key in collector:
                    if key.startswith('ASA_Botanist_ID_') and collector[key] == asa_id:
                        matching_irn = irn
                        break
                if matching_irn:
                    break
        
        # If no match by ASA ID, try to match by name
        if not matching_irn:
            name_variants = set()
            for field in ['Brief', 'Full', 'OtherNam']:
                if not pd.isna(row[field]):
                    name = str(row[field]).strip()
                    if name:
                        name_variants.add(name.lower())
            
            for irn, collector in master_collectors.items():
                for name_field in ['nam_NamFullName', 'nam_NamBriefName', 'OtherNames']:
                    if name_field in collector and not pd.isna(collector[name_field]):
                        if name_field == 'OtherNames':
                            names = str(collector[name_field]).split('|')
                        else:
                            names = [str(collector[name_field])]
                        
                        for name in names:
                            if name.strip().lower() in name_variants:
                                matching_irn = irn
                                break
                    if matching_irn:
                        break
                if matching_irn:
                    break
        
        if matching_irn:
            collector = master_collectors[matching_irn]
            
            if 'Source_of_Information' in collector:
                sources = collector['Source_of_Information']
                if source_name not in sources:
                    collector['Source_of_Information'] = f"{sources}, {source_name}"
            else:
                collector['Source_of_Information'] = source_name
            
            #Update taxonomic names if exists
            if not pd.isna(row['Taxonomic']) and ('Taxanomic_names' not in collector or not collector['Taxanomic_names']):
                collector['Taxanomic_names'] = str(row['Taxonomic'])
            
            # Add new variant names
            new_variants = []
            for field in ['Brief', 'Full', 'OtherNam']:
                if not pd.isna(row[field]):
                    variant = str(row[field]).strip()
                    if variant:
                        new_variants.append(variant)
            
            if new_variants:
                #check if these variants already exist in any name field
                existing_names = set()
                for name_field in ['nam_NamFullName', 'nam_NamBriefName', 'OtherNames'] + \
                                 [f'Variant_name_{i}' for i in range(1, 12)]:
                    if name_field in collector and not pd.isna(collector[name_field]):
                        if name_field == 'OtherNames':
                            existing_names.update(str(collector[name_field]).split('|'))
                        else:
                            existing_names.add(str(collector[name_field]))
                
                # Add new variants that aren't already present
                for variant in new_variants:
                    if variant not in existing_names:
                        added = False
                        for i in range(1, 12):
                            field_name = f'Variant_name_{i}' if i > 1 else 'Variant_name'
                            if field_name not in collector or not collector[field_name]:
                                collector[field_name] = variant
                                added = True
                                if i > int(collector.get('Variant_name_n', 0)):
                                    collector['Variant_name_n'] = str(i)
                                break
                        
                        # If all variant slots are full, add to OtherNames
                        if not added:
                            existing_other = collector.get('OtherNames', '')
                            if existing_other:
                                collector['OtherNames'] = f"{existing_other}|{variant}"
                            else:
                                collector['OtherNames'] = variant

# Main processing function
def create_master_collector():
    # Process each file
    process_countries_combined('EMU_Combined_Sheets/countries_combined.csv')
    process_huh_combined('HUH/HUH_Combined.csv')    
    process_botany_parties_author_names('BotanyParties/Botany_Parties_Author_names.xlsx')
    
    # Add FM date ranges from countries_combined.csv
    update_fm_date_ranges('EMU_Combined_Sheets/countries_combined.csv')
    
    # Convert to DataFrame
    master_df = pd.DataFrame.from_dict(master_collectors, orient='index')
    
    #clean OtherNames column
    master_df['OtherNames'] = master_df['OtherNames'].apply(clean_other_names)
    
    base_columns = [
        'Collector_irn', 'GUID', 'ASA_Botanist_ID', 
        'Source_of_Information', 'Geography_Collector', 'Geography_Author', 
        'Lifespan', 'HUH_Collections_in', 'date_range_FM', 'Standard_Label_Name', 
        'nam_NamFullName', 'nam_NamFirst', 'nam_NamMiddle', 'nam_NamLast', 
        'nam_NamBriefName', 'OtherNames', 'Variant_name', 'Taxanomic_names', 
        'Collector_Team'
    ]
    
    # Get all ASA_Botanist_ID_n columns and sort them numerically
    asa_id_cols = [col for col in master_df.columns if col.startswith('ASA_Botanist_ID_')]
    asa_id_cols.sort(key=lambda x: int(x.split('_')[-1]))
    
    # Get all Variant_name_n columns
    variant_cols = []
    for i in range(2, 12):
        col_name = f'Variant_name_{i}'
        variant_cols.append(col_name)
    
    # Combine all columns
    output_columns = (
        base_columns[:3] + 
        asa_id_cols + 
        base_columns[3:15] + 
        variant_cols + 
        base_columns[16:]
    )
    
    # Add any missing columns
    for col in output_columns:
        if col not in master_df.columns:
            master_df[col] = ''
    
    master_df = master_df[output_columns]
    
    #Save to CSV
    master_df.to_csv('Master_Collector(main).csv', index=False)
    print("Master collector file created: Master_Collector(main).csv")

if __name__ == '__main__':
    create_master_collector()