'''
Field Museum Master Collector Sheet

Purpose:
Creates a master collector data sheet by combining data from multiple sources:
- countries_combined.csv (EMU data)
    -This file is not found in the repository since it is too large but it can be found in 
     google drive > 2025 folder > testing > Round2
- HUH_Combined.csv (Harvard Herbaria data)
- Botany_Parties_Author_names.xlsx (botany parties data)

Key Features:
- Standardizes collector names and IDs
- Merges duplicate records
- Creates comprehensive date ranges
- Builds collector team associations
'''

import pandas as pd
import re
import os
from collections import defaultdict

#Initialize master dict.
master_collectors = defaultdict(dict)

#Helper Functions
def clean_name(name):
    """Clean name by removing et al. and extra spaces"""
    if pd.isna(name) or not name:
        return name
    name = str(name).strip()
    return re.sub(r'\s+et\s+al\.?', '', name, flags=re.IGNORECASE).strip()

def clean_other_names(other_names):
    """Clean and deduplicate the OtherNames field"""
    if pd.isna(other_names) or not other_names:
        return ''
    names = [name.strip() for name in str(other_names).split('|') if name.strip()]
    seen = set()
    return '|'.join([name for name in names if not (name in seen or seen.add(name))])

def extract_asa_ids(external_refs):
    """Extract ASA Botanist IDs from external references field"""
    if pd.isna(external_refs):
        return []
    external_refs = str(external_refs)
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

def extract_year_from_date_string(date_str):
    """Extract 4-digit year from various date formats"""
    if pd.isna(date_str) or not date_str:
        return None
    year_match = re.search(r'\b(\d{4})\b', str(date_str).strip())
    return int(year_match.group(1)) if year_match else None

def clean_year(year_val):
    """Clean year value handling both strings and floats"""
    if pd.isna(year_val):
        return None
    try:
        year = int(float(re.sub(r'[^\d-]', '', str(year_val).strip())))
        return year if 1000 <= year <= 9999 else None
    except (ValueError, TypeError):
        return None

def format_date_range(years):
    """Format a list of years into a date range string"""
    if not years:
        return None
    min_year, max_year = min(years), max(years)
    return f"{min_year}-{max_year}" if min_year != max_year else f"{min_year}-{min_year}"

def update_collector_dates(irn, years, current_year):
    """Update date ranges for a collector"""
    if irn in master_collectors and years:
        valid_years = [y for y in years if 1500 <= y <= current_year]
        if valid_years:
            master_collectors[irn]['date_range_FM'] = format_date_range(valid_years)

def process_collector_row(row, col_prefix, irn):
    """Process a single collector row from countries_combined.csv"""
    collector_data = {
        'Collector_irn': irn,
        'Source_of_Information': 'countries_combined.csv'
    }
    
    #Handle names
    name_fields = ['NamFullName', 'NamBriefName', 'NamFirst', 'NamMiddle', 'NamLast']
    for field in name_fields:
        value = row.get(f'{col_prefix}{field}', '')
        if not pd.isna(value):
            collector_data[f'nam_{field}'] = str(value)
    
    # Handle OtherNames
    other_names = []
    for other_field in ['NamOtherNames_tab']:
        value = row.get(f'{col_prefix}{other_field}', '')
        if not pd.isna(value):
            other_names.append(str(value))
    if other_names:
        collector_data['OtherNames'] = '|'.join(other_names)
    
    # Handle ASA IDs
    external_refs = row.get(f'{col_prefix}NamExternalReferences_tab', '')
    asa_ids = extract_asa_ids(external_refs)
    for i, asa_id in enumerate(asa_ids, 1):
        field = 'ASA_Botanist_ID' if i == 1 else f'ASA_Botanist_ID_{i}'
        collector_data[field] = asa_id
    
    return collector_data

def update_existing_collector(irn, row, col_prefix):
    """Update an existing collector with new data"""
    # Update brief name if missing
    if 'nam_NamBriefName' not in master_collectors[irn]:
        value = row.get(f'{col_prefix}NamBriefName', '')
        if not pd.isna(value):
            master_collectors[irn]['nam_NamBriefName'] = str(value)
    
    # Add new names to OtherNames
    current_names = set(master_collectors[irn].get('OtherNames', '').split('|'))
    new_names = set()
    
    for field in ['NamFullName', 'NamBriefName', 'NamFirst', 'NamMiddle', 'NamLast', 'NamOtherNames_tab']:
        value = row.get(f'{col_prefix}{field}', '')
        if not pd.isna(value):
            value = str(value)
            if value not in current_names and value != master_collectors[irn].get(f'nam_{field}', ''):
                new_names.add(value)
    
    if new_names:
        existing_other = master_collectors[irn].get('OtherNames', '')
        master_collectors[irn]['OtherNames'] = existing_other + ('|' if existing_other else '') + '|'.join(new_names)
    
    # Add new ASA IDs
    external_refs = row.get(f'{col_prefix}NamExternalReferences_tab', '')
    asa_ids = extract_asa_ids(external_refs)
    if asa_ids:
        existing_asa_ids = [v for k, v in master_collectors[irn].items() 
                          if k.startswith('ASA_Botanist_ID')]
        for asa_id in asa_ids:
            if asa_id not in existing_asa_ids:
                if 'ASA_Botanist_ID' not in master_collectors[irn]:
                    master_collectors[irn]['ASA_Botanist_ID'] = asa_id
                else:
                    n = 2
                    while f'ASA_Botanist_ID_{n}' in master_collectors[irn]:
                        n += 1
                    master_collectors[irn][f'ASA_Botanist_ID_{n}'] = asa_id

# Main Processing Functions
def update_fm_date_ranges(filepath):
    """Update date ranges from countries_combined.csv"""
    df = pd.read_csv(filepath, low_memory=False)
    current_year = pd.Timestamp.now().year
    collector_years = defaultdict(list)
    
    for n in range(1, 12):
        col_prefix = f'col_{n}_'
        irn_col = f'{col_prefix}Collector_irn'
        if irn_col not in df.columns:
            continue
            
        for _, row in df.iterrows():
            irn = row[irn_col]
            if pd.isna(irn):
                continue
            irn = str(int(irn)) if isinstance(irn, float) else str(irn)
            
            for col in ['ColEarliestDateCollected', 'ColLatestDateCollected', 'ColDateCollected']:
                year = extract_year_from_date_string(row.get(col))
                if year:
                    collector_years[irn].append(year)
    
    for irn, years in collector_years.items():
        update_collector_dates(irn, years, current_year)

def extract_years_from_collections(collections_str):
    """Optimized extraction of years from Collections_in string"""
    if pd.isna(collections_str) or not collections_str:
        return []
    
    # Use findall directly on the string
    years = re.findall(r'\b(\d{4})\b', str(collections_str))
    return [int(year) for year in years] if years else []

def format_collections_range(collections_str=None, birth_date=None, death_date=None):
    """Optimized formatting of collection ranges with lifespan calculation"""
    # Extract years if collections_str provided
    years = []
    if collections_str is not None:
        years = extract_years_from_collections(collections_str)
    
    # Clean and validate years
    clean_birth = clean_year(birth_date) if birth_date is not None else None
    clean_death = clean_year(death_date) if death_date is not None else None
    
    # Case 1: We have collection years
    if years:
        return f"{min(years)}-{max(years)}"
    
    # Case 2: Both birth and death dates available
    if clean_birth is not None and clean_death is not None:
        return f"{clean_birth}-{clean_death}"
    
    # Case 3: Only death date available (apply 80-year rule)
    if clean_death is not None:
        return f"{clean_death-80}-{clean_death}"
    
    # Case 4: Only birth date available (birth to birth + 100 years)
    if clean_birth is not None:
        return f"{clean_birth}-{clean_birth+100}"
    
    return None

def process_collector_teams(filepath):
    """Process collector teams from countries_combined.csv"""
    df = pd.read_csv(filepath, low_memory=False)
    collector_teams = defaultdict(set)
    
    for _, row in df.iterrows():
        collectors_in_row = set()
        
        # Collect all collector names in this row
        for n in range(1, 12):
            col_prefix = f'col_{n}_'
            brief_name_col = f'{col_prefix}NamBriefName'
            if brief_name_col in row and not pd.isna(row[brief_name_col]):
                name = clean_name(str(row[brief_name_col]).strip())
                if name:
                    collectors_in_row.add(name)
        
        # Create team strings for each collector
        if len(collectors_in_row) > 1:
            sorted_team = sorted(collectors_in_row)
            team_str = ', '.join(sorted_team)
            for collector in collectors_in_row:
                collector_teams[collector].add(team_str)
    
    # Update master collectors with team info
    for irn, collector in master_collectors.items():
        if 'nam_NamBriefName' in collector:
            brief_name = clean_name(collector['nam_NamBriefName'])
            if brief_name in collector_teams:
                collector['FM_Collector_Teams'] = ' & '.join(sorted(collector_teams[brief_name]))

def process_countries_combined(filepath):
    """Process countries_combined.csv file"""
    df = pd.read_csv(filepath, low_memory=False)
    collector_countries = defaultdict(set)
    
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
            
            # Process countries
            if 'PolPD1' in row and not pd.isna(row['PolPD1']):
                country = str(row['PolPD1']).strip()
                if country:
                    collector_countries[irn].add(country)
            
            # Process collector data
            if irn not in master_collectors:
                master_collectors[irn] = process_collector_row(row, col_prefix, irn)
            else:
                update_existing_collector(irn, row, col_prefix)
    
    # Add countries to master collectors
    for irn, countries in collector_countries.items():
        if irn in master_collectors:
            master_collectors[irn]['FM_Countries'] = '|'.join(sorted(countries))

def process_huh_combined(filepath):
    """Optimized processing of HUH_Combined.csv"""
    df = pd.read_csv(filepath, low_memory=False)
    non_matches = new_entries = 0
    
    # Pre-compile regex for ASA ID extraction
    asa_num_pattern = re.compile(r'\d+')
    
    for _, row in df.iterrows():
        # Clean name fields in bulk
        row_cleaned = {
            k: clean_name(v) if k in ['Name', 'Standard_Label_Name', 'Full_Name'] or 
               k.startswith('Variant_name') else v
            for k, v in row.items()
        }
        
        # Find matching collector
        irn = None
        
        # First try ASA ID match
        asa_field = row_cleaned.get('ASA_Botanist_ID')
        if pd.notna(asa_field):
            asa_id = asa_num_pattern.search(str(asa_field))
            if asa_id:
                asa_id = asa_id.group()
                for existing_irn, collector in master_collectors.items():
                    if collector.get('ASA_Botanist_ID') == asa_id:
                        irn = existing_irn
                        break
                    if not irn:
                        for k, v in collector.items():
                            if k.startswith('ASA_Botanist_ID_') and v == asa_id:
                                irn = existing_irn
                                break
        
        # If no ASA match, try name match
        if not irn:
            huh_names = {
                str(row_cleaned[k]).lower() for k in [
                    'Name', 'Standard_Label_Name', 'Full_Name',
                    *[f'Variant_name_{i}' for i in range(1, 12)]
                ] if k in row_cleaned and pd.notna(row_cleaned[k])
            }
            
            for existing_irn, collector in master_collectors.items():
                for field in ['nam_NamFullName', 'nam_NamFirst', 'nam_NamLast', 
                            'nam_NamBriefName', 'OtherNames']:
                    if field in collector and pd.notna(collector[field]):
                        names = (collector[field].split('|') if field == 'OtherNames' 
                                else [str(collector[field])])
                        if any(name.lower() in huh_names for name in names):
                            irn = existing_irn
                            break
                    if irn:
                        break
                if irn:
                    break
        
        if irn:
            # Update existing collector
            collector = master_collectors[irn]
            
            # Update GUID
            if 'GUID' not in collector and 'GUID' in row_cleaned and pd.notna(row_cleaned['GUID']):
                collector['GUID'] = row_cleaned['GUID']
            
            # Update geography
            for field in ['Geography_Collector', 'Geography_Author']:
                if field in row_cleaned and pd.notna(row_cleaned[field]):
                    if field not in collector or not collector[field]:
                        collector[field] = row_cleaned[field]
            
            # Update collections info
            if 'Collections_in' in row_cleaned and pd.notna(row_cleaned['Collections_in']):
                years = extract_years_from_collections(row_cleaned['Collections_in'])
                if years:
                    range_str = f"{min(years)} - {max(years)}"
                    if 'HUH_Collections_in' not in collector or not collector['HUH_Collections_in']:
                        collector['HUH_Collections_in'] = range_str
            
            # Update lifespan
            birth = clean_year(row_cleaned.get('Date_of_birth'))
            death = clean_year(row_cleaned.get('Date_of_death'))
            lifespan = format_collections_range(None, birth, death)
            if lifespan and ('Lifespan' not in collector or not collector['Lifespan']):
                collector['Lifespan'] = lifespan
            
            # Update standard label name
            if ('Standard_Label_Name' in row_cleaned and pd.notna(row_cleaned['Standard_Label_Name']) and
                ('Standard_Label_Name' not in collector or not collector['Standard_Label_Name'])):
                collector['Standard_Label_Name'] = row_cleaned['Standard_Label_Name']
            
            # Update collector team
            if ('Collector_Teams' in row_cleaned and pd.notna(row_cleaned['Collector_Teams']) and
                ('Collector_Team' not in collector or not collector['Collector_Team'])):
                collector['Collector_Team'] = row_cleaned['Collector_Teams']
            
            # Update variant names
            for i in range(1, 12):
                v_field = f'Variant_name_{i}' if i > 1 else 'Variant_name'
                if (v_field in row_cleaned and pd.notna(row_cleaned[v_field]) and
                    (v_field not in collector or not collector[v_field])):
                    collector[v_field] = row_cleaned[v_field]
            
            # Update source
            if 'Source_of_Information' in collector:
                if 'HUH_Combined.csv' not in collector['Source_of_Information']:
                    collector['Source_of_Information'] += ', HUH_Combined.csv'
            else:
                collector['Source_of_Information'] = 'HUH_Combined.csv'
        else:
            # Create new entry for non-match
            non_matches += 1
            new_irn = f"HUH_{len(master_collectors) + 1}"
            new_entry = {
                'Collector_irn': new_irn,
                'Source_of_Information': 'HUH_Combined.csv',
            }
            
            # Add basic info
            for field in ['GUID', 'Geography_Collector', 'Geography_Author', 
                         'Standard_Label_Name', 'Collector_Teams']:
                if field in row_cleaned and pd.notna(row_cleaned[field]):
                    new_entry[field if field != 'Collector_Teams' else 'Collector_Team'] = row_cleaned[field]
            
            # Add ASA ID if available
            if 'ASA_Botanist_ID' in row_cleaned and pd.notna(row_cleaned['ASA_Botanist_ID']):
                asa_id = asa_num_pattern.search(str(row_cleaned['ASA_Botanist_ID']))
                if asa_id:
                    new_entry['ASA_Botanist_ID'] = asa_id.group()
            
            # Add name info
            for huh_field, master_field in [('Name', 'nam_NamFullName'),
                                          ('Full_Name', 'nam_NamFullName'),
                                          ('Standard_Label_Name', 'Standard_Label_Name')]:
                if huh_field in row_cleaned and pd.notna(row_cleaned[huh_field]):
                    new_entry[master_field] = row_cleaned[huh_field]
            
            # Add collections info
            if 'Collections_in' in row_cleaned and pd.notna(row_cleaned['Collections_in']):
                years = extract_years_from_collections(row_cleaned['Collections_in'])
                if years:
                    new_entry['HUH_Collections_in'] = f"{min(years)} - {max(years)}"
            
            # Add lifespan
            birth = clean_year(row_cleaned.get('Date_of_birth'))
            death = clean_year(row_cleaned.get('Date_of_death'))
            lifespan = format_collections_range(None, birth, death)
            if lifespan:
                new_entry['Lifespan'] = lifespan
            
            # Add variant names
            for i in range(1, 12):
                v_field = f'Variant_name_{i}' if i > 1 else 'Variant_name'
                if v_field in row_cleaned and pd.notna(row_cleaned[v_field]):
                    new_entry[v_field] = row_cleaned[v_field]
                    if i > 1:
                        new_entry['Variant_name_n'] = str(i)
            
            master_collectors[new_irn] = new_entry
            new_entries += 1
    
    print(f"Non-matching HUH records: {non_matches}, New entries created: {new_entries}")

def process_botany_parties_author_names(filepath):
    """Optimized processing of botany parties data"""
    try:
        df = pd.read_excel(filepath)
        source_name = os.path.basename(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return
    
    for _, row in df.iterrows():
        # Try to match by ASA ID first
        matching_irn = None
        if pd.notna(row['External_refs']):
            asa_ids = extract_asa_ids(row['External_refs'])
            if asa_ids:
                asa_id = asa_ids[0]
                for irn, collector in master_collectors.items():
                    if collector.get('ASA_Botanist_ID') == asa_id:
                        matching_irn = irn
                        break
                    if not matching_irn:
                        for k, v in collector.items():
                            if k.startswith('ASA_Botanist_ID_') and v == asa_id:
                                matching_irn = irn
                                break
        
        # If no ASA match, try name match
        if not matching_irn:
            name_variants = {
                str(row[field]).lower() for field in ['Brief', 'Full', 'OtherNam'] 
                if pd.notna(row[field])
            }
            
            for irn, collector in master_collectors.items():
                for field in ['nam_NamFullName', 'nam_NamBriefName', 'OtherNames']:
                    if field in collector and pd.notna(collector[field]):
                        names = (collector[field].split('|') if field == 'OtherNames' 
                                else [str(collector[field])])
                        if any(name.lower() in name_variants for name in names):
                            matching_irn = irn
                            break
                if matching_irn:
                    break
        
        # Update matched collector
        if matching_irn:
            collector = master_collectors[matching_irn]
            
            # Update source
            if 'Source_of_Information' in collector:
                if source_name not in collector['Source_of_Information']:
                    collector['Source_of_Information'] += f", {source_name}"
            else:
                collector['Source_of_Information'] = source_name
            
            # Update taxonomic names
            if pd.notna(row['Taxonomic']) and ('Taxanomic_names' not in collector or not collector['Taxanomic_names']):
                collector['Taxanomic_names'] = str(row['Taxonomic'])
            
            # Add new variant names
            new_variants = [
                str(row[field]).strip() for field in ['Brief', 'Full', 'OtherNam'] 
                if pd.notna(row[field])
            ]
            
            if new_variants:
                existing_names = set()
                for field in ['nam_NamFullName', 'nam_NamBriefName', 'OtherNames'] + \
                            [f'Variant_name_{i}' for i in range(1, 12)]:
                    if field in collector and pd.notna(collector[field]):
                        if field == 'OtherNames':
                            existing_names.update(collector[field].split('|'))
                        else:
                            existing_names.add(str(collector[field]))
                
                for variant in new_variants:
                    if variant not in existing_names:
                        # Find first available slot
                        added = False
                        for i in range(1, 12):
                            v_field = f'Variant_name_{i}' if i > 1 else 'Variant_name'
                            if v_field not in collector or not collector[v_field]:
                                collector[v_field] = variant
                                added = True
                                if i > int(collector.get('Variant_name_n', 0)):
                                    collector['Variant_name_n'] = str(i)
                                break
                        
                        if not added:
                            collector['OtherNames'] = '|'.join(
                                [collector.get('OtherNames', ''), variant] 
                                if 'OtherNames' in collector else [variant]
                            )


def create_master_collector():
    """Main function to create the master collector file"""
    # Process data files
    process_countries_combined('EMU_Combined_Sheets/countries_combined.csv')
    process_huh_combined('HUH/HUH_Combined.csv')    
    process_botany_parties_author_names('BotanyParties/Botany_Parties_Author_names.xlsx')
    
    #Add data
    update_fm_date_ranges('EMU_Combined_Sheets/countries_combined.csv')
    process_collector_teams('EMU_Combined_Sheets/countries_combined.csv')
    
    # Convert to DataFrame and clean names
    master_df = pd.DataFrame.from_dict(master_collectors, orient='index')
    
    # Clean name fields
    name_cols = ['nam_NamFullName', 'nam_NamBriefName', 'nam_NamFirst', 
                'nam_NamMiddle', 'nam_NamLast', 'Standard_Label_Name', 'Variant_name']
    name_cols += [f'Variant_name_{i}' for i in range(1, 12)]
    
    for col in name_cols:
        if col in master_df.columns:
            master_df[col] = master_df[col].apply(clean_name)
    
    master_df['OtherNames'] = master_df['OtherNames'].apply(
        lambda x: '|'.join([clean_name(n) for n in str(x).split('|')]) if not pd.isna(x) else x
    )
    
    # Define and order output columns
    base_cols = [
        'Collector_irn', 'GUID', 'ASA_Botanist_ID', 
        'Source_of_Information', 'Geography_Collector', 'Geography_Author', 
        'FM_Countries', 'Lifespan', 'HUH_Collections_in', 'date_range_FM', 
        'Standard_Label_Name', 'nam_NamFullName', 'nam_NamBriefName', 'nam_NamFirst', 
        'nam_NamMiddle', 'nam_NamLast', 'OtherNames', 'Variant_name', 
        'Taxanomic_names', 'Collector_Team', 'FM_Collector_Teams'
    ]
    
    asa_id_cols = sorted([c for c in master_df.columns if c.startswith('ASA_Botanist_ID_')], 
                         key=lambda x: int(x.split('_')[-1]))
    
    variant_cols = [f'Variant_name_{i}' for i in range(2, 12)]
    
    output_cols = base_cols[:3] + asa_id_cols + base_cols[3:16] + variant_cols + base_cols[16:]
    
    # Ensure all columns exist
    for col in output_cols:
        if col not in master_df.columns:
            master_df[col] = ''
    
    master_df[output_cols].to_csv('Master_Collector(Original).csv', index=False)
    print("Master_Collector(Original).csv file created")

if __name__ == '__main__':
    create_master_collector()