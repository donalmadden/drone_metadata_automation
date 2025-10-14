# Drone Metadata Automation System
## Project Architecture & Implementation Plan

**Project Name**: `drone-metadata-automation`  
**Version**: 1.0.0  
**Created**: October 8, 2025  
**Updated**: October 14, 2025 (Phase 1 Complete)  
**Purpose**: Automated metadata extraction and annotation generation for drone inspection workflows

---

## Overview

This system automates the metadata extraction and annotation process by leveraging multiple data sources:

1. **Airdata CSV files** - Flight telemetry (48+ fields, 10Hz sampling)
2. **🆕 MP4 drone videos** - Comprehensive video metadata extraction (Phase 1)
3. **🆕 DJI-specific metadata** - GPS, technical specs, mission data (Phase 1)
4. **SRT files** - Frame-by-frame camera settings and GPS data
5. **Flight record TXT files** - Flight logs and events
6. **Media files (DJI)** - Photos/videos with EXIF metadata
7. **Directory structure** - Bay/location identification from folder naming

The system produces standardized metadata output compatible with existing annotation formats while reducing manual effort by 75-85%. **Phase 1** adds comprehensive video processing with professional output generation.

---

## Data Sources Analysis

### 1. Airdata CSV Files
```csv
time(millisecond), datetime(utc), latitude, longitude, height_above_takeoff(feet),
speed(mph), distance(feet), battery_percent, compass_heading(degrees),
isPhoto, isVideo, gimbal_heading(degrees), flycState, message
```
- **Sampling Rate**: 10Hz (100ms intervals)
- **Content**: Complete flight telemetry
- **Usage**: Primary source for flight metrics, timing, GPS, equipment status

### 2. SRT Subtitle Files
```
[iso : 200] [shutter : 1/800.0] [fnum : 280] [ev : 0.7] [ct : 5500] 
[color_md : default] [focal_len : 240] [latitude: 46.013268] 
[longitude: 13.250646] [altitude: 1.400000]
```
- **Sampling Rate**: 25Hz (40ms intervals)
- **Content**: Camera settings, GPS per video frame
- **Usage**: Frame-accurate metadata, camera parameter analysis

### 3. Directory Structure
```
aug_2025/
├── 8B-7F/           # Bay identifier
├── 8D/              # Bay identifier  
├── 6E-7C/angles/    # Bay + inspection type
└── 6F-7B/angles/    # Bay + inspection type
```
- **Content**: Location and inspection type classification
- **Usage**: Automated bay identification and inspection categorization

### 4. Media Files
- **DNG/JPG**: Photos with EXIF GPS and camera settings
- **MP4**: Videos with associated SRT metadata
- **Content**: Visual data with embedded metadata
- **Usage**: Media-specific metadata extraction and validation

---

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Data Ingestion Layer                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  CSV Parser  │  🆕 Video Parser  │  SRT Parser  │  EXIF Reader  │  File Scanner │
│              │  (FFmpeg/Hachoir) │              │               │               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Data Processing Engine                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Flight Analysis │ 🆕 Video Analysis │ GIS Mapping │ Pattern Recognition │ QA   │
│                 │ Mission Classify  │             │                     │      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         🆕 Professional Output Generation                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Markdown Gen │ Thumbnail Gen │ CSV Exporter │ Index Builder │ Template Engine │
│ (.MP4.md)    │ (Phase 2)     │ (Semantic)   │ (Dataset)     │                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Language**: Python 3.11+
- **Data Processing**: pandas, numpy, scipy
- **🆕 Video Metadata**: ffmpeg-python, hachoir, pymediainfo, exifread
- **🆕 Output Generation**: jinja2 (templates), pillow (thumbnails)
- **GIS Operations**: geopandas, shapely, folium
- **Time Series**: pytz, dateutil
- **Machine Learning**: scikit-learn (pattern recognition)
- **Database**: SQLite (development) / PostgreSQL (production)
- **API Framework**: FastAPI
- **Frontend**: Streamlit (rapid prototyping)
- **Testing**: pytest, pytest-cov
- **Packaging**: poetry

### 🆕 Phase 1 Additions
- **VideoMetadataParser**: Multi-library video analysis (FFmpeg, Hachoir, MediaInfo)
- **Enhanced Models**: VideoMetadata, TechnicalSpecs, GPSData, MissionData
- **Formatter System**: 4 professional output formatters
- **Mission Classification**: Intelligent video categorization

---

## Implementation Modules

### 1. Data Ingestion (`ingestion/`)

#### `airdata_parser.py`
```python
class AirdataParser:
    def parse_csv(self, file_path: str) -> FlightData
    def extract_flight_metrics(self, data: pd.DataFrame) -> FlightMetrics
    def get_media_timestamps(self, data: pd.DataFrame) -> List[MediaEvent]
    def analyze_flight_phases(self, data: pd.DataFrame) -> FlightPhases
```

#### `srt_parser.py`
```python
class SRTParser:
    def parse_srt(self, file_path: str) -> List[SRTFrame]
    def extract_camera_settings(self, srt_data: List[SRTFrame]) -> CameraProfile
    def correlate_with_video(self, srt_data: List[SRTFrame], video_path: str) -> VideoMetadata
```

#### `media_processor.py`
```python
class MediaProcessor:
    def extract_exif(self, image_path: str) -> EXIFData
    def process_video_metadata(self, video_path: str) -> VideoInfo
    def correlate_media_with_telemetry(self, media_files: List[str], telemetry: FlightData) -> MediaCorrelation
```

#### `directory_scanner.py`
```python
class DirectoryScanner:
    def scan_flight_directory(self, path: str) -> FlightDataset
    def identify_bay_from_path(self, path: str) -> BayIdentifier
    def categorize_inspection_type(self, path: str) -> InspectionType
    def discover_data_sources(self, path: str) -> DataSources
```

### 2. Data Processing (`processing/`)

#### `flight_analyzer.py`
```python
class FlightAnalyzer:
    def calculate_duration(self, telemetry: FlightData) -> timedelta
    def analyze_altitude_profile(self, telemetry: FlightData) -> AltitudeAnalysis
    def compute_flight_statistics(self, telemetry: FlightData) -> FlightStats
    def detect_anomalies(self, telemetry: FlightData) -> List[Anomaly]
```

#### `gis_processor.py`
```python
class GISProcessor:
    def map_coordinates_to_bays(self, coords: List[GPSPoint], bay_db: BayDatabase) -> BayMapping
    def analyze_flight_path(self, coords: List[GPSPoint]) -> FlightPath
    def calculate_coverage_area(self, path: FlightPath) -> CoverageAnalysis
    def generate_flight_map(self, data: FlightData) -> FlightMap
```

#### `pattern_recognizer.py`
```python
class PatternRecognizer:
    def classify_flight_pattern(self, path: FlightPath) -> FlightPattern
    def identify_inspection_type(self, pattern: FlightPattern, location: BayMapping) -> InspectionClassification
    def score_flight_quality(self, metrics: FlightStats) -> QualityScore
```

### 3. Metadata Generation (`generation/`)

#### `report_builder.py`
```python
class ReportBuilder:
    def generate_flight_report(self, analysis: FlightAnalysis) -> FlightReport
    def create_metadata_summary(self, dataset: FlightDataset) -> MetadataSummary
    def build_annotation_templates(self, data: ProcessedData) -> AnnotationTemplates
```

#### `export_formatter.py`
```python
class ExportFormatter:
    def format_as_csv(self, report: FlightReport) -> str
    def format_as_json(self, report: FlightReport) -> str
    def format_as_markdown(self, report: FlightReport) -> str
    def export_to_existing_format(self, data: ProcessedData) -> CompatibleFormat
```

### 4. Configuration (`config/`)

#### `bay_database.py`
```python
class BayDatabase:
    def load_bay_definitions(self, config_file: str) -> Dict[str, BayConfig]
    def get_bay_coordinates(self, bay_id: str) -> GPSBounds
    def classify_bay_type(self, bay_id: str) -> BayType
```

#### `inspection_templates.py`
```python
class InspectionTemplates:
    def get_template_for_type(self, inspection_type: InspectionType) -> AnnotationTemplate
    def customize_template(self, template: AnnotationTemplate, context: ProcessingContext) -> CustomTemplate
```

---

## Data Models

### Core Data Structures

```python
@dataclass
class FlightData:
    timestamp_start: datetime
    timestamp_end: datetime
    duration: timedelta
    telemetry: pd.DataFrame
    media_events: List[MediaEvent]
    flight_phases: FlightPhases

@dataclass
class FlightMetrics:
    max_altitude: float
    avg_altitude: float
    max_speed: float
    avg_speed: float
    total_distance: float
    battery_start: float
    battery_end: float
    gps_quality: float

@dataclass
class MediaEvent:
    timestamp: datetime
    event_type: str  # "photo" | "video_start" | "video_end"
    location: GPSPoint
    camera_settings: CameraSettings
    file_path: Optional[str]

@dataclass
class BayMapping:
    bay_id: str
    bay_name: str
    coordinates: GPSBounds
    inspection_type: InspectionType
    confidence_score: float

@dataclass
class FlightReport:
    flight_id: str
    bay_mapping: BayMapping
    flight_metrics: FlightMetrics
    inspection_classification: InspectionClassification
    media_summary: MediaSummary
    anomalies: List[Anomaly]
    quality_score: QualityScore
    automated_annotations: Dict[str, Any]
    human_verification_needed: List[str]
```

---

## Configuration Management

### Bay Database Configuration
```yaml
# config/bay_definitions.yaml
bays:
  "8B-7F":
    name: "Bay 8B-7F Primary Structure"
    type: "industrial_inspection"
    coordinates:
      center: [46.01326, 13.25064]
      bounds: [[46.0130, 13.2504], [46.0135, 13.2509]]
    inspection_types: ["overview", "detailed", "angles"]
    
  "8D":
    name: "Bay 8D Secondary Structure" 
    type: "infrastructure_survey"
    coordinates:
      center: [46.01340, 13.25080]
      bounds: [[46.0132, 13.2506], [46.0136, 13.2510]]
    inspection_types: ["survey", "angles"]
```

### Processing Configuration
```yaml
# config/processing_config.yaml
telemetry:
  sampling_rate: 10  # Hz
  altitude_units: "feet"
  speed_units: "mph"
  coordinate_precision: 7

quality_thresholds:
  min_gps_accuracy: 5  # satellites
  max_altitude_variance: 50  # feet
  min_battery_level: 20  # percent
  max_speed_for_inspection: 15  # mph

pattern_recognition:
  perimeter_detection:
    min_circuit_completion: 0.8
    max_altitude_variation: 30
  detail_inspection:
    min_hover_time: 2.0  # seconds
    max_movement_speed: 5  # mph
```

---

## Implementation Phases

### Phase 1: Core Data Processing (Weeks 1-3)
**Deliverables:**
- [x] Project structure and configuration
- [ ] Airdata CSV parser with full telemetry extraction
- [ ] SRT parser for camera metadata
- [ ] Basic directory scanning and file discovery
- [ ] Core data models and validation
- [ ] Unit tests for parsers

**Success Criteria:**
- Parse 100% of airdata CSV fields accurately
- Extract camera settings from SRT files with <1% error rate
- Automatically discover and categorize all file types

### Phase 2: GIS and Analysis (Weeks 4-6)
**Deliverables:**
- [ ] Bay mapping and coordinate correlation
- [ ] Flight path analysis and visualization
- [ ] Pattern recognition for inspection types
- [ ] Statistical analysis of flight metrics
- [ ] Anomaly detection algorithms

**Success Criteria:**
- Achieve >90% accuracy in bay identification
- Classify inspection types with >85% accuracy
- Generate meaningful flight quality scores

### Phase 3: Report Generation (Weeks 7-9)
**Deliverables:**
- [ ] Automated report generation
- [ ] Template-based annotation system
- [ ] Export compatibility with existing formats
- [ ] Web interface for verification and editing
- [ ] Batch processing capabilities

**Success Criteria:**
- Generate reports in <30 seconds per flight
- Achieve 75% reduction in manual annotation time
- Maintain 100% compatibility with existing workflows

### Phase 4: Production Integration (Weeks 10-12)
**Deliverables:**
- [ ] Production deployment scripts
- [ ] Monitoring and logging systems
- [ ] Performance optimization
- [ ] User training documentation
- [ ] Quality assurance framework

**Success Criteria:**
- Process 100+ flight datasets without manual intervention
- Achieve <5% error rate requiring human correction
- Deploy to production environment successfully

---

## Quality Assurance Framework

### Automated Validation
```python
class ValidationFramework:
    def validate_telemetry_consistency(self, data: FlightData) -> ValidationResult
    def check_coordinate_validity(self, coords: List[GPSPoint]) -> bool
    def verify_timestamp_sequence(self, timestamps: List[datetime]) -> bool
    def detect_data_anomalies(self, metrics: FlightMetrics) -> List[Anomaly]
```

### Human Verification Interface
- Interactive map showing flight path and detected bays
- Side-by-side comparison of automated vs manual annotations
- Confidence scoring for each automated classification
- Workflow for approving/rejecting automated annotations

### Performance Metrics
- **Processing Speed**: Target <30 seconds per flight
- **Accuracy Rate**: Target >90% for bay identification
- **Coverage**: Target 100% automation for high-confidence fields
- **Error Rate**: Target <5% requiring human correction

---

## Expected Outcomes

### Quantified Benefits
- **Time Savings**: 75-85% reduction in annotation time
- **Cost Reduction**: $300-450 → $60-120 per 58-video dataset
- **Scalability**: Enable processing of 1000+ video datasets
- **Accuracy**: Consistent metadata quality without human fatigue
- **Standardization**: Uniform annotation format and quality

### Technical Achievements
- Fully automated telemetry processing pipeline
- Real-time flight path visualization
- Intelligent bay identification and inspection classification
- Quality-assured metadata generation
- Seamless integration with existing workflows

---

## Getting Started

### Prerequisites
- Python 3.11+
- Git
- 8GB RAM minimum (16GB recommended for large datasets)
- 50GB free disk space for processing cache

### Installation
```bash
# Clone repository
git clone https://github.com/your-org/drone-metadata-automation.git
cd drone-metadata-automation

# Install dependencies
poetry install

# Configure environment
cp config/config.template.yaml config/config.yaml
# Edit config.yaml with your specific settings

# Run initial setup
python -m setup.init_database
python -m setup.validate_config
```

### Quick Start
```bash
# Process a single flight directory
python -m drone_metadata process --input "C:\path\to\flight\data" --output "C:\path\to\results"

# Batch process multiple flights
python -m drone_metadata batch --input-dir "C:\path\to\aug_2025" --output-dir "C:\path\to\results"

# Launch web interface
python -m drone_metadata serve --port 8080
```

---

**Next Steps**: Ready to begin implementation with Phase 1 development. Priority focus on airdata CSV parsing and SRT metadata extraction to establish core processing foundation.
