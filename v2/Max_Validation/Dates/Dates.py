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
    
    Non-Ambiguous: Any date containing letters/characters
    Ambiguous: Purely numeric dates or empty dates
    """
    if pd.isna(date_str) or date_str == "":
        return "", ""
    
    # Remove quotations and strip whitespace
    date_str = str(date_str).strip().strip('"').strip("'").strip()
    
    # If empty after cleaning, return empty
    if not date_str:
        return "", ""
    
    # If the date contains any letters, it's non-ambiguous
    if re.search(r'[a-zA-Z]', date_str):
        return "", date_str
    else:
        return date_str, ""

def process_transcription_file(input_file, output_file):
    """Process the transcription CSV file and add Ambiguous/Non_Ambiguous/Years columns"""
    
    # Read the CSV file
    df = pd.read_csv(input_file)
    
    # Clean the VerbatimCollectionDate column - remove quotes
    df['VerbatimCollectionDate'] = df['VerbatimCollectionDate'].astype(str).str.strip().str.strip('"').str.strip("'").str.strip()
    df['VerbatimCollectionDate'] = df['VerbatimCollectionDate'].replace('nan', '')
    
    # Find the VerbatimCollectionDate column index
    verbatim_col_idx = df.columns.get_loc('VerbatimCollectionDate')
    
    # Create new columns
    ambiguous_data = []
    non_ambiguous_data = []
    years_data = []
    
    for i, row in df.iterrows():
        # Analyze VerbatimCollectionDate
        verbatim_date = row['VerbatimCollectionDate']
        ambiguous, non_ambiguous = analyze_date(verbatim_date)
        ambiguous_data.append(ambiguous)
        non_ambiguous_data.append(non_ambiguous)
        
        # Extract year from both VerbatimCollectionDate and MinimumDate
        verbatim_year = extract_year(verbatim_date)
        minimum_year = extract_year(row.get('MinimumDate', '')) if 'MinimumDate' in df.columns else ''
        
        # Use verbatim year if available, otherwise use minimum year
        final_year = verbatim_year if verbatim_year else minimum_year
        years_data.append(final_year)
    
    # Insert new columns after VerbatimCollectionDate
    df.insert(verbatim_col_idx + 1, 'Ambiguous', ambiguous_data)
    df.insert(verbatim_col_idx + 2, 'Non_Ambiguous', non_ambiguous_data)
    df.insert(verbatim_col_idx + 3, 'Years', years_data)
    
    # Save the processed file
    df.to_csv(output_file, index=False)
    
    # Print summary
    ambiguous_count = sum(1 for x in ambiguous_data if x != "")
    non_ambiguous_count = sum(1 for x in non_ambiguous_data if x != "")
    years_with_brackets = sum(1 for x in years_data if '[' in str(x))
    years_extracted = sum(1 for x in years_data if x != "")
    total_count = len(df)
    
    print(f"Processing complete!")
    print(f"Total records: {total_count}")
    print(f"Ambiguous dates: {ambiguous_count}")
    print(f"Non-ambiguous dates: {non_ambiguous_count}")
    print(f"Years extracted: {years_extracted}")
    print(f"Ambiguous years (in brackets): {years_with_brackets}")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    input_file = r"../Testing/Modified_Max_Sheet_with_Top_Results.csv"
    output_file = r"/home/riley/Documents/Python/Max_Validation/Dates/Modified_Max_Sheet_with_Top_Results_with_date_analysis.csv"
    
    process_transcription_file(input_file, output_file)