# Tests Directory

This directory contains all tests for the drone metadata automation system.

## Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                   # Test configuration and fixtures
├── README.md                     # This file
├── ingestion/                    # Tests for data ingestion components
│   ├── __init__.py              # Ingestion test package
│   ├── test_airdata_parser.py   # AirdataParser unit tests
│   └── test_video_metadata_parser.py # VideoMetadataParser tests
├── phase2/                       # ✅ NEW - Phase 2 specific tests
│   ├── test_phase2_batch_processing.py
│   ├── test_phase2_mission_classifier.py
│   ├── test_phase2_semantic_model.py
│   └── test_phase2_thumbnails.py
└── test_models.py                # Model class tests
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
- **VideoMetadataParser Tests** (`test_video_metadata_parser.py`): Tests for video metadata extraction, FFmpeg integration, and GPS data parsing
- **Model Tests** (`test_models.py`): Tests for data model classes and validation

### Phase 2 Integration Tests
- **Batch Processing Tests** (`test_phase2_batch_processing.py`): Multi-video processing with organized output
- **Mission Classification Tests** (`test_phase2_mission_classifier.py`): BOX/SAFETY classification logic and confidence scoring
- **Semantic Model Tests** (`test_phase2_semantic_model.py`): Complete 7-table CSV generation and validation
- **Thumbnail Tests** (`test_phase2_thumbnails.py`): Real FFmpeg thumbnail generation and organization

### Integration Tests
- Comprehensive end-to-end testing of complete processing pipeline
- Real-world drone video processing validation
- Performance benchmarking and consistency checks
- Mission-based directory organization validation

## Test Data

Tests use the following sample data:
- **CSV File**: `C:\Users\donal\Downloads\aug_2025\8D\JPG-Aug-27th-2025-12-00PM-Flight-Airdata.csv`
- **Format**: Mixed pipe-comma delimiter format (line_number|csv_data)
- **Contents**: ~2,500 telemetry points from a 4-minute drone flight

## Test Coverage

### Phase 1 & 2 Combined Coverage:

**Core Functionality (Phase 1)**:
- ✅ Mixed delimiter CSV format parsing
- ✅ Flight data extraction and validation
- ✅ Flight metrics calculation
- ✅ Media events detection
- ✅ Flight phases analysis
- ✅ Telemetry consistency validation
- ✅ Video metadata extraction (FFmpeg, Hachoir, MediaInfo)
- ✅ GPS coordinate parsing from video metadata
- ✅ DJI-specific metadata parsing

**Phase 2 Enhanced Features**:
- ✅ Real FFmpeg thumbnail generation from video frames
- ✅ Intelligent mission classification (BOX/SAFETY) with confidence scoring
- ✅ Complete semantic model export (7 CSV dimension tables)
- ✅ Mission-based directory organization with nested structure
- ✅ Batch processing with centralized output management
- ✅ CLI integration for production-ready video processing
- ✅ Error handling for video processing failures
- ✅ File organization and duplicate prevention

## Adding New Tests

When adding new test files:

1. Create test files with `test_` prefix
2. Use unittest.TestCase as base class
3. Add appropriate docstrings
4. Update this README
5. Update the test runner if needed

## Recent Changes

### Phase 2 Completion (October 2025)
- **Added**: Complete Phase 2 test suite for all new functionality
- **Added**: Real FFmpeg thumbnail generation testing
- **Added**: Mission classification testing with confidence validation
- **Added**: Semantic model testing for 7-table CSV generation
- **Added**: Batch processing integration tests
- **Enhanced**: Directory organization and file management testing
- **Enhanced**: CLI command integration testing

### Phase 1 Foundation
- **Fixed**: AirdataParser handles mixed pipe-comma delimiter format
- **Added**: Comprehensive video metadata extraction testing
- **Added**: Model validation and GPS parsing tests
- **Improved**: Error handling and validation throughout
