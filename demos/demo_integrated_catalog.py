#!/usr/bin/env python3
"""
Demo: Phase 2 Integrated Thumbnail + Markdown Catalog

This demo shows the new Phase 2 capabilities:
- Real FFmpeg thumbnail generation
- Mission classification 
- Enhanced semantic model
- Integrated markdown catalog with thumbnails
"""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from drone_metadata.ingestion.video_metadata_parser import VideoMetadataParser
from drone_metadata.analysis.mission_classifier import MissionClassifier
from drone_metadata.formatters.markdown_formatter import MarkdownFormatter
from drone_metadata.formatters.thumbnail_generator import ThumbnailGenerator
from drone_metadata.formatters.semantic_model_exporter import SemanticModelExporter
from drone_metadata.formatters.base_formatter import FormatterConfig


def process_video_with_thumbnails(video_path: str, output_dir: str):
    """
    Process a single video file with full Phase 2 pipeline:
    1. Extract video metadata
    2. Classify mission type
    3. Generate thumbnail 
    4. Create markdown documentation
    5. Export semantic model
    """
    print(f"🎬 Processing video: {Path(video_path).name}")
    print("=" * 60)
    
    # Step 1: Extract video metadata
    print("📹 Step 1: Extracting video metadata...")
    parser = VideoMetadataParser(require_all_dependencies=False)
    result = parser.parse_video(video_path)
    
    if not result.success:
        print(f"❌ Failed to parse video: {result.errors}")
        return
    
    print(f"✅ Video parsed successfully:")
    
    # Extract duration from FFmpeg format info
    duration = 0.0
    if result.ffmpeg_metadata and 'ffmpeg_format' in result.ffmpeg_metadata:
        duration = float(result.ffmpeg_metadata['ffmpeg_format'].get('duration', 0))
    
    # Extract resolution from video streams
    width = height = 'N/A'
    if result.ffmpeg_metadata and 'video_streams' in result.ffmpeg_metadata and result.ffmpeg_metadata['video_streams']:
        video_stream = result.ffmpeg_metadata['video_streams'][0]
        width = video_stream.get('width', 'N/A')
        height = video_stream.get('height', 'N/A')
    
    print(f"   Duration: {duration:.1f}s")
    print(f"   Resolution: {width}x{height}")
    print(f"   GPS: {'Available' if result.gps_data else 'Not available'}")
    print(f"   DJI metadata: {len(result.dji_specific.get('dji_specific', {}))} fields")
    
    # Step 2: Classify mission type
    print(f"\n🎯 Step 2: Classifying mission type...")
    classifier = MissionClassifier()
    
    # Convert to VideoAnalysisResult for classification
    from drone_metadata.models import VideoAnalysisResult, VideoMetadata, TechnicalSpecs, GPSData
    
    # Create VideoAnalysisResult from parser result
    # Extract duration from FFmpeg format info
    duration_seconds = 0.0
    if result.ffmpeg_metadata and 'ffmpeg_format' in result.ffmpeg_metadata:
        duration_seconds = float(result.ffmpeg_metadata['ffmpeg_format'].get('duration', 0))
    
    video_metadata = VideoMetadata(
        filename=Path(video_path).name,
        filepath=video_path,
        filesize_bytes=result.file_info.get('filesize_bytes', 0),
        filesize_mb=result.file_info.get('filesize_mb', 0),
        duration_seconds=duration_seconds
    )
    
    technical_specs = TechnicalSpecs()
    if result.ffmpeg_metadata and 'video_streams' in result.ffmpeg_metadata:
        video_stream = result.ffmpeg_metadata['video_streams'][0]
        technical_specs.width = video_stream.get('width')
        technical_specs.height = video_stream.get('height')
        technical_specs.framerate = video_stream.get('avg_frame_rate')
        technical_specs.video_codec = video_stream.get('codec_name')
    
    gps_data = None
    if result.gps_data:
        gps_data = GPSData(
            latitude_decimal=result.gps_data.get('latitude'),
            longitude_decimal=result.gps_data.get('longitude'),
            altitude_meters=result.gps_data.get('altitude')
        )
    
    analysis_result = VideoAnalysisResult(
        video_metadata=video_metadata,
        technical_specs=technical_specs,
        gps_data=gps_data,
        dji_metadata=result.dji_specific.get('dji_specific', {}),
        extraction_success=True
    )
    
    # Classify mission
    mission_data = classifier.classify_video(analysis_result, video_path)
    analysis_result.mission_data = mission_data
    
    print(f"✅ Mission classified:")
    print(f"   Type: {mission_data.mission_type.value}")
    print(f"   Confidence: {mission_data.classification_confidence:.3f}")
    print(f"   Bay: {mission_data.bay_designation or 'Not detected'}")
    
    # Step 3: Generate thumbnail
    print(f"\n🖼️  Step 3: Generating thumbnail...")
    config = FormatterConfig(output_directory=output_dir)
    
    thumbnail_gen = ThumbnailGenerator(config)
    thumbnail_paths = thumbnail_gen.format_single_video(analysis_result)
    
    for thumbnail_path in thumbnail_paths:
        if thumbnail_path.exists():
            print(f"✅ Thumbnail generated: {thumbnail_path}")
            print(f"   Size: {thumbnail_path.stat().st_size} bytes")
        else:
            print(f"⚠️  Thumbnail placeholder: {thumbnail_path}")
    
    # Step 4: Generate markdown documentation
    print(f"\n📝 Step 4: Creating markdown documentation...")
    markdown_gen = MarkdownFormatter(config)
    markdown_paths = markdown_gen.format_single_video(analysis_result)
    
    for md_path in markdown_paths:
        if md_path.exists():
            print(f"✅ Markdown created: {md_path}")
            print(f"   Size: {md_path.stat().st_size} bytes")
            
            # Show first few lines of markdown
            with open(md_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:10]
                print(f"   Preview:")
                for line in lines:
                    print(f"     {line.rstrip()}")
    
    # Step 5: Export semantic model
    print(f"\n📊 Step 5: Exporting semantic model...")
    semantic_gen = SemanticModelExporter(config)
    csv_paths = semantic_gen.format_single_video(analysis_result)
    
    print(f"✅ Semantic model exported:")
    for csv_path in csv_paths:
        if csv_path.exists():
            print(f"   📄 {csv_path.name}: {csv_path.stat().st_size} bytes")
    
    print(f"\n🎉 Complete processing pipeline finished!")
    print(f"📁 All outputs saved to: {output_dir}")
    
    return analysis_result


def main():
    """Main demo function."""
    print("🚀 PHASE 2 INTEGRATED CATALOG DEMO")
    print("=" * 50)
    
    # Configuration
    video_path = r"C:\Users\donal\Downloads\aug_2025\8D\DJI_0593.MP4"
    output_dir = r"C:\Users\donal\drone_metadata_automation\integrated_catalog_output"
    
    # Check if video exists
    if not Path(video_path).exists():
        print(f"❌ Video file not found: {video_path}")
        print("Please check the path and try again.")
        return
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    print(f"📹 Input video: {video_path}")
    print(f"📁 Output directory: {output_dir}")
    print()
    
    try:
        # Process the video
        result = process_video_with_thumbnails(video_path, output_dir)
        
        print(f"\n📋 SUMMARY")
        print("-" * 30)
        print(f"Video: {Path(video_path).name}")
        print(f"Mission: {result.mission_data.mission_type.value}")
        print(f"Duration: {result.video_metadata.duration_seconds:.1f}s")
        print(f"Resolution: {result.technical_specs.width}x{result.technical_specs.height}")
        print(f"GPS: {'✓' if result.gps_data and result.gps_data.is_valid() else '✗'}")
        
        print(f"\nGenerated files in {output_dir}:")
        output_path = Path(output_dir)
        for file in output_path.glob("*"):
            if file.is_file():
                print(f"  📄 {file.name} ({file.stat().st_size} bytes)")
        
        print(f"\n💡 Next steps:")
        print(f"1. Check the markdown file for comprehensive video documentation")
        print(f"2. View the thumbnail image (if FFmpeg is available)")
        print(f"3. Examine the CSV files for structured data analysis")
        print(f"4. Run this on multiple videos for batch processing")
        
    except Exception as e:
        print(f"❌ Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()