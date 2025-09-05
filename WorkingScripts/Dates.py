import pandas as pd
import re
import argparse
import os
import sys
import textwrap
from pathlib import Path


# Seperate Day and month year
# If  Letters NOT AMBIGIOUS (Day)
# Check minimum 
# Cs for heck Collector Date 00XX Years. 
# if unvalidated 00XX put into brackets (After collector validation) 

#Look at Verbatim NAMES !! 

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

# New helper to resolve column names case-insensitively and by aliases
def resolve_column_name(df: pd.DataFrame, candidates):
    """Return the actual column name in df matching any candidate (case-insensitive)."""
    if not isinstance(candidates, (list, tuple)):
        candidates = [candidates]
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if not cand:
            continue
        found = lower_map.get(str(cand).lower())
        if found:
            return found
    return None

# NEW: Robust detection of IRN and date-range columns in Master file

def _find_master_irn_column(master_df: pd.DataFrame):
    candidates = [
        'Collector_irn', 'primary_master_irn', 'nam_irn', 'NamIRN', 'IRN', 'irn'
    ]
    col = resolve_column_name(master_df, candidates)
    if col:
        return col
    for c in master_df.columns:
        if 'irn' in str(c).lower():
            return c
    return None


def _find_master_date_range_column(master_df: pd.DataFrame):
    candidates = [
        'date_range_FM', 'Date_Range_FM', 'date_range', 'Date Range',
        'years_active', 'Years_Active', 'Active_Years', 'activity_dates',
        'DatesActive', 'collector_dates'
    ]
    col = resolve_column_name(master_df, candidates)
    if col:
        return col
    for c in master_df.columns:
        cl = str(c).lower()
        if 'date' in cl and ('range' in cl or 'active' in cl or 'years' in cl):
            return c
    return None


def build_master_collector_lookup(master_df):
    """Build a lookup dictionary from all possible collector name columns and IRNs to their date ranges.
    Keys: lower-cased names and IRN strings. Values: (start_year, end_year) or None if no range parsable.
    """
    lookup = {}

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
    existing_name_cols = [c for c in (resolve_column_name(master_df, c) for c in name_columns) if c]

    date_range_col = _find_master_date_range_column(master_df)
    irn_col = _find_master_irn_column(master_df)

    for _, row in master_df.iterrows():
        raw_range = row.get(date_range_col) if date_range_col else None
        date_range = parse_collector_date_range(raw_range) if raw_range is not None else None

        # Add all name variants to the lookup (store first seen non-None range)
        for col in existing_name_cols:
            val = row.get(col)
            if pd.notna(val):
                name = str(val).strip().lower()
                if name:
                    if name not in lookup or lookup[name] is None:
                        lookup[name] = date_range

        # Add the collector IRN to the lookup
        if irn_col:
            irn_val = row.get(irn_col)
            if pd.notna(irn_val):
                try:
                    irn_key = str(int(irn_val))
                except (ValueError, TypeError):
                    irn_key = str(irn_val).strip()
                if irn_key:
                    if irn_key not in lookup or lookup[irn_key] is None:
                        lookup[irn_key] = date_range

    return lookup

def find_collector_column(df):
    """Dynamically find the primary collector column in the input dataframe."""
    possible_columns = [
        'collectorName1', 'Collector_1_EMu_Name', 'Primary_Collector_1', 'CollectorName', 'Collector'
    ]
    for col in possible_columns:
        if col in df.columns:
            # Return the first one found
            return col
    return None

# NEW: try to find the IRN column in input rows

def find_input_irn_column(df: pd.DataFrame):
    candidates = [
        'primary_master_irn', 'Collector_irn', 'collector_irn', 'master_irn', 'IRN', 'irn'
    ]
    col = resolve_column_name(df, candidates)
    if col:
        return col
    for c in df.columns:
        cl = str(c).lower()
        if 'irn' in cl and 'primary' in cl:
            return c
    for c in df.columns:
        if 'irn' in str(c).lower():
            return c
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

    # Resolve key column names that vary by case/spelling across files
    verbatim_col = resolve_column_name(df, [
        'VerbatimCollectionDate', 'verbatimCollectionDate', 'VerbatimDate', 'verbatim_date'
    ])
    if not verbatim_col:
        print("Error: Could not find a 'VerbatimCollectionDate' column (tried variants: VerbatimCollectionDate, verbatimCollectionDate, VerbatimDate, verbatim_date).")
        print("Available columns:", list(df.columns))
        return

    min_date_col = resolve_column_name(df, ['MinimumDate', 'minimumDate', 'MinDate', 'minDate'])
    years_src_col = resolve_column_name(df, ['Years', 'Year', 'years', 'year'])
    catalogue_col = resolve_column_name(df, ['CatalogueNumber', 'CatologueNumber'])

    # --- 1. Build Master Collector Lookup ---
    master_collectors = build_master_collector_lookup(master_df)
    if not master_collectors:
        print("Warning: Master collector lookup table is empty. Date validation will be skipped.")
    # Diagnostics: which columns were detected in master
    try:
        master_irn_col = _find_master_irn_column(master_df)
        master_range_col = _find_master_date_range_column(master_df)
        print(f"Detected master IRN column: {master_irn_col or 'None'}; Date range column: {master_range_col or 'None'}")
    except Exception:
        pass

    # --- 2. Prepare Input DataFrame ---
    # Find the correct collector column dynamically
    collector_column = find_collector_column(df)
    if not collector_column:
        print("Error: Could not find a suitable collector name column in the input file.")
        # Still, we can proceed without date validation
    else:
        # Normalize the collector names from the identified column
        df['normalized_collector'] = df[collector_column].astype(str).str.strip().str.lower()

    # Identify IRN column in input (more robust)
    input_irn_col = find_input_irn_column(df)
    print(f"Detected input IRN column: {input_irn_col or 'None'}")
    # Diagnostics: IRN overlap
    if input_irn_col:
        try:
            input_irns = df[input_irn_col].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            input_irn_unique = set([x for x in input_irns.unique() if x and x.lower() not in ('nan', 'none')])
            master_irn_keys = {k for k in master_collectors.keys() if k.isdigit()}
            matched_irns = input_irn_unique & master_irn_keys
            print(f"Input IRNs: {len(input_irn_unique)} unique; Master IRNs: {len(master_irn_keys)}; Matches by IRN: {len(matched_irns)}")
        except Exception:
            pass

    # Identify and convert all irn/ID columns to integers, handling potential errors
    # Exclude validation match columns that contain structured data like "True|12345"
    for col in df.columns:
        lower = col.lower()
        # Skip columns that contain match results (they have structured validation data)
        if '_match' in lower:
            continue
        if 'irn' in lower or ('id' in lower and 'uuid' not in lower):
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            except Exception:
                pass

    if catalogue_col:
        try:
            df[catalogue_col] = pd.to_numeric(df[catalogue_col], errors='coerce').astype('Int64')
        except Exception:
            pass
            
    df[verbatim_col] = df[verbatim_col].astype(str).str.strip().str.strip('"').str.strip("'").str.strip()
    df[verbatim_col] = df[verbatim_col].replace('nan', '')

    # --- 3. Process Each Row ---
    verbatim_col_idx = df.columns.get_loc(verbatim_col)
    
    ambiguous_data = []
    non_ambiguous_data = []
    years_data = []
    date_validation_data = []
    
    print("\n--- Starting Date Validation Detailed Log ---")
    for index, row in df.iterrows():
        print(f"\nProcessing row {index + 2}:")

        # Analyze VerbatimCollectionDate
        verbatim_date = row[verbatim_col]
        ambiguous, non_ambiguous = analyze_date(verbatim_date)
        ambiguous_data.append(ambiguous)
        non_ambiguous_data.append(non_ambiguous)
        
        # Extract year from Verbatim, MinimumDate, or an existing 'Years'/'Year' column
        verbatim_year = extract_year(row[verbatim_col])
        minimum_year = extract_year(row[min_date_col]) if min_date_col else ""
        years_col_year = extract_year(row[years_src_col]) if years_src_col else ""  # Check for existing 'Years'/'Year' column
        
        final_year_str = verbatim_year or minimum_year or years_col_year
        years_data.append(final_year_str)
        print(f"  - Extracted Year: '{final_year_str}' (from Verbatim: '{verbatim_year}', Minimum: '{minimum_year}', Years Col: '{years_col_year}')")

        # --- 4. Validate Date Against Collector's Range ---
        validation_result = ""
        # Prioritize checking by IRN first, then by names
        primary_irn = row.get(input_irn_col) if input_irn_col else None
        if pd.notna(primary_irn):
            try:
                primary_irn = str(int(primary_irn))
            except (ValueError, TypeError):
                primary_irn = str(primary_irn).strip()
        else:
            primary_irn = None

        # Prepare name candidates for lookup
        verbatim_collector_name = row.get('verbatimCollector1')
        master_collector_name = row.get('primary_master_name')
        name_candidates = []
        if 'normalized_collector' in row and pd.notna(row['normalized_collector']):
            name_candidates.append(str(row['normalized_collector']).strip().lower())
        if pd.notna(master_collector_name):
            name_candidates.append(str(master_collector_name).strip().lower())
        if pd.notna(verbatim_collector_name):
            name_candidates.append(str(verbatim_collector_name).strip().lower())

        print(f"  - Collector Info: IRN='{primary_irn}', Name candidates={name_candidates[:3]}")

        key_to_check = None
        if primary_irn and primary_irn in master_collectors:
            key_to_check = primary_irn
            print(f"  - Using IRN '{primary_irn}' for lookup.")
        else:
            for nm in name_candidates:
                if nm and nm in master_collectors:
                    key_to_check = nm
                    print(f"  - Using Collector Name '{nm}' for lookup.")
                    break

        if key_to_check:
            print(f"  - Collector '{key_to_check}' found in master file.")
            date_range = master_collectors.get(key_to_check)
            if date_range is None:
                validation_result = "Collector Found (No Master Range)"
            else:
                if final_year_str and final_year_str.isdigit():
                    year_to_check = int(final_year_str)
                    start_year, end_year = date_range
                    print(f"  - Collector's valid date range: {start_year}-{end_year}")
                    if start_year <= year_to_check <= end_year:
                        validation_result = "In Range"
                    else:
                        validation_result = "Out of Range"
                elif final_year_str:
                    validation_result = "Invalid Year Format"
                else:
                    validation_result = "No Year Found"
        elif primary_irn or name_candidates:
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

    # The verbatim collector names are already in the data, no need to add new columns
    
    # Drop the temporary normalized column if it was created
    if 'normalized_collector' in df.columns:
        df = df.drop(columns=['normalized_collector'])
    
    # Final conversion to handle CatalogueNumber/CatologueNumber as integer strings for output
    if catalogue_col:
        try:
            df[catalogue_col] = df[catalogue_col].astype('Int64').astype(str).replace('<NA>', '')
        except Exception:
            pass

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
    no_range_count = sum(1 for x in date_validation_data if x == "Collector Found (No Master Range)")
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
    print(f"  Found (No Master Range): {no_range_count}")
    print(f"  Collector Not Found: {not_found_count}")
    print("-" * 20)
    print(f"Output saved to: {output_file}")
    
    # Print examples of collector names from existing columns
    if 'verbatimCollector1' in df.columns:
        # Filter out 'nan' strings and actual NaN values
        verbatim_clean = df['verbatimCollector1'][~df['verbatimCollector1'].isna() & 
                                                  ~df['verbatimCollector1'].astype(str).str.lower().isin(['nan', '', 'none'])]
        unique_verbatim = verbatim_clean.unique()
        print(f"\nVerbatim collector names: {len(unique_verbatim)} unique names")
        if len(unique_verbatim) > 0:
            print("Examples:", list(unique_verbatim[:5]))
    
    if 'primary_master_name' in df.columns:
        # Filter out 'nan' strings and actual NaN values
        master_clean = df['primary_master_name'][~df['primary_master_name'].isna() & 
                                                 ~df['primary_master_name'].astype(str).str.lower().isin(['nan', '', 'none'])]
        unique_master = master_clean.unique()
        print(f"Master collector names: {len(unique_master)} unique names")
        if len(unique_master) > 0:
            print("Examples:", list(unique_master[:5]))
 
def _default_output_path(input_path: str) -> str:
    p = Path(input_path)
    return str(p.with_name(f"{p.stem}_with_date_analysis{p.suffix}"))


def _print_instructions():
    banner = textwrap.dedent(
        """
        Date Validation Tool
        --------------------
        This script analyzes 'VerbatimCollectionDate' values, extracts years,
        flags ambiguous dates, and validates years against a Master Collector date range.

        Required columns in your input file (case-insensitive variants supported):
          - VerbatimCollectionDate (or verbatimCollectionDate / VerbatimDate / verbatim_date)
          - Needed: MinimumDate, Years/Year, collector name columns (e.g., collectorName1)
          - Needed: primary_master_irn, primary_master_name, verbatimCollector1

        Usage (PowerShell):
          python Dates.py -i "<path>\\Modified_Max_Sheet_with_Top_Results.csv" -m "<path>\\Master_Collector(newmain).csv"
          python Dates.py -i .\\Modified_Max_Sheet_with_Top_Results.csv -m .\\Validations\\Master_Collector(newmain).csv -o .\\out.csv

       
        """
    ).strip()
    print(banner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Dates.py",
        description="Analyze and validate collection dates in a CSV using a Master Collector date range file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples (PowerShell):
              python Dates.py -i "C:\\path\\Modified_Max_Sheet_with_Top_Results.csv" -m "C:\\path\\Master_Collector(newmain).csv"
              python Dates.py -i .\\Modified_Max_Sheet_with_Top_Results.csv -m .\\Validations\\Master_Collector(newmain).csv -o .\\output.csv
            """
        ).strip(),
    )
    parser.add_argument(
        "-i", "--input", dest="input_file", required=False, help="Path to the input CSV file to process."
    )
    parser.add_argument(
        "-m", "--master", dest="master_collector_file", required=False, help="Path to the Master Collector CSV file."
    )
    parser.add_argument(
        "-o", "--output", dest="output_file", required=False, help="Path to write the output CSV. Defaults to '<input>_with_date_analysis.csv'."
    )

    # If launched with no args, show instructions and help then exit.
    if len(sys.argv) == 1:
        _print_instructions()
        print()
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if not args.input_file or not args.master_collector_file:
        print("Error: --input and --master are required.")
        print()
        parser.print_help()
        sys.exit(1)

    input_file = args.input_file
    master_collector_file = args.master_collector_file
    output_file = args.output_file or _default_output_path(input_file)

    # Basic validation of file paths
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    if not os.path.exists(master_collector_file):
        print(f"Error: Master Collector file not found: {master_collector_file}")
        sys.exit(1)

    # Show a brief instruction banner at start of run
    _print_instructions()
    print()
    print(f"Input:  {input_file}")
    print(f"Master: {master_collector_file}")
    print(f"Output: {output_file}")
    print("-" * 20)

    process_transcription_file(input_file, output_file, master_collector_file)