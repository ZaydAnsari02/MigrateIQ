# MigrateIQ - BI Report Comparison Tool

A Python-based CLI tool that compares Tableau workbooks (.twbx) and Power BI reports (.pbix) to validate that they represent the same data, semantic model, and relationships.

## Features

- **Data Comparison**: Compare table names, columns, row counts, data types across TWBX and PBIX files
- **Semantic Model Comparison**: Validate measures, calculated fields, and table structures
- **Relationships Validation**: Check relationships (cardinality, foreign keys) between tables
- **Structured Output**: Save detailed comparison results to JSON format
- **Tolerance-Based Validation**: Allows for &lt;0.5% numeric differences (configurable)
- **Comprehensive Logging**: Detailed logging with optional verbose mode
- **Unit-Testable Design**: Modular architecture separating parsing, comparison, and output logic

## Installation

### Requirements
- Python 3.10 or higher
- pip package manager

### Setup

1. Clone or download the repository:
```bash
cd MigrateIQ
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python compare_reports.py --twbx path/to/tableau_file.twbx --pbix path/to/powerbi_file.pbix
```

### with Custom Output Path

```bash
python compare_reports.py --twbx file.twbx --pbix file.pbix --output /path/to/result.json
```

### Verbose Mode (Detailed Logging)

```bash
python compare_reports.py --twbx file.twbx --pbix file.pbix --verbose
```

### CLI Options

```
--twbx PATH      (required) Path to Tableau Packaged Workbook (.twbx) file
--pbix PATH      (required) Path to Power BI Desktop (.pbix) file
--output PATH    (optional) Path to save JSON result (default: comparison_result.json)
--verbose        (optional) Enable detailed per-column logging
```

### Exit Codes

- `0`: Comparison completed successfully with PASS result
- `1`: Comparison completed with FAIL result or error occurred

## Output Format

The tool generates a structured JSON file with the following format:

```json
{
  "comparison_id": "<uuid>",
  "timestamp": "<ISO 8601>",
  "inputs": {
    "twbx_file": "<filename>",
    "pbix_file": "<filename>"
  },
  "overall_result": "PASS|FAIL",
  "categories": {
    "data": {
      "result": "PASS|FAIL",
      "tolerance_threshold_pct": 0.5,
      "tables_compared": <int>,
      "details": [
        {
          "table_name": "<name>",
          "result": "PASS|FAIL",
          "row_count_twbx": <int>,
          "row_count_pbix": <int>,
          "row_count_diff_pct": <float>,
          "columns_matched": ["col1", "col2"],
          "columns_missing_in_pbix": [],
          "columns_missing_in_twbx": [],
          "column_type_mismatches": [],
          "failure_reasons": []
        }
      ]
    },
    "semantic_model": {
      "result": "PASS|FAIL",
      "measures_compared": <int>,
      "details": {
        "measures_matched": [],
        "measures_missing_in_pbix": [],
        "measures_missing_in_twbx": [],
        "expression_mismatches": [],
        "data_type_mismatches": [],
        "failure_reasons": []
      }
    },
    "relationships": {
      "result": "PASS|FAIL",
      "relationships_compared": <int>,
      "details": {
        "relationships_matched": [],
        "relationships_missing_in_pbix": [],
        "relationships_missing_in_twbx": [],
        "cardinality_mismatches": [],
        "failure_reasons": []
      }
    }
  },
  "summary": {
    "total_failures": <int>,
    "failure_categories": ["data", "relationships"],
    "notes": "<summary notes>"
  }
}
```

## What Gets Compared

### 1. Data Layer
- **Table Names**: Case-insensitive comparison
- **Column Names**: Per-table column matching
- **Row Counts**: With configurable tolerance (default 0.5%)
- **Column Data Types**: Type compatibility checking
- **Value Distributions**: Min, max, null count, distinct count per column

### 2. Semantic Model
- **Measures**: DAX/calculated field expressions and data types
- **Calculated Columns**: Column definitions
- **Table Display Names**: Normalized names vs display names
- **Column Data Types**: Aggregation types and properties

### 3. Relationships
- **Relationship Pairs**: From/To table and column mappings
- **Cardinality**: one-to-many, many-to-one, many-to-many
- **Active vs Inactive**: Relationship status
- **Cross-Filter Direction**: Filter propagation direction

## Pass/Fail Logic

**Result is PASS when:**
- All numeric metrics are within &lt;0.5% tolerance
- All structural elements (tables, columns, measures) match between files
- All relationships match in terms of tables and cardinality

**Result is FAIL when:**
- Any structural element is missing or mismatched
- Any numeric difference exceeds 0.5% tolerance
- Any relationship cardinality differs

**Overall Result:**
- PASS: All three categories (data, semantic_model, relationships) PASS
- FAIL: Any one category has a FAIL

## Project Structure

```
MigrateIQ/
├── compare_reports.py          # CLI entry point
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── parsers/
│   ├── __init__.py
│   ├── twbx_parser.py          # Tableau TWBX extraction logic
│   └── pbix_parser.py          # Power BI PBIX extraction logic
├── comparators/
│   ├── __init__.py
│   ├── data_comparator.py      # Data table comparison
│   ├── model_comparator.py     # Semantic model comparison
│   └── relationship_comparator.py  # Relationship comparison
├── output/
│   ├── __init__.py
│   └── result_builder.py       # JSON result building and IO
└── tests/
    ├── __init__.py
    ├── test_data_comparator.py
    ├── test_model_comparator.py
    ├── test_relationship_comparator.py
    └── test_result_builder.py
```

## Running Tests

Run all unit tests:
```bash
python -m pytest tests/ -v
```

Run specific test file:
```bash
python -m pytest tests/test_data_comparator.py -v
```

Run tests with coverage:
```bash
python -m pytest tests/ --cov=comparators --cov=parsers --cov=output
```

## Implementation Notes

### Data Extraction

**TWBX Files:**
- Extracts from `.hyper` Hyper Database files (if available) using `tableauhyperapi`
- Falls back to CSV data extracts embedded in the workbook
- Parses `Workbook.xml` for datasources, calculated fields, and relationships

**PBIX Files:**
- Parses the embedded data model from `DataModel` or JSON files
- Extracts table schemas and column definitions
- Extracts DAX measures and relationships from model metadata
- Note: Actual data row extraction from PBIX requires decompressing the VertiPaq model (not fully implemented in v1)

### Tolerance Handling

Default tolerance is 0.5% for numeric comparisons:
```python
difference_pct = abs(twbx_value - pbix_value) / twbx_value * 100
passes = difference_pct < 0.5
```

### Case Sensitivity

- Table names and column names are compared case-insensitively
- Measure/field names are compared case-insensitively
- Data types and expressions are compared as-is

## Limitations

1. **PBIX Data Extraction**: Current version extracts column schemas but not actual data rows from PBIX files. The VertiPaq model decompression is complex and would require additional dependencies.

2. **Complex Relationships**: Many-to-many relationships with bridge tables may not be fully detected.

3. **Custom Calculations**: Complex nested DAX expressions may not be fully parsed for detailed comparison.

4. **Performance**: Large files (>500MB) may take significant time to extract and compare.

## Future Enhancements

- [ ] Full data row extraction from PBIX VertiPaq model
- [ ] DAX expression normalization for better matching
- [ ] Configurable tolerance thresholds
- [ ] HTML and CSV report generation
- [ ] Incremental comparison for partial file updates
- [ ] Parallel processing for large files
- [ ] Integration with CI/CD pipelines

## Troubleshooting

### "TWBX file not found"
- Verify the file path is correct
- Ensure you have read permissions on the file

### "Could not parse DataModel"
- The PBIX file may be corrupted or from an older Power BI version
- Try rebuilding the PBIX file in Power BI Desktop

### Memory issues with large files
- Reduce verbose logging
- Process files in batches
- Increase system RAM

### No data extracted from TWBX
- The TWBX may not have embedded Hyper extracts
- Check if CSV data sources are embedded instead
- Ensure the TWBX was created with modern Tableau versions

## Error Handling

The tool provides clear error messages for:
- Missing or invalid input files
- Corrupt file archives
- Parsing errors in XML/JSON
- File permission issues
- Out of memory conditions

All errors are logged with timestamps for debugging.

## Contributing

When contributing improvements:
1. Maintain the modular structure (parsers, comparators, output separate)
2. Add unit tests for new comparison logic
3. Follow PEP 8 style guide
4. Document complex parsing logic with comments
5. Update this README with new features

## License

This tool is provided as-is for BI migration automation purposes.

## Support

For issues or questions:
1. Check this README and the code docstrings
2. Review test cases for usage examples
3. Check log output with `--verbose` flag for detailed error messages
4. Review the generated JSON output structure
