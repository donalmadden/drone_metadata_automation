# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Environment Setup
Use the conda environment for development:
```powershell
# Activate the conda environment
conda activate drone_metadata_parser

# Or use full path on Windows
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe
```

### Testing Commands
```powershell
# Run all tests (recommended)
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe -m pytest tests/ -v

# Using the test runner script
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe run_tests.py --all

# Run specific test modules
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe -m pytest tests/test_models.py -v
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe -m pytest tests/ingestion/test_video_metadata_parser.py -v

# Run with coverage
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe -m pytest tests/ --cov=drone_metadata

# AirdataParser tests only
C:\users\donal\.conda\envs\drone_metadata_parser\python.exe run_tests.py --airdata
```

### Development Environment 
```powershell
# Install dependencies with Poetry (if available)
poetry install

# Or install with pip
pip install -e .

# Verify installation
python -c "import drone_metadata; print(drone_metadata.__version__)"
```

### Running Demos
```powershell
# Legacy demo (synthetic data)
python demo.py

# Phase 1 video processing demo (recommended for real drone videos)
python demo_video_processing.py

# CLI demo
drone-metadata demo
```

### CLI Usage
```powershell
# Process a single flight directory
drone-metadata process "C:\path\to\flight\data" --format json

# Batch process multiple flights
drone-metadata batch "C:\Users\donal\Downloads\aug_2025" --output-dir reports

# Scan directory without processing
drone-metadata scan "C:\path\to\flight\data"
```

### Code Quality
```powershell
# Format code (if available)
poetry run black drone_metadata

# Type checking (if mypy is configured)
poetry run mypy drone_metadata
```

## Architecture Overview

### System Design
This is a **drone metadata automation system** that processes multiple data sources to generate comprehensive flight reports, reducing manual annotation time by 75-85%.

### Core Components

#### Data Ingestion Layer (`drone_metadata/ingestion/`)
- **AirdataParser**: Processes CSV telemetry files with 48+ fields at 10Hz sampling
- **VideoMetadataParser**: **NEW** - Extracts comprehensive metadata from MP4 videos using FFmpeg, Hachoir, MediaInfo
- **SRTParser**: Processes subtitle files with frame-accurate GPS and camera settings (25Hz)
- **DirectoryScanner**: Discovers and categorizes data sources from directory structure

#### Data Processing (`drone_metadata/processor.py`)
- **DroneMetadataProcessor**: Main orchestrator combining all data sources
- Performs flight analysis, GIS mapping, quality assessment, anomaly detection
- Bay identification from directory structure (8B-7F, 8D, 6E-7C/angles patterns)

#### Output Generation (`drone_metadata/formatters/`) **NEW**
- **MarkdownFormatter**: Generates individual `.MP4.md` files with comprehensive metadata
- **SemanticModelExporter**: Creates normalized CSV tables (flight_facts, dimension tables)
- **ThumbnailGenerator**: Video frame extraction (Phase 2)
- **DatasetIndexGenerator**: Master documentation and index files

#### Data Models (`drone_metadata/models.py`)
Core models include `FlightReport`, `FlightData`, `FlightMetrics`, `QualityScore`, and **NEW** video-specific models:
- `VideoMetadata`, `TechnicalSpecs`, `GPSData`, `MissionData`

### Data Sources
The system processes:
1. **Airdata CSV files** - Flight telemetry (48+ fields, 10Hz)
2. **MP4 drone videos** - Comprehensive metadata extraction **NEW**  
3. **SRT files** - Frame-by-frame camera settings and GPS (25Hz)
4. **Directory structure** - Bay/location identification from folder naming
5. **Media files** - Photos/videos with EXIF metadata

### Development Phases
- **Phase 1 ✅ COMPLETED**: Core Integration Architecture with video metadata extraction
- **Phase 2 (Next)**: Enhanced processing features, thumbnail generation, mission classification
- **Phase 3 (Planned)**: Production features, GIS integration, ML classification

### Key Processing Pipeline
```
Input Data → Directory Scanner → Multi-Parser Ingestion → 
Flight Analysis → Quality Assessment → Professional Output Generation →
Structured Reports (JSON/CSV/Markdown)
```

### Windows-Specific Notes
- Redis runs natively in Windows (per user rules)
- Use PowerShell commands and Windows-style file paths
- Conda environment path: `C:\users\donal\.conda\envs\drone_metadata_parser\`
- Poetry may not be fully configured; use conda/pip for dependencies

### Important Files
- `pyproject.toml`: Project dependencies and configuration
- `PROJECT_ARCHITECTURE.md`: Detailed technical architecture
- `DEVELOPMENT_PLAN.md`: Phase-by-phase implementation roadmap  
- `PHASE_1_COMPLETE.md`: Phase 1 completion summary
- `run_tests.py`: Comprehensive test runner with multiple options

### Expected Directory Structure for Processing
```
flight_directory/
├── 8B-7F/                     # Bay identifier
│   ├── *.csv                  # Airdata telemetry files  
│   ├── *.srt                  # Video subtitle files
│   ├── *.mp4, *.jpg, *.dng    # Media files
│   └── angles/                # Inspection type subdirectory
```

### Output Structure (Phase 1)
```
output/
├── individual_video_docs/     # .MP4.md files
├── semantic_model/           # Normalized CSV tables
├── thumbnails/               # Video thumbnails (Phase 2)
└── dataset_index/           # Master documentation
```