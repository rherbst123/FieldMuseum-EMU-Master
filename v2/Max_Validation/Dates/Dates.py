import pandas as pd
import re


# Seperate Day and month year
# If  Letters NOT AMBIGIOUS (Day)
# Check minimum 
# Cs for heck Collector Date 00XX Years. 
# if unvalidated 00XX put into brackets (After collector validation) 


def extract_year(date_str):
    """
    Extract year from date string. Mark years like 0000 or 00XX as ambiguous.
    """
    if pd.isna(date_str) or date_str == "":
        return ""
    
    date_str = str(date_str).strip().strip('"').strip("'").strip()
    if not date_str:
        return ""
    
    # Find 4-digit year pattern
    year_match = re.search(r'\b(\d{4})\b', date_str)
    if year_match:
        year = year_match.group(1)
        # Check if year is ambiguous (0000 or 00XX pattern)
        if year == "0000" or re.match(r'^00\d{2}$', year):
            return f"[{year}]"
        return year
    
    return ""

def analyze_date(date_str):
    """
    Analyze a date string to determine if it's ambiguous or non-ambiguous.
    
    Non-Ambiguous: Any date containing letters/characters, or formats like DD-MM-YYYY, DD/MM/YY.
    Ambiguous: Purely numeric dates that don't match common date patterns, empty dates, or dates with brackets.
    """
    if pd.isna(date_str) or date_str == "":
        return "", ""
    
    # Remove quotations and strip whitespace
    date_str = str(date_str).strip().strip('"').strip("'").strip()
    
    # If empty after cleaning, return empty
    if not date_str:
        return "", ""
    
    # If the date contains brackets, it's ambiguous
    if '[' in date_str or ']' in date_str:
        return date_str, ""
    
    # If the date contains any letters, it's non-ambiguous
    if re.search(r'[a-zA-Z]', date_str):
        return "", date_str
        
    # Regex to match formats like 26-02-1973 or 28/5/46
    if re.search(r'^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$', date_str):
        return "", date_str
        
    # If it doesn't contain letters and doesn't match the pattern, it's ambiguous
    else:
        return date_str, ""

def parse_collector_date_range(date_range_str):
    """Safely parse a date range string (e.g., '1950-1990' or '1965') into a start and end year."""
    if pd.isna(date_range_str):
        return None
    try:
        # Find all 4-digit numbers, which represent years
        years = re.findall(r'\b\d{4}\b', str(date_range_str))
        if len(years) >= 2:
            # Multiple years found, use the first and last as the range
            start_year = int(years[0])
            end_year = int(years[-1])
            return min(start_year, end_year), max(start_year, end_year)
        elif len(years) == 1:
            # Single year found, range is that year
            year = int(years[0])
            return year, year
    except (ValueError, TypeError):
        # Handle cases where conversion to int fails or input is not as expected
        pass
    return None

def build_master_collector_lookup(master_df):
    """Build a lookup dictionary from all possible collector name columns and IRNs to their date ranges."""
    lookup = {}
    
    # List of all columns that might contain a collector's name
    name_columns = [
        'Standard_Label_Name', 'nam_NamFullName', 'nam_NamBriefName', 
        'nam_NamFirst', 'nam_NamMiddle', 'nam_NamLast', 
        'Variant_name_2', 'Variant_name_3', 'Variant_name_4', 'Variant_name_5',
        'Variant_name_6', 'Variant_name_7', 'Variant_name_8', 'Variant_name_9',
        'Variant_name_10', 'Variant_name_11', 'Variant_name_12', 'Variant_name_13',
        'Variant_name_14', 'Variant_name_15', 'Variant_name_16', 'Variant_name_17',
        'Variant_name_18', 'Variant_name_19', 'Variant_name_20', 'Variant_name',
        'HUH_Collections_in_Field'
    ]
    
    # The column containing the date range and the IRN
    date_range_col = 'date_range_FM'
    irn_col = 'Collector_irn' # Assumed IRN column in master file

    for _, row in master_df.iterrows():
        date_range = parse_collector_date_range(row.get(date_range_col))
        if date_range:
            # Add all name variants to the lookup
            for col in name_columns:
                if col in row and pd.notna(row[col]):
                    name = str(row[col]).strip().lower()
                    if name:
                        lookup[name] = date_range
            
            # Add the collector IRN to the lookup
            if irn_col in row and pd.notna(row[irn_col]):
                irn = str(int(row[irn_col])) # Ensure IRN is a clean string
                lookup[irn] = date_range
    return lookup

def find_collector_column(df):
    """Dynamically find the primary collector column in the input dataframe."""
    # List of possible column names for the collector, in order of preference
    possible_columns = [
        'collectorName1', 'Collector_1_EMu_Name', 'Primary_Collector_1', 'CollectorName', 'Collector'
    ]
    for col in possible_columns:
        if col in df.columns:
            # Return the first one found
            return col
    return None

def process_transcription_file(input_file, output_file, master_collector_file):
    """Process the transcription CSV file and add Ambiguous/Non_Ambiguous/Years/DateValidation columns."""
    
    try:
        df = pd.read_csv(input_file, low_memory=False)
        master_df = pd.read_csv(master_collector_file, low_memory=False)
    except FileNotFoundError as e:
        print(f"Error: Input file not found. {e}")
        return
    except Exception as e:
        print(f"Error reading CSV files: {e}")
        return

    # --- 1. Build Master Collector Lookup ---
    master_collectors = build_master_collector_lookup(master_df)
    if not master_collectors:
        print("Warning: Master collector lookup table is empty. Date validation will be skipped.")

    # --- 2. Prepare Input DataFrame ---
    # Find the correct collector column dynamically
    collector_column = find_collector_column(df)
    if not collector_column:
        print("Error: Could not find a suitable collector name column in the input file.")
        # Still, we can proceed without date validation
    else:
        # Normalize the collector names from the identified column
        df['normalized_collector'] = df[collector_column].astype(str).str.strip().str.lower()

    # Identify and convert all irn/ID columns to integers, handling potential errors
    for col in df.columns:
        if 'irn' in col.lower() or 'id' in col.lower():
            # Use pd.to_numeric to handle non-numeric values gracefully by turning them into NaNs
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

    # Ensure CatalogueNumber is an integer, handling potential errors
    if 'CatalogueNumber' in df.columns:
        df['CatalogueNumber'] = pd.to_numeric(df['CatalogueNumber'], errors='coerce').astype('Int64')
            
    # Clean the VerbatimCollectionDate column
    df['VerbatimCollectionDate'] = df['VerbatimCollectionDate'].astype(str).str.strip().str.strip('"').str.strip("'").str.strip()
    df['VerbatimCollectionDate'] = df['VerbatimCollectionDate'].replace('nan', '')

    # --- 3. Process Each Row ---
    verbatim_col_idx = df.columns.get_loc('VerbatimCollectionDate')
    
    # Prepare lists to hold the new column data
    ambiguous_data = []
    non_ambiguous_data = []
    years_data = []
    date_validation_data = []
    
    print("\n--- Starting Date Validation Detailed Log ---")
    for index, row in df.iterrows():
        print(f"\nProcessing row {index + 2}:") # +2 to account for header and 0-based index

        # Analyze VerbatimCollectionDate
        verbatim_date = row['VerbatimCollectionDate']
        ambiguous, non_ambiguous = analyze_date(verbatim_date)
        ambiguous_data.append(ambiguous)
        non_ambiguous_data.append(non_ambiguous)
        
        # Extract year from Verbatim, MinimumDate, or an existing 'Years' column
        verbatim_year = extract_year(row['VerbatimCollectionDate'])
        minimum_year = extract_year(row.get('MinimumDate', ''))
        years_col_year = extract_year(row.get('Years', '')) # Check for existing 'Years' column
        
        final_year_str = verbatim_year or minimum_year or years_col_year
        years_data.append(final_year_str)
        print(f"  - Extracted Year: '{final_year_str}' (from Verbatim: '{verbatim_year}', Minimum: '{minimum_year}', Years Col: '{years_col_year}')")

        # --- 4. Validate Date Against Collector's Range ---
        validation_result = ""
        # Prioritize checking by IRN first, then by name
        primary_irn = row.get('primary_master_irn')
        collector_name = row.get('normalized_collector')
        print(f"  - Collector Info: IRN='{primary_irn}', Name='{collector_name}'")

        # Clean the IRN value - convert to integer string, handle NaNs
        if pd.notna(primary_irn):
            try:
                primary_irn = str(int(primary_irn))
            except (ValueError, TypeError):
                primary_irn = None # Set to None if it's not a valid number
        else:
            primary_irn = None

        key_to_check = None
        if primary_irn and primary_irn in master_collectors:
            key_to_check = primary_irn
            print(f"  - Using IRN '{primary_irn}' for lookup.")
        elif collector_name and collector_name in master_collectors:
            key_to_check = collector_name
            print(f"  - Using Collector Name '{collector_name}' for lookup.")

        if key_to_check:
            print(f"  - Collector '{key_to_check}' found in master file.")
            if final_year_str and final_year_str.isdigit():
                year_to_check = int(final_year_str)
                start_year, end_year = master_collectors[key_to_check]
                print(f"  - Collector's valid date range: {start_year}-{end_year}")
                if start_year <= year_to_check <= end_year:
                    validation_result = "In Range"
                else:
                    validation_result = "Out of Range"
            elif final_year_str:
                validation_result = "Invalid Year Format"
            else:
                validation_result = "No Year Found"
        elif primary_irn or collector_name:
             validation_result = "Collector Not Found"
             print(f"  - Collector not found in master file.")
        else:
            validation_result = "No Collector Info"
            print(f"  - No collector IRN or name provided for this row.")
            
        date_validation_data.append(validation_result)
        print(f"  - Validation Result: {validation_result}")

    print("\n--- End of Date Validation Detailed Log ---")

    # --- 5. Insert New Columns and Save ---
    df.insert(verbatim_col_idx + 1, 'Ambiguous', ambiguous_data)
    df.insert(verbatim_col_idx + 2, 'Non_Ambiguous', non_ambiguous_data)
    df.insert(verbatim_col_idx + 3, 'Years', years_data)
    df.insert(verbatim_col_idx + 4, 'DateValidation', date_validation_data)

    # Drop the temporary normalized column if it was created
    if 'normalized_collector' in df.columns:
        df = df.drop(columns=['normalized_collector'])
    
    # Final conversion to handle CatalogueNumber as integer strings for output
    if 'CatalogueNumber' in df.columns:
        df['CatalogueNumber'] = df['CatalogueNumber'].astype('Int64').astype(str).replace('<NA>', '')

    try:
        df.to_csv(output_file, index=False)
    except Exception as e:
        print(f"Error saving output file: {e}")
        return
    
    # --- 6. Print Summary ---
    ambiguous_count = sum(1 for x in ambiguous_data if x)
    non_ambiguous_count = sum(1 for x in non_ambiguous_data if x)
    years_extracted = sum(1 for x in years_data if x)
    in_range_count = sum(1 for x in date_validation_data if x == "In Range")
    out_of_range_count = sum(1 for x in date_validation_data if x == "Out of Range")
    not_found_count = sum(1 for x in date_validation_data if x == "Collector Not Found")
    
    print("Processing complete!")
    print(f"Total records processed: {len(df)}")
    print(f"Ambiguous dates: {ambiguous_count}")
    print(f"Non-ambiguous dates: {non_ambiguous_count}")
    print(f"Years extracted: {years_extracted}")
    print("-" * 20)
    print("Date Validation Summary:")
    print(f"  In Range: {in_range_count}")
    print(f"  Out of Range: {out_of_range_count}")
    print(f"  Collector Not Found: {not_found_count}")
    print("-" * 20)
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    input_file = r"C:\Users\Riley\Documents\GitHub\FieldMuseum-EMU-Master\v2\Max_Validation\Testing\Modified_Max_Sheet_with_Top_Results.csv"
    output_file = r"C:\Users\Riley\Documents\GitHub\FieldMuseum-EMU-Master\v2\Max_Validation\Dates\Modified_Max_Sheet_with_Top_Results_with_date_analysis.csv"
    master_collector_file = r"C:\Users\Riley\Documents\GitHub\FieldMuseum-EMU-Master\v2\Max_Validation\Dates\Validator\Master_Collector(newmain).csv"
    
    process_transcription_file(input_file, output_file, master_collector_file)