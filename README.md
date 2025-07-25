# **FieldMuseum-EMU-Master Spreadsheet & Validation Information**

This repository contains scripts for managing and validating collector records for the Field Museum's EMU database. Below is an overview of the workflow and requirements for each script.
---

## **1. Creating the Master Spreadsheet (`Master_Collector_main.py`)**
Generates the initial master collector spreadsheet by combining data from multiple sources.

### **Required Input Files:**
- `countries_combined.csv` (Located in `EMU_Combined_Sheets`; not in this repo due to size. Available in Google Drive: **2025 > testing > Round2**)
- `HUH_Combined.csv` (Located in `HUH` folder)
- `Botany_Parties_Author_names.xlsx` (Located in `BotanyParties` folder)

### **Output:**
- `Master_Collector(Original).csv` (Pre-generated; only re-run if new EMU data or `countries_combined` updates are available.)

## **2. Validating Spreadsheets & New Collector Records (`Master_Validator.py`)**
Checks new collector records (from Max) against the master sheet for consistency.

### **Required Input Files:**
- `Master_Collector(newmain).csv` (Copy of `Master_Collector(Original)`, located in `Validations` folder)
- `Example CSV for Max - Sheet1.csv` (Sample format for Max's input, in `Examples` folder)

### **How to Run:**
- Replace `Example CSV for Max - Sheet1.csv` with new Max files **OR** modify the file path in the script (see comments for details).

### **Output:**
Two validation reports per input file:
1. `validation_results(Primary).csv` (Primary collector checks)
2. `validation_results(Secondary).csv` (Co-collector checks)

## **3. Updating the Master Spreadsheet (`UpdateMaster.py`)**
Incorporates validated records from Max into the master sheet.

### **Required Input Files:**
- `Master_Collector(newmain).csv` (Updated incrementally)
- `Example CSV for Max - Sheet1.csv` (New records from Max, located in `Examples` folder)
- `Test_Validated.csv` (Sample validated data, in `Examples` folder)

### **How to Run:**
- As with `Master_Validator.py`, replace the example file or adjust the path.

### **Output:**
- Modifies `Master_Collector(newmain).csv` in place (no new file created).

## **4. [IN PROGRESS] Cleaning Dates & Transcription Additions (`Transcription_Validation.py`)**
**Work in Progress** – Cleans date formats and enriches transcribed records.

### **Current Requirements:**
- `Example CSV for Max - Sheet1.csv`  
- `Master_Collector(newmain).csv`

### **Current Outputs:**
1. `cleaned_dates.csv` (Adds cleaned date columns; partial formatting support).  
2. User-named file (Adds `collector_irn`, `collector_id`, and cleaned dates to the input sheet).

## **General Notes**
- **File Paths:** Scripts assume files are in specified folders. Adjust paths in code if needed.  
- **Google Drive Access:** `countries_combined.csv` is available in **Google Drive > 2025 > testing > Round2**.  
- **Backups:** Retain copies of `Master_Collector(Original).csv` before running updates in case of any errors.  

For any questions or issues, email Alex Wcislo at [alexwcislo1@gmail.com] or [awcislo@fieldmuseum.org] (short-term).  