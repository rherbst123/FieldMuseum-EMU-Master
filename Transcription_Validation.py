import pandas as pd


## This script was created by Riley Herbst and Alex Wcislo

##TODO: 
"""
Add Validation for the following fields
- Collector names: Check All variants, Collector Teams
- Dates: Check record to the collector ranges and dates
- Countries: Yes or No 

- Score: TBD on what our metrics are.
- But talked about score being not a way of determining how "Good" something is but how "bad" and can be used for sorting
"""
#Here is the Sheet we have been working on

"""
# Validation criteria
VALIDATION_RULES = {
    'botanist_id': {
        'type': 'match',
        'source': 'F_party_botanist_id',
        'score': ['yes', 'no']
    },
    'name_variant': {
        'type': 'match', 
        'note': 'Handle multiple IRN matches for ambiguous names',
        'score': ['yes', 'no']
    },
    'country': {
        'type': 'match',
        'score': ['yes', 'no']
    },
    'date': {
        'rules': {
            'birth_date': {
                'range': [20, 80],  # Years after birth
                'note': 'Must be before death date'
            },
            'collection_dates': {
                'F_party': {
                    'range': [-20, 20],  # Years +/- collection date
                    'weight': 'high'
                },
                'HUH': {
                    'range': [-30, 30]  # Years +/- collection date
                }
            }
        },
        'special_case': 'Handle 00 in four digit years'
    },
    'score_components': {
        'lifetime': ['yes', 'no', 'unknown'],
        'collecting_times': ['F', 'HUH', 'both', 'no'],
        'collector_teams': {
            'match_type': 'last_name',
            'score': ['F', 'HUH', 'both', 'no']
        }
    }
}
"""





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
    
    
    example_df.to_csv(output_csv_path, index=False)
    return example_df










def get_output_filename():
    filename = input("Enter the Output name for the file: ")
    if not filename.endswith('.csv'):
        filename += '.csv'
    return filename

if __name__ == "__main__":
    output_file = get_output_filename()
    result_df = merge_collector_data(
        'Examples/Example CSV for Max - Sheet1.csv',
        'Master_Collector(main).csv',
        output_file
    )
    print(f"Final sheet created successfully as {output_file}!")