# MAX Collector Validation System

This system validates collector names from MAX spreadsheets against a Master collector database and assigns appropriate IRNs and botanist IDs.

## Files Structure

```
Max_Validation/
├── FilesToValidate/          # Place your MAX CSV files here
│   └── Example_MAX_Sheet.csv
├── Validators/               # Master database files
│   └── Master_Collector(newmain).csv
├── ValidatedFiles/          # Output directory (created automatically)
├── collector_validation.py  # Main validation script
├── batch_validator.py      # Batch processing script
└── requirements.txt        # Python dependencies
```

## Installation

1. Install required Python packages:
```bash
pip install -r requirements.txt
```

## Usage

### Single File Validation

To validate a single MAX file:

```bash
python collector_validation.py
```

This will process `FilesToValidate/Example_MAX_Sheet.csv` and create a validated output file.

### Batch Processing

To validate all CSV files in the `FilesToValidate` directory:

```bash
python batch_validator.py
```

This will:
- Process all CSV files in `FilesToValidate/`
- Create validated files in `ValidatedFiles/`
- Generate a summary report

## How It Works

1. **Name Matching**: The script matches collector names from MAX sheets against the Master database using:
   - Exact matches on standard names
   - Exact matches on variant names
   - Fuzzy matching as fallback (80% similarity threshold)

2. **Data Assignment**: For matched collectors, the script assigns:
   - Collector IRN
   - ASA Botanist ID
   - GUID
   - Match confidence level

3. **Output**: Creates new CSV files with additional validation columns:
   - `Validation_Status`: MATCHED or NO_MATCH
   - `Matched_Collector`: Name from master database
   - `Assigned_IRN`: Collector IRN number
   - `Assigned_Botanist_ID`: Botanist ID
   - `Assigned_GUID`: GUID identifier
   - `Match_Confidence`: Confidence level

## Validation Results

The script provides:
- Match statistics (total, matched, unmatched records)
- Match rate percentage
- Detailed validation columns in output files
- Summary reports for batch processing

## Customization

You can modify the scripts to:
- Adjust similarity thresholds for fuzzy matching
- Add additional matching criteria
- Change output format or columns
- Process different file formats