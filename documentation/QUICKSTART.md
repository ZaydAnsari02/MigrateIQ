# Quick Start Guide

## 5-Minute Setup

### 1. Install Python Dependencies
```bash
cd MigrateIQ
pip install -r requirements.txt
```

### 2. Run Your First Comparison
```bash
python compare_reports.py --twbx your_report.twbx --pbix your_report.pbix
```

### 3. Check Results
Open `comparison_result.json` in your editor to see detailed comparison results.

## Expected Output

The tool will:
1. **Extract** data, models, and relationships from both files
2. **Compare** them across three categories: data, semantic model, relationships
3. **Generate** a JSON report with detailed findings
4. **Print** a summary to the console

Example console output:
```
======================================================================
COMPARISON RESULT SUMMARY
======================================================================

Comparison ID: 550e8400-e29b-41d4-a716-446655440000
Timestamp: 2024-01-15T10:30:45.123456Z
TWBX File: sales_dashboard.twbx
PBIX File: sales_dashboard.pbix

OVERALL RESULT: FAIL

--- DATA COMPARISON ---
Result: PASS
Tables Compared: 3

--- SEMANTIC MODEL COMPARISON ---
Result: FAIL
Measures Compared: 4
Issues: 2
  - Measure 'Average Order Value' missing in PBIX
  - Measure 'Year-to-Date Sales' missing in PBIX

--- RELATIONSHIPS COMPARISON ---
Result: FAIL
Relationships Compared: 3
Issues: 1
  - Relationship missing in PBIX: Customers[CountryID] -> Countries[CountryID]

--- SUMMARY ---
Total Failures: 2
Failure Categories: semantic_model, relationships
Notes: 2 measure(s) have semantic model mismatches; 1 relationship issue(s) detected

======================================================================
```

## Understanding Results

### PASS Means:
✅ All data rows match (within 0.5% tolerance)
✅ All table/column names and types match
✅ All measures and calculated fields match
✅ All relationships (foreign keys) match

### FAIL Means:
❌ Missing or extra tables/columns
❌ Data row count differs >0.5%
❌ Data types don't match
❌ Measures (DAX expressions) differ
❌ Relationships missing or cardinality mismatch

## Common Scenarios

### Scenario 1: Reports are Identical
```bash
python compare_reports.py --twbx ref.twbx --pbix migrated.pbix

# Result: PASS
# The migration is complete and accurate
```

### Scenario 2: Measures Missing in Migration
```bash
# Result: FAIL (semantic_model)
# Add missing measures to the PBIX file
# Re-run comparison to verify
```

### Scenario 3: Row Count Mismatch
```bash
# Result: FAIL (data)
# 1000 TWBX rows vs 994 PBIX rows = 0.6% difference > 0.5% tolerance
# Investigate data source filters in PBIX
```

### Scenario 4: Column Type Mismatch
```bash
# Result: FAIL (data)
# Column 'SalesAmount' is decimal in TWBX but string in PBIX
# Fix data types in PBIX model
```

## Working with Results

### View Full Details
```bash
# Open the JSON file
cat comparison_result.json

# Or use a JSON viewer (VS Code, online tools)
```

### Verbose Mode for Debugging
```bash
python compare_reports.py \
  --twbx report.twbx \
  --pbix report.pbix \
  --verbose

# Prints detailed per-column information to console
```

### Save to Custom Location
```bash
python compare_reports.py \
  --twbx report.twbx \
  --pbix report.pbix \
  --output /path/to/my_results/report_v1.json
```

## Interpreting the JSON

The output JSON has this structure:

```json
{
  "overall_result": "PASS" or "FAIL",
  
  "categories": {
    "data": { /* Table/column/row count comparisons */ },
    "semantic_model": { /* Measures and calculated fields */ },
    "relationships": { /* Foreign key relationships */ }
  },
  
  "summary": {
    "total_failures": <number>,
    "failure_categories": ["data", "relationships"]
  }
}
```

## Common Issues & Solutions

### Issue: "File not found"
```bash
# Make sure file paths are correct (relative or absolute)
python compare_reports.py --twbx ./reports/file.twbx --pbix ./reports/file.pbix
```

### Issue: "tableauhyperapi not available"
```bash
# Try installing and retrying
pip install --upgrade tableauhyperapi

# If that doesn't work, the tool will fall back to CSV extraction
```

### Issue: "Memory error with large files"
```bash
# Reduce verbose logging
python compare_reports.py --twbx big.twbx --pbix big.pbix
# (Don't use --verbose)

# Or process files in batches
```

### Issue: "No measures found"
```bash
# Some TWBX/PBIX files may not have embedded measures
# The tool will find them if they exist
# Check the generated JSON for "measures_compared": 0
```

## Next Steps

1. **Review the README.md** for detailed documentation
2. **Check SETUP.md** for advanced configuration
3. **Read example_usage.py** for programmatic integration
4. **Run unit tests** to validate installation:
   ```bash
   python -m pytest tests/ -v
   ```

## Tips for Best Results

✅ **Do:**
- Use original source files (before any modifications)
- Ensure both files are complete and not corrupted
- Run comparison after completing migration
- Save results for audit trail
- Use verbose mode if results are unexpected

❌ **Don't:**
- Modify files during comparison
- Interrupt the tool during processing
- Delete temporary files until comparison completes
- Expect 100% match for filtered/transformed data

## File Size Guidelines

| File Size | Expected Time | Recommended |
|-----------|---------------|------------|
| < 10 MB | < 10 sec | Yes |
| 10-100 MB | 30 sec - 2 min | Yes |
| 100-500 MB | 2-5 min | Careful |
| > 500 MB | 5+ min | Requires resources |

## Support

For detailed help:
```bash
python compare_reports.py --help
```

For issues, check:
1. Run with `--verbose` for detailed output
2. Search the README.md
3. Review sample_comparison_result.json for output structure
4. Check test files for working examples

## What Gets Checked

**Data Layer:**
- Table names match
- Column names match per table
- Column count matches
- Row count within 0.5%
- Data types match

**Semantic Model:**
- Measure names
- DAX expressions
- Data types
- Calculated columns

**Relationships:**
- Table pairs match
- Column pairs match
- Cardinality type (1:1, 1:M, M:M)
- Active/inactive status

## Exit Status

```bash
echo $?  # Shows exit code after running

# 0 = Comparison PASSED
# 1 = Comparison FAILED or error occurred
```

Useful for scripting and CI/CD:
```bash
python compare_reports.py --twbx file.twbx --pbix file.pbix
if [ $? -eq 0 ]; then
    echo "Migration successful!"
else
    echo "Issues found - review comparison_result.json"
fi
```

---

**Ready to compare?**

```bash
python compare_reports.py --twbx your_tableau.twbx --pbix your_powerbi.pbix
```
