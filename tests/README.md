# Tests Directory

This directory contains all tests for the drone metadata automation system.

## Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                   # Test configuration and fixtures
├── README.md                     # This file
└── ingestion/                    # Tests for data ingestion components
    ├── __init__.py              # Ingestion test package
    └── test_airdata_parser.py   # AirdataParser unit tests
```

## Running Tests

### Option 1: Using the Test Runner (Recommended)

From the project root directory:

```bash
# Run default test suite (AirdataParser tests)
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe run_tests.py

# Run all tests
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe run_tests.py --all

# Run only AirdataParser tests
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe run_tests.py --airdata

# List available test modules
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe run_tests.py --list
```

### Option 2: Direct Test Execution

```bash
# Run specific test file directly
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe tests/ingestion/test_airdata_parser.py

# Run with unittest module
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe -m unittest tests.ingestion.test_airdata_parser
```

## Test Categories

### Unit Tests
- **AirdataParser Tests** (`test_airdata_parser.py`): Tests for CSV parsing, data validation, and mixed delimiter format handling

### Integration Tests
- Comprehensive end-to-end testing of parser functionality
- Real-world CSV file processing validation
- Performance and consistency checks

## Test Data

Tests use the following sample data:
- **CSV File**: `C:\Users\donal\Downloads\aug_2025\8D\JPG-Aug-27th-2025-12-00PM-Flight-Airdata.csv`
- **Format**: Mixed pipe-comma delimiter format (line_number|csv_data)
- **Contents**: ~2,500 telemetry points from a 4-minute drone flight

## Test Coverage

Current tests cover:
- ✅ Mixed delimiter CSV format parsing
- ✅ Flight data extraction and validation
- ✅ Flight metrics calculation
- ✅ Media events detection
- ✅ Flight phases analysis
- ✅ Telemetry consistency validation
- ✅ Error handling for invalid files
- ✅ CSV structure validation

## Adding New Tests

When adding new test files:

1. Create test files with `test_` prefix
2. Use unittest.TestCase as base class
3. Add appropriate docstrings
4. Update this README
5. Update the test runner if needed

## Recent Changes

- **Fixed**: AirdataParser now handles mixed pipe-comma delimiter format
- **Added**: Comprehensive test coverage for the parser fix
- **Improved**: Better error handling and validation