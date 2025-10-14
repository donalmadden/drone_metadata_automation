#!/usr/bin/env python3
"""
Drone Video Metadata Processing Demo
===================================

This demo script showcases the Phase 1 video metadata processing capabilities.
It processes drone videos from your test data and generates all output formats.

Usage:
    python demo_video_processing.py

Or with Poetry (if environment is set up):
    poetry run python demo_video_processing.py

Or with your conda environment:
    C:\\users\\donal\\.conda\\envs\\drone_metadata_parser\\python.exe demo_video_processing.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from drone_metadata.ingestion.video_metadata_parser import VideoMetadataParser
from drone_metadata.models import (
    VideoMetadata, TechnicalSpecs, GPSData, MissionData, MissionType,
    VideoAnalysisResult, VideoProcessingBatch
)
from drone_metadata.formatters import (
    FormatterConfig, MarkdownFormatter, ThumbnailGenerator, 
    SemanticModelExporter, DatasetIndexGenerator
)


def process_videos_demo():
    """Main demo function showing complete video processing workflow."""
    print("🚁 DRONE VIDEO METADATA PROCESSING DEMO")
    print("=" * 60)
    
    # Configuration
    test_data_dir = Path("C:/Users/donal/Downloads/aug_2025/8D")
    output_dir = Path("demo_output")
    
    # Create output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"📁 Output directory: {output_dir.absolute()}")
    print(f"📹 Test data directory: {test_data_dir}")
    print()
    
    # Initialize video parser
    print("🔧 Initializing VideoMetadataParser...")
    parser = VideoMetadataParser(require_all_dependencies=False)
    available_libs = parser.get_available_libraries()
    
    print("📚 Available metadata extraction libraries:")
    for lib, available in available_libs.items():
        status = "✅" if available else "❌"
        print(f"   {status} {lib}")
    print()
    
    # Find video files (excluding angles subdirectory)
    video_files = []
    for pattern in ["*.MP4", "*.mp4"]:
        # Get files in main directory
        video_files.extend(test_data_dir.glob(pattern))
        # Get files in subdirectories but exclude 'angles'
        for video_file in test_data_dir.glob(f"**/{pattern}"):
            if 'angles' not in str(video_file.parent).lower():
                video_files.append(video_file)
    
    print(f"🎬 Found {len(video_files)} video files:")
    for vf in video_files:
        print(f"   📹 {vf.relative_to(test_data_dir) if vf.is_relative_to(test_data_dir) else vf.name}")
    print()
    
    # Process videos
    results = []
    batch = VideoProcessingBatch(
        batch_id=f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        processing_start=datetime.now(),
        source_directory=str(test_data_dir)
    )
    
    print("🚀 Processing videos...")
    print("-" * 40)
    
    for i, video_file in enumerate(video_files[:2], 1):  # Limit to first 2 videos
        print(f"\\n{i}. Processing: {video_file.name}")
        
        try:
            # Extract metadata
            extraction_result = parser.parse_video(str(video_file))
            
            # Convert to our model format
            video_result = convert_to_analysis_result(extraction_result, video_file)
            results.append(video_result)
            batch.add_result(video_result)
            
            # Print summary
            print(f"   ✅ Success: {video_result.extraction_success}")
            print(f"   📊 File size: {video_result.video_metadata.filesize_mb:.1f} MB")
            print(f"   ⏱️  Duration: {video_result.video_metadata.get_duration_formatted()}")
            
            if video_result.technical_specs.width:
                print(f"   🎬 Resolution: {video_result.technical_specs.width}x{video_result.technical_specs.height}")
            
            if video_result.has_gps():
                gps = video_result.gps_data
                print(f"   🌍 GPS: {gps.latitude_decimal:.6f}, {gps.longitude_decimal:.6f}")
            
            print(f"   🚁 DJI fields: {len(video_result.dji_metadata)}")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            continue
    
    batch.processing_end = datetime.now()
    
    # Generate outputs using formatters
    print(f"\\n📝 Generating output files...")
    print("-" * 40)
    
    config = FormatterConfig(
        output_directory=str(output_dir),
        overwrite_existing=True,
        create_directories=True
    )
    
    all_output_files = []
    
    # 1. Markdown documentation
    print("\\n📋 Generating Markdown documentation...")
    md_formatter = MarkdownFormatter(config)
    for result in results:
        md_files = md_formatter.format_single_video(result)
        all_output_files.extend(md_files)
        print(f"   ✅ {md_files[0].name}")
    
    # 2. Thumbnail placeholders
    print("\\n🖼️  Generating thumbnail placeholders...")
    thumb_formatter = ThumbnailGenerator(config)
    for result in results:
        thumb_files = thumb_formatter.format_single_video(result)
        all_output_files.extend(thumb_files)
        print(f"   ✅ {thumb_files[0].name}")
    
    # 3. Semantic model CSV tables
    print("\\n📊 Generating semantic model CSV tables...")
    csv_formatter = SemanticModelExporter(config)
    csv_files = csv_formatter.format_batch(batch)
    all_output_files.extend(csv_files)
    for csv_file in csv_files:
        print(f"   ✅ {csv_file.name}")
    
    # 4. Dataset index and documentation
    print("\\n📋 Generating dataset documentation...")
    index_formatter = DatasetIndexGenerator(config)
    index_files = index_formatter.format_batch(batch)
    all_output_files.extend(index_files)
    for index_file in index_files:
        print(f"   ✅ {index_file.name}")
    
    # Summary
    print(f"\\n🎉 PROCESSING COMPLETE!")
    print("=" * 60)
    print(f"📹 Videos processed: {len(results)}")
    print(f"📁 Output files generated: {len(all_output_files)}")
    print(f"⏱️  Total processing time: {batch.get_processing_duration().total_seconds():.2f} seconds")
    print(f"✅ Success rate: {batch.get_success_rate():.1f}%")
    
    # Show output directory contents
    print(f"\\n📂 Output directory contents ({output_dir.absolute()}):")
    for file_path in sorted(output_dir.iterdir()):
        if file_path.is_file():
            size_kb = file_path.stat().st_size / 1024
            print(f"   📄 {file_path.name} ({size_kb:.1f} KB)")
    
    print(f"\\n💡 You can now inspect the generated files in: {output_dir.absolute()}")
    print("   - *.md files contain video documentation")
    print("   - *.csv files contain normalized data tables")
    print("   - DATASET_INDEX.md contains the master overview")
    print("   - *_thumbnail.jpg are placeholder files (Phase 2 will generate real thumbnails)")
    
    return output_dir, results


def convert_to_analysis_result(extraction_result, video_file: Path) -> VideoAnalysisResult:
    """Convert VideoMetadataExtractionResult to VideoAnalysisResult model."""
    
    # Extract file info
    video_metadata = VideoMetadata(
        filename=video_file.name,
        filepath=str(video_file.absolute()),
        filesize_bytes=extraction_result.file_info.get('filesize_bytes', 0),
        filesize_mb=extraction_result.file_info.get('filesize_mb', 0.0),
        duration_seconds=None,
        last_modified=datetime.now(),
        extraction_time=datetime.now()
    )
    
    # Extract technical specs
    tech_specs = TechnicalSpecs()
    
    if extraction_result.ffmpeg_metadata:
        # Get duration from format info
        fmt = extraction_result.ffmpeg_metadata.get('ffmpeg_format', {})
        if 'duration' in fmt:
            video_metadata.duration_seconds = float(fmt['duration'])
        
        # Get video specs from streams
        video_streams = extraction_result.ffmpeg_metadata.get('video_streams', [])
        if video_streams:
            stream = video_streams[0]
            tech_specs.width = stream.get('width')
            tech_specs.height = stream.get('height')
            tech_specs.video_codec = stream.get('codec_name')
            
            # Handle framerate properly (FFmpeg returns strings like "30/1")
            raw_framerate = stream.get('r_frame_rate')
            if raw_framerate:
                try:
                    if isinstance(raw_framerate, str) and '/' in raw_framerate:
                        num, den = raw_framerate.split('/')
                        tech_specs.framerate = float(num) / float(den)
                    else:
                        tech_specs.framerate = float(raw_framerate)
                except (ValueError, ZeroDivisionError):
                    tech_specs.framerate = raw_framerate  # Keep as string if can't parse
            
            if tech_specs.width and tech_specs.height:
                tech_specs.resolution_string = f"{tech_specs.width}x{tech_specs.height}"
    
    # Extract GPS data (basic implementation)
    gps_data = None
    if extraction_result.gps_data and 'gps' in extraction_result.gps_data:
        gps_info = extraction_result.gps_data['gps']
        if 'latitude_decimal' in gps_info and 'longitude_decimal' in gps_info:
            gps_data = GPSData(
                latitude_decimal=gps_info['latitude_decimal'],
                longitude_decimal=gps_info['longitude_decimal']
            )
    
    # Create mission data (improved classification logic)
    mission_data = MissionData()
    filename_lower = video_file.name.lower()
    parent_dir_lower = str(video_file.parent).lower()
    
    # Enhanced classification logic
    if 'box' in filename_lower or 'bay' in filename_lower:
        mission_data.mission_type = MissionType.BOX
        mission_data.classification_method = "filename"
        mission_data.classification_confidence = 0.7
    elif 'safety' in filename_lower:
        mission_data.mission_type = MissionType.SAFETY
        mission_data.classification_method = "filename"
        mission_data.classification_confidence = 0.7
    elif filename_lower.startswith('dji_'):
        # Default classification for standard DJI videos - assume inspection mission
        mission_data.mission_type = MissionType.OVERVIEW
        mission_data.classification_method = "filename_pattern"
        mission_data.classification_confidence = 0.6
        mission_data.mission_notes = "Standard DJI video - classified as overview inspection"
    else:
        # Fallback for other video files
        mission_data.mission_type = MissionType.SURVEY
        mission_data.classification_method = "default"
        mission_data.classification_confidence = 0.3
    
    return VideoAnalysisResult(
        video_metadata=video_metadata,
        technical_specs=tech_specs,
        gps_data=gps_data,
        mission_data=mission_data,
        dji_metadata=extraction_result.dji_specific.get('dji_specific', {}),
        extraction_success=extraction_result.success,
        extraction_errors=extraction_result.errors,
        extraction_warnings=extraction_result.warnings,
        raw_metadata=extraction_result.__dict__
    )


if __name__ == "__main__":
    try:
        output_dir, results = process_videos_demo()
        print(f"\\n🎯 Demo completed successfully!")
        print(f"📂 Check the output files in: {output_dir.absolute()}")
        
    except Exception as e:
        print(f"\\n❌ Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()