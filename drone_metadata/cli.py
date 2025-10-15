"""
Command-line interface for drone metadata automation system.
"""

import click
import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from .processor import DroneMetadataProcessor, ProcessingError
from .models import FlightReport
from .ingestion.video_metadata_parser import VideoMetadataParser
from .formatters.base_formatter import FormatterConfig
from .formatters.markdown_formatter import MarkdownFormatter
from .formatters.semantic_model_exporter import SemanticModelExporter
from .formatters.thumbnail_generator import ThumbnailGenerator
from .formatters.directory_organizer import DirectoryOrganizer
from .analysis.mission_classifier import MissionClassifier


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def main(ctx, verbose, config):
    """
    Drone Metadata Automation CLI
    
    Automated metadata extraction and annotation generation for drone inspection workflows.
    """
    # Setup logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Load configuration if provided
    config_data = {}
    if config:
        try:
            import yaml
            with open(config, 'r') as f:
                config_data = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    
    # Store configuration in context
    ctx.ensure_object(dict)
    ctx.obj['config'] = config_data


@main.command()
@click.argument('input_directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'markdown']), 
              default='json', help='Output format')
@click.pass_context
def process(ctx, input_directory, output, format):
    """
    Process a single flight directory and generate metadata report.
    
    INPUT_DIRECTORY: Path to flight directory containing telemetry and media files
    """
    try:
        logger.info(f"Processing flight directory: {input_directory}")
        
        # Initialize processor with configuration
        processor = DroneMetadataProcessor(config=ctx.obj.get('config'))
        
        # Process directory
        report = processor.process_flight_directory(input_directory)
        
        # Generate output
        if output:
            output_path = Path(output)
        else:
            # Auto-generate output filename
            dir_name = Path(input_directory).name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"flight_report_{dir_name}_{timestamp}.{format}")
        
        # Write report
        _write_report(report, output_path, format)
        
        # Print summary
        click.echo(f"\n✅ Processing completed successfully!")
        click.echo(f"📊 Flight ID: {report.flight_id}")
        click.echo(f"🏗️  Bay: {report.bay_mapping.bay_id if report.bay_mapping else 'Unknown'}")
        click.echo(f"📈 Quality Score: {report.quality_score.get_grade()} ({report.quality_score.overall_score:.2f})")
        click.echo(f"⏱️  Processing Time: {report.processing_time.total_seconds():.1f}s")
        click.echo(f"📁 Output: {output_path}")
        
        if report.human_verification_needed:
            click.echo(f"⚠️  Human verification needed: {', '.join(report.human_verification_needed)}")
        
        if report.anomalies:
            click.echo(f"🚨 Anomalies detected: {len(report.anomalies)}")
            for anomaly in report.anomalies[:3]:  # Show first 3
                click.echo(f"   • {anomaly.description}")
        
    except ProcessingError as e:
        logger.error(f"Processing failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('parent_directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory for reports')
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'markdown']), 
              default='json', help='Output format')
@click.option('--summary/--no-summary', default=True, help='Generate batch summary report')
@click.pass_context
def batch(ctx, parent_directory, output_dir, format, summary):
    """
    Process multiple flight directories in batch.
    
    PARENT_DIRECTORY: Parent directory containing flight subdirectories
    """
    try:
        logger.info(f"Starting batch processing: {parent_directory}")
        
        # Initialize processor
        processor = DroneMetadataProcessor(config=ctx.obj.get('config'))
        
        # Setup output directory
        if output_dir:
            output_path = Path(output_dir)
        else:
            output_path = Path(f"batch_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process directories
        reports = processor.process_batch_directories(parent_directory)
        
        if not reports:
            click.echo("❌ No flight directories found or processed successfully")
            return
        
        # Write individual reports
        for report in reports:
            filename = f"flight_report_{report.flight_id}.{format}"
            report_path = output_path / filename
            _write_report(report, report_path, format)
        
        # Generate summary if requested
        if summary:
            summary_data = _generate_batch_summary(reports)
            summary_path = output_path / f"batch_summary.json"
            
            with open(summary_path, 'w') as f:
                json.dump(summary_data, f, indent=2, default=str)
        
        # Print results
        click.echo(f"\n✅ Batch processing completed!")
        click.echo(f"📊 Processed: {len(reports)} flight directories")
        click.echo(f"📁 Output directory: {output_path}")
        
        # Quality distribution
        grades = [r.quality_score.get_grade() for r in reports]
        grade_counts = {g: grades.count(g) for g in set(grades)}
        click.echo(f"📈 Quality distribution: {dict(sorted(grade_counts.items()))}")
        
        # Anomaly summary
        total_anomalies = sum(len(r.anomalies) for r in reports)
        click.echo(f"🚨 Total anomalies detected: {total_anomalies}")
        
    except ProcessingError as e:
        logger.error(f"Batch processing failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_context
def scan(ctx, directory):
    """
    Scan a directory and show discovered data sources without processing.
    
    DIRECTORY: Directory to scan for flight data
    """
    try:
        from .ingestion.directory_scanner import DirectoryScanner
        
        scanner = DirectoryScanner()
        dataset = scanner.scan_flight_directory(directory)
        validation = scanner.validate_dataset_completeness(dataset)
        recommendations = scanner.get_processing_recommendations(dataset)
        
        click.echo(f"\n📁 Directory: {directory}")
        click.echo(f"🏗️  Bay ID: {dataset.bay_identifier or 'Not detected'}")
        click.echo(f"🔍 Inspection Type: {dataset.inspection_type.value if dataset.inspection_type else 'Not detected'}")
        
        click.echo(f"\n📄 Data Sources:")
        click.echo(f"   • CSV files: {len(dataset.airdata_csv_files)}")
        click.echo(f"   • SRT files: {len(dataset.srt_files)}")
        click.echo(f"   • Media files: {len(dataset.media_files)}")
        click.echo(f"   • Flight records: {len(dataset.flight_record_files)}")
        
        click.echo(f"\n✅ Validation:")
        for check, result in validation.items():
            status = "✓" if result else "✗"
            click.echo(f"   {status} {check}: {result}")
        
        if recommendations:
            click.echo(f"\n💡 Recommendations:")
            for rec in recommendations:
                click.echo(f"   • {rec}")
        
        # Show file details if verbose
        if ctx.obj.get('config', {}).get('verbose', False):
            click.echo(f"\n📋 File Details:")
            for file_type, files in [
                ('CSV', dataset.airdata_csv_files),
                ('SRT', dataset.srt_files),
                ('Media', dataset.media_files[:10]),  # Limit media files shown
                ('Flight Records', dataset.flight_record_files)
            ]:
                if files:
                    click.echo(f"   {file_type} files:")
                    for file in files:
                        click.echo(f"     - {Path(file).name}")
                    if file_type == 'Media' and len(dataset.media_files) > 10:
                        click.echo(f"     ... and {len(dataset.media_files) - 10} more")
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@main.command()
def demo():
    """
    Run demonstration with sample data.
    """
    click.echo("🚁 Drone Metadata Automation Demo")
    click.echo("\nThis would demonstrate the system with sample flight data.")
    click.echo("Use the 'process' command with your actual flight directories.")
    
    # Show example usage
    click.echo(f"\n📚 Example Usage:")
    click.echo(f"   drone-metadata process 'C:\\path\\to\\flight\\data'")
    click.echo(f"   drone-metadata batch 'C:\\path\\to\\aug_2025'")
    click.echo(f"   drone-metadata scan 'C:\\path\\to\\flight\\data'")
    click.echo(f"   drone-metadata process-videos 'C:\\path\\to\\videos'")
    click.echo(f"   drone-metadata extract-metadata 'video.mp4'")
    
    # Show expected directory structure
    click.echo(f"\n📁 Expected Directory Structure:")
    click.echo(f"   flight_directory/")
    click.echo(f"   ├── *.csv (airdata files)")
    click.echo(f"   ├── *.srt (subtitle files)")
    click.echo(f"   ├── *.mp4, *.jpg (media files)")
    click.echo(f"   └── *.txt (flight records)")


@main.command('process-videos')
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output directory for processed files')
@click.option('--format', '-f', multiple=True, 
              type=click.Choice(['markdown', 'semantic', 'thumbnails']),
              default=['markdown', 'thumbnails'], 
              help='Output formats to generate (can specify multiple)')
@click.option('--organize/--no-organize', default=True, 
              help='Organize outputs by mission type')
@click.option('--parallel', '-p', type=int, default=1,
              help='Number of parallel processing threads')
@click.option('--classify-missions/--no-classify-missions', default=True,
              help='Enable automatic mission classification')
@click.pass_context
def process_videos(ctx, input_path, output, format, organize, parallel, classify_missions):
    """
    Process drone videos with Phase 2 capabilities.
    
    INPUT_PATH: Path to video file or directory containing videos
    
    This command provides advanced video processing with:
    - Automatic mission classification (box/safety)
    - Real FFmpeg thumbnail generation 
    - Semantic model export
    - Mission-based directory organization
    """
    try:
        input_path = Path(input_path)
        
        # Setup output directory - centralized by default
        if output:
            output_dir = Path(output)
        else:
            # Use centralized output directory
            centralized_output = Path("C:\\Users\\donal\\drone_metadata_automation\\output")
            
            # Create a subdirectory based on the input source
            if input_path.is_file():
                subdir_name = f"{input_path.stem}_processed"
            else:
                # Use the input directory name for organization
                subdir_name = f"{input_path.name}_processed"
            
            output_dir = centralized_output / subdir_name
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        click.echo(f"🎬 Processing videos from: {input_path}")
        click.echo(f"📁 Output directory: {output_dir}")
        click.echo(f"🔧 Formats: {', '.join(format)}")
        click.echo(f"📋 Mission classification: {'enabled' if classify_missions else 'disabled'}")
        click.echo(f"🗂️  Organization: {'enabled' if organize else 'disabled'}")
        
        # Create formatter config
        formatter_config = FormatterConfig(
            output_directory=str(output_dir),
            create_directories=True,
            overwrite_existing=True
        )
        
        # Setup formatters based on requested formats
        formatters = []
        
        if 'markdown' in format:
            formatters.append(MarkdownFormatter(formatter_config))
            click.echo("   ✓ Markdown formatter enabled")
        
        if 'semantic' in format:
            formatters.append(SemanticModelExporter(formatter_config))
            click.echo("   ✓ Semantic model exporter enabled")
            
        if 'thumbnails' in format:
            # Configure thumbnail generator
            formatter_config.thumbnail_timestamp = 3.0
            formatter_config.thumbnail_width = 640
            formatter_config.thumbnail_quality = 3
            formatter_config.fallback_enabled = True
            formatters.append(ThumbnailGenerator(formatter_config))
            click.echo("   ✓ Thumbnail generator enabled")
        
        # Setup mission classifier if enabled
        mission_classifier = None
        if classify_missions:
            mission_classifier = MissionClassifier()
            click.echo("   ✓ Mission classifier enabled")
        
        # Setup directory organizer if enabled
        organizer = None
        if organize:
            organizer = DirectoryOrganizer(formatter_config)
            formatter_config.organizer = organizer  # Configure organizer in formatter config
            click.echo("   ✓ Directory organizer enabled")
        
        # Initialize video metadata parser
        video_parser = VideoMetadataParser(require_all_dependencies=False)
        
        # Collect video files to process
        if input_path.is_file():
            if input_path.suffix.lower() in ['.mp4', '.mov', '.avi']:
                video_files = [input_path]
            else:
                click.echo(f"❌ {input_path} is not a supported video file")
                return
        else:
            # Find all video files in directory
            video_files = []
            for ext in ['.mp4', '.mov', '.avi']:
                video_files.extend(input_path.rglob(f'*{ext}'))
                video_files.extend(input_path.rglob(f'*{ext.upper()}'))
        
        if not video_files:
            click.echo("❌ No video files found to process")
            return
        
        click.echo(f"\n🎥 Found {len(video_files)} video files to process")
        
        # Process videos
        processed_count = 0
        failed_count = 0
        
        for i, video_file in enumerate(video_files, 1):
            click.echo(f"\n[{i}/{len(video_files)}] Processing: {video_file.name}")
            
            try:
                # Parse video metadata
                parse_result = video_parser.parse_video(str(video_file))
                
                if not parse_result.success:
                    raise Exception(f"Failed to parse metadata: {'; '.join(parse_result.errors)}")
                
                # Create VideoAnalysisResult from parse result
                result = _create_analysis_result_from_parse(parse_result, video_file)
                
                # Apply mission classification if enabled
                if mission_classifier and result:
                    mission_data = mission_classifier.classify_video(
                        result,
                        str(video_file)
                    )
                    result.mission_data = mission_data
                    click.echo(f"   🎯 Mission: {mission_data.mission_type.name.lower()}")
                
                # Apply formatters (will use organized paths if organizer is configured)
                for formatter in formatters:
                    try:
                        output_paths = formatter.format_single_video(result)
                        organized_info = " (organized)" if organize else ""
                        click.echo(f"   ✓ {formatter.__class__.__name__}: {len(output_paths)} files{organized_info}")
                    except Exception as e:
                        click.echo(f"   ❌ {formatter.__class__.__name__} failed: {e}")
                
                processed_count += 1
                
            except Exception as e:
                click.echo(f"   ❌ Processing failed: {e}")
                failed_count += 1
                logger.error(f"Failed to process {video_file}: {e}", exc_info=True)
        
        # Final summary
        click.echo(f"\n✅ Processing complete!")
        click.echo(f"   📊 Successfully processed: {processed_count}")
        click.echo(f"   ❌ Failed: {failed_count}")
        click.echo(f"   📁 Output directory: {output_dir}")
        
        # Show directory structure if organized
        if organize and organizer:
            structure_info = organizer.get_directory_structure()
            click.echo(f"\n📂 Directory Structure Created:")
            for dir_path in sorted(structure_info.keys()):
                file_count = structure_info[dir_path].get('file_count', 0)
                click.echo(f"   📁 {dir_path}/ ({file_count} files)")
        
    except Exception as e:
        logger.error(f"Video processing failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@main.command('extract-metadata')
@click.argument('video_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'markdown']), 
              default='json', help='Output format')
@click.option('--include-technical/--no-technical', default=True,
              help='Include technical video specifications')
@click.option('--include-gps/--no-gps', default=True,
              help='Include GPS/location data if available')
@click.pass_context
def extract_metadata(ctx, video_path, output, format, include_technical, include_gps):
    """
    Extract metadata from a single video file.
    
    VIDEO_PATH: Path to the video file to analyze
    
    This command extracts detailed metadata including:
    - Basic video properties (duration, resolution, format)
    - DJI-specific metadata (GPS, gimbal, camera settings)
    - Technical specifications
    """
    try:
        video_path = Path(video_path)
        
        if not video_path.exists():
            click.echo(f"❌ Video file not found: {video_path}")
            return
        
        click.echo(f"📹 Extracting metadata from: {video_path.name}")
        
        # Initialize video metadata parser
        video_parser = VideoMetadataParser(require_all_dependencies=False)
        
        # Parse the video metadata
        parse_result = video_parser.parse_video(str(video_path))
        
        if not parse_result.success:
            raise Exception(f"Failed to parse metadata: {'; '.join(parse_result.errors)}")
        
        # Create simplified result for metadata extraction
        result = _create_analysis_result_from_parse(parse_result, video_path)
        
        if not result:
            click.echo("❌ Failed to extract metadata")
            return
        
        # Prepare metadata for output
        metadata = {
            'filename': result.video_metadata.filename,
            'duration_seconds': result.video_metadata.duration_seconds,
            'duration_formatted': result.video_metadata.get_duration_formatted(),
            'file_size_mb': result.video_metadata.filesize_mb,
            'created_at': result.video_metadata.creation_time.isoformat() if result.video_metadata.creation_time else None
        }
        
        # Add technical specs if requested
        if include_technical and result.technical_specs:
            metadata['technical_specs'] = {
                'width': result.technical_specs.width,
                'height': result.technical_specs.height,
                'fps': result.technical_specs.framerate,
                'bitrate': result.technical_specs.bitrate_video,
                'codec': result.technical_specs.video_codec,
                'container': result.technical_specs.container_format
            }
        
        # Add GPS data if requested
        if include_gps and result.gps_data:
            metadata['gps_data'] = {
                'latitude': result.gps_data.latitude_decimal,
                'longitude': result.gps_data.longitude_decimal,
                'altitude_meters': result.gps_data.altitude_meters
            }
        
        # Add DJI metadata if available
        if result.dji_metadata:
            metadata['dji_metadata'] = dict(result.dji_metadata)
        
        # Determine output path - use centralized output by default
        if output:
            output_path = Path(output)
        else:
            centralized_output = Path("C:\\Users\\donal\\drone_metadata_automation\\output")
            centralized_output.mkdir(parents=True, exist_ok=True)
            output_path = centralized_output / f"{video_path.stem}_metadata.{format}"
        
        # Write metadata
        if format == 'json':
            import json
            with open(output_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
        else:  # markdown
            md_content = f"""# Video Metadata: {metadata['filename']}

## Basic Information

- **Duration:** {metadata['duration_formatted']} ({metadata['duration_seconds']} seconds)
- **File Size:** {metadata['file_size_mb']:.2f} MB
- **Created:** {metadata.get('created_at', 'Unknown')}

"""
            
            if 'technical_specs' in metadata:
                specs = metadata['technical_specs']
                md_content += f"""## Technical Specifications

- **Resolution:** {specs['width']}x{specs['height']}
- **Frame Rate:** {specs['fps']} fps
- **Bitrate:** {specs['bitrate']} kbps
- **Codec:** {specs['codec']}
- **Container:** {specs['container']}

"""
            
            if 'gps_data' in metadata:
                gps = metadata['gps_data']
                md_content += f"""## Location Data

- **Latitude:** {gps['latitude']}
- **Longitude:** {gps['longitude']}
- **Altitude:** {gps['altitude_meters']}m

"""
            
            if 'dji_metadata' in metadata:
                md_content += "## DJI Metadata\n\n"
                for key, value in metadata['dji_metadata'].items():
                    md_content += f"- **{key}:** {value}\n"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
        
        click.echo(f"✅ Metadata extracted successfully")
        click.echo(f"   📁 Output: {output_path}")
        click.echo(f"   📊 Format: {format}")
        
        # Show basic info
        click.echo(f"\n📋 Summary:")
        click.echo(f"   Duration: {metadata['duration_formatted']}")
        click.echo(f"   File size: {metadata['file_size_mb']:.2f} MB")
        if 'technical_specs' in metadata:
            specs = metadata['technical_specs']
            click.echo(f"   Resolution: {specs['width']}x{specs['height']}")
        if 'gps_data' in metadata:
            click.echo(f"   GPS: Available")
        if 'dji_metadata' in metadata:
            click.echo(f"   DJI metadata: {len(metadata['dji_metadata'])} fields")
        
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@main.command('generate-catalog')
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--output', '-o', type=click.Path(), help='Output catalog file')
@click.option('--format', '-f', type=click.Choice(['html', 'markdown']), 
              default='html', help='Catalog format')
@click.option('--include-thumbnails/--no-thumbnails', default=True,
              help='Generate and include thumbnail images')
@click.option('--group-by', type=click.Choice(['mission', 'date', 'none']),
              default='mission', help='How to group videos in catalog')
@click.pass_context
def generate_catalog(ctx, directory, output, format, include_thumbnails, group_by):
    """
    Generate a visual catalog of processed videos.
    
    DIRECTORY: Directory containing processed videos and metadata
    
    Creates an HTML or Markdown catalog showing:
    - Video thumbnails and metadata
    - Mission classifications
    - Processing results summary
    """
    try:
        directory = Path(directory)
        
        click.echo(f"📚 Generating video catalog for: {directory}")
        click.echo(f"🎨 Format: {format}")
        click.echo(f"🖼️  Include thumbnails: {include_thumbnails}")
        click.echo(f"📊 Group by: {group_by}")
        
        # Find all processed metadata files
        metadata_files = list(directory.rglob('*.md')) + list(directory.rglob('*_metadata.json'))
        
        if not metadata_files:
            click.echo("❌ No processed metadata files found")
            click.echo("   Run 'process-videos' first to generate metadata")
            return
        
        click.echo(f"📄 Found {len(metadata_files)} metadata files")
        
        # Determine output path - use centralized output by default
        if output:
            output_path = Path(output)
        else:
            centralized_output = Path("C:\\Users\\donal\\drone_metadata_automation\\output")
            centralized_output.mkdir(parents=True, exist_ok=True)
            output_path = centralized_output / f"video_catalog.{format}"
        
        # Generate catalog content
        if format == 'html':
            catalog_content = _generate_html_catalog(metadata_files, directory, include_thumbnails, group_by)
        else:  # markdown
            catalog_content = _generate_markdown_catalog(metadata_files, directory, include_thumbnails, group_by)
        
        # Write catalog
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(catalog_content)
        
        click.echo(f"\n✅ Catalog generated successfully")
        click.echo(f"   📁 Output: {output_path}")
        click.echo(f"   📊 Videos cataloged: {len(metadata_files)}")
        
        if format == 'html':
            click.echo(f"   🌐 Open in browser: file://{output_path.absolute()}")
        
    except Exception as e:
        logger.error(f"Catalog generation failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


def _write_report(report: FlightReport, output_path: Path, format: str) -> None:
    """Write report to file in specified format."""
    
    if format == 'json':
        # Convert report to JSON-serializable dict
        report_dict = _report_to_dict(report)
        
        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2, default=str)
            
    elif format == 'markdown':
        markdown_content = _report_to_markdown(report)
        
        with open(output_path, 'w') as f:
            f.write(markdown_content)
            
    elif format == 'csv':
        # Simple CSV format with key metrics
        import csv
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'flight_id', 'bay_id', 'inspection_type', 'quality_grade', 'quality_score',
                'max_altitude_ft', 'total_distance_miles', 'battery_consumed_pct',
                'total_photos', 'total_videos', 'anomalies_count', 'processing_time_sec'
            ])
            
            # Data
            writer.writerow([
                report.flight_id,
                report.bay_mapping.bay_id if report.bay_mapping else '',
                report.inspection_classification.inspection_type.value,
                report.quality_score.get_grade(),
                f"{report.quality_score.overall_score:.3f}",
                f"{report.flight_metrics.max_altitude:.1f}",
                f"{report.flight_metrics.total_distance:.3f}",
                f"{report.flight_metrics.battery_consumed:.1f}",
                report.media_summary.total_photos,
                report.media_summary.total_videos,
                len(report.anomalies),
                f"{report.processing_time.total_seconds():.1f}"
            ])


def _report_to_dict(report: FlightReport) -> Dict[str, Any]:
    """Convert FlightReport to dictionary for JSON serialization."""
    return {
        'flight_id': report.flight_id,
        'timestamp_generated': report.timestamp_generated.isoformat(),
        'processing_time_seconds': report.processing_time.total_seconds() if report.processing_time else 0,
        
        'bay_mapping': {
            'bay_id': report.bay_mapping.bay_id,
            'bay_name': report.bay_mapping.bay_name,
            'confidence_score': report.bay_mapping.confidence_score,
            'coverage_percentage': report.bay_mapping.coverage_percentage
        } if report.bay_mapping else None,
        
        'flight_metrics': {
            'max_altitude_ft': report.flight_metrics.max_altitude,
            'avg_altitude_ft': report.flight_metrics.avg_altitude,
            'max_speed_mph': report.flight_metrics.max_speed,
            'avg_speed_mph': report.flight_metrics.avg_speed,
            'total_distance_miles': report.flight_metrics.total_distance,
            'battery_start_pct': report.flight_metrics.battery_start,
            'battery_end_pct': report.flight_metrics.battery_end,
            'battery_consumed_pct': report.flight_metrics.battery_consumed,
            'gps_quality_avg': report.flight_metrics.gps_quality_avg
        },
        
        'quality_score': {
            'overall_score': report.quality_score.overall_score,
            'grade': report.quality_score.get_grade(),
            'gps_quality': report.quality_score.gps_quality,
            'battery_health': report.quality_score.battery_health,
            'flight_stability': report.quality_score.flight_stability,
            'coverage_quality': report.quality_score.coverage_quality,
            'equipment_performance': report.quality_score.equipment_performance
        },
        
        'inspection_classification': {
            'inspection_type': report.inspection_classification.inspection_type.value,
            'confidence': report.inspection_classification.confidence
        },
        
        'media_summary': {
            'total_photos': report.media_summary.total_photos,
            'total_videos': report.media_summary.total_videos,
            'video_duration_minutes': report.media_summary.total_video_duration.total_seconds() / 60
        },
        
        'flight_path': {
            'total_distance_miles': report.flight_path.total_distance,
            'coordinate_count': len(report.flight_path.coordinates),
            'is_circular': report.flight_path.is_circular,
            'is_linear': report.flight_path.is_linear,
            'circuit_completion': report.flight_path.circuit_completion
        },
        
        'anomalies': [
            {
                'timestamp': anomaly.timestamp.isoformat(),
                'type': anomaly.anomaly_type,
                'severity': anomaly.severity,
                'description': anomaly.description
            }
            for anomaly in report.anomalies
        ],
        
        'automated_annotations': report.automated_annotations,
        'human_verification_needed': report.human_verification_needed
    }


def _report_to_markdown(report: FlightReport) -> str:
    """Convert FlightReport to Markdown format."""
    md = f"""# Flight Report: {report.flight_id}

**Generated:** {report.timestamp_generated.strftime('%Y-%m-%d %H:%M:%S')}  
**Processing Time:** {report.processing_time.total_seconds():.1f}s

## Summary

- **Bay:** {report.bay_mapping.bay_id if report.bay_mapping else 'Unknown'}
- **Inspection Type:** {report.inspection_classification.inspection_type.value}
- **Quality Grade:** {report.quality_score.get_grade()} ({report.quality_score.overall_score:.2f})

## Flight Metrics

| Metric | Value |
|--------|-------|
| Max Altitude | {report.flight_metrics.max_altitude:.1f} ft |
| Average Altitude | {report.flight_metrics.avg_altitude:.1f} ft |
| Max Speed | {report.flight_metrics.max_speed:.1f} mph |
| Total Distance | {report.flight_metrics.total_distance:.2f} miles |
| Battery Consumed | {report.flight_metrics.battery_consumed:.1f}% |
| GPS Quality | {report.flight_metrics.gps_quality_avg:.1f} satellites |

## Media Summary

- **Photos:** {report.media_summary.total_photos}
- **Videos:** {report.media_summary.total_videos}
- **Video Duration:** {report.media_summary.total_video_duration.total_seconds() / 60:.1f} minutes

## Quality Assessment

| Component | Score | Rating |
|-----------|-------|--------|
| Overall | {report.quality_score.overall_score:.2f} | {report.quality_score.get_grade()} |
| GPS Quality | {report.quality_score.gps_quality:.2f} | {'✓' if report.quality_score.gps_quality > 0.8 else '⚠️'} |
| Battery Health | {report.quality_score.battery_health:.2f} | {'✓' if report.quality_score.battery_health > 0.8 else '⚠️'} |
| Flight Stability | {report.quality_score.flight_stability:.2f} | {'✓' if report.quality_score.flight_stability > 0.8 else '⚠️'} |
"""

    if report.anomalies:
        md += f"\n## Anomalies ({len(report.anomalies)})\n\n"
        for anomaly in report.anomalies:
            md += f"- **{anomaly.severity.upper()}:** {anomaly.description}\n"
    
    if report.human_verification_needed:
        md += f"\n## Human Verification Required\n\n"
        for item in report.human_verification_needed:
            md += f"- {item.replace('_', ' ').title()}\n"
    
    return md


def _generate_batch_summary(reports: List[FlightReport]) -> Dict[str, Any]:
    """Generate summary statistics for batch processing."""
    if not reports:
        return {}
    
    total_flights = len(reports)
    
    # Quality distribution
    grades = [r.quality_score.get_grade() for r in reports]
    grade_distribution = {grade: grades.count(grade) for grade in set(grades)}
    
    # Average metrics
    avg_altitude = sum(r.flight_metrics.avg_altitude for r in reports) / total_flights
    avg_distance = sum(r.flight_metrics.total_distance for r in reports) / total_flights
    avg_battery = sum(r.flight_metrics.battery_consumed for r in reports) / total_flights
    
    # Bay distribution
    bays = [r.bay_mapping.bay_id for r in reports if r.bay_mapping]
    bay_distribution = {bay: bays.count(bay) for bay in set(bays)} if bays else {}
    
    # Processing performance
    avg_processing_time = sum(
        r.processing_time.total_seconds() for r in reports if r.processing_time
    ) / max(len([r for r in reports if r.processing_time]), 1)
    
    return {
        'batch_summary': {
            'total_flights': total_flights,
            'timestamp_generated': datetime.now().isoformat(),
            'processing_performance': {
                'avg_processing_time_seconds': avg_processing_time,
                'total_processing_time_seconds': sum(
                    r.processing_time.total_seconds() for r in reports if r.processing_time
                )
            }
        },
        'quality_distribution': grade_distribution,
        'bay_distribution': bay_distribution,
        'average_metrics': {
            'altitude_ft': round(avg_altitude, 1),
            'distance_miles': round(avg_distance, 2), 
            'battery_consumed_pct': round(avg_battery, 1)
        },
        'anomaly_summary': {
            'total_anomalies': sum(len(r.anomalies) for r in reports),
            'flights_with_anomalies': len([r for r in reports if r.anomalies]),
            'anomaly_types': list(set(
                a.anomaly_type for r in reports for a in r.anomalies
            ))
        }
    }


def _generate_html_catalog(metadata_files: List[Path], base_directory: Path, 
                          include_thumbnails: bool, group_by: str) -> str:
    """Generate HTML catalog content."""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Drone Video Catalog</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .video-group {{ margin-bottom: 40px; }}
        .video-item {{ 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            margin: 20px 0; 
            padding: 15px; 
            background: #f9f9f9;
        }}
        .thumbnail {{ float: left; margin-right: 15px; max-width: 200px; }}
        .metadata {{ overflow: auto; }}
        .filename {{ font-weight: bold; font-size: 1.2em; color: #333; }}
        .details {{ margin-top: 10px; }}
        .mission-badge {{ 
            display: inline-block; 
            padding: 4px 8px; 
            border-radius: 4px; 
            background: #007bff; 
            color: white; 
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚁 Drone Video Catalog</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Total Videos: {len(metadata_files)}</p>
    </div>
"""
    
    # Group files if requested
    if group_by == 'mission':
        html_content += "<div class='video-group'><h2>📋 Videos by Mission Type</h2>"
    elif group_by == 'date':
        html_content += "<div class='video-group'><h2>📅 Videos by Date</h2>"
    else:
        html_content += "<div class='video-group'><h2>🎥 All Videos</h2>"
    
    # Add video entries
    for metadata_file in metadata_files:
        try:
            # Extract basic info from filename
            video_name = metadata_file.stem.replace('_metadata', '').replace('.MP4', '.MP4')
            
            # Look for thumbnail
            thumbnail_path = None
            if include_thumbnails:
                thumbnail_candidates = [
                    metadata_file.parent / f"{video_name}_thumbnail.jpg",
                    metadata_file.parent / "thumbnails" / f"{video_name}_thumbnail.jpg",
                ]
                for candidate in thumbnail_candidates:
                    if candidate.exists():
                        thumbnail_path = candidate.relative_to(base_directory)
                        break
            
            html_content += f"""
            <div class="video-item">
                <div class="filename">{video_name}</div>
                {f'<img class="thumbnail" src="{thumbnail_path}" alt="Thumbnail">' if thumbnail_path else ''}
                <div class="metadata">
                    <div class="details">
                        <span class="mission-badge">Video File</span>
                        <p>Metadata: {metadata_file.name}</p>
                    </div>
                </div>
                <div style="clear: both;"></div>
            </div>
            """
        except Exception as e:
            logger.warning(f"Failed to process metadata file {metadata_file}: {e}")
    
    html_content += "</div></body></html>"
    return html_content


def _generate_markdown_catalog(metadata_files: List[Path], base_directory: Path,
                              include_thumbnails: bool, group_by: str) -> str:
    """Generate Markdown catalog content."""
    md_content = f"""# 🚁 Drone Video Catalog

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Total Videos:** {len(metadata_files)}

---

"""
    
    if group_by == 'mission':
        md_content += "## 📋 Videos by Mission Type\n\n"
    elif group_by == 'date':
        md_content += "## 📅 Videos by Date\n\n"
    else:
        md_content += "## 🎥 All Videos\n\n"
    
    # Add video entries
    for i, metadata_file in enumerate(metadata_files, 1):
        try:
            video_name = metadata_file.stem.replace('_metadata', '').replace('.MP4', '.MP4')
            
            md_content += f"### {i}. {video_name}\n\n"
            
            # Look for thumbnail
            if include_thumbnails:
                thumbnail_candidates = [
                    metadata_file.parent / f"{video_name}_thumbnail.jpg",
                    metadata_file.parent / "thumbnails" / f"{video_name}_thumbnail.jpg",
                ]
                for candidate in thumbnail_candidates:
                    if candidate.exists():
                        thumbnail_rel = candidate.relative_to(base_directory)
                        md_content += f"![Thumbnail]({thumbnail_rel})\n\n"
                        break
            
            md_content += f"**Metadata File:** `{metadata_file.name}`\n\n"
            md_content += "---\n\n"
            
        except Exception as e:
            logger.warning(f"Failed to process metadata file {metadata_file}: {e}")
    
    return md_content


def _create_analysis_result_from_parse(parse_result, video_file):
    """Create a VideoAnalysisResult from VideoMetadataParser result."""
    from .models import VideoMetadata, VideoAnalysisResult, TechnicalSpecs, GPSData
    from datetime import datetime
    
    # Create video metadata
    file_info = parse_result.file_info
    video_metadata = VideoMetadata(
        filename=Path(video_file).name,
        filepath=str(video_file),
        filesize_bytes=int(file_info.get('size_mb', 0) * 1024 * 1024),
        filesize_mb=file_info.get('size_mb', 0),
        duration_seconds=file_info.get('duration_seconds'),
        creation_time=file_info.get('created_at')
    )
    
    # Create technical specs from combined metadata
    all_metadata = {
        **parse_result.ffmpeg_metadata,
        **parse_result.hachoir_metadata,
        **parse_result.mediainfo_metadata
    }
    
    technical_specs = TechnicalSpecs(
        width=all_metadata.get('width'),
        height=all_metadata.get('height'),
        framerate=all_metadata.get('frame_rate') or all_metadata.get('fps'),
        bitrate_video=all_metadata.get('bit_rate') or all_metadata.get('bitrate'),
        video_codec=all_metadata.get('codec_name') or all_metadata.get('codec'),
        container_format=Path(video_file).suffix.lower().lstrip('.')
    )
    
    # Create GPS data if available
    gps_data = None
    if parse_result.gps_data:
        gps_data = GPSData(
            latitude_decimal=parse_result.gps_data.get('latitude'),
            longitude_decimal=parse_result.gps_data.get('longitude'),
            altitude_meters=parse_result.gps_data.get('altitude_meters')
        )
    
    # Create analysis result
    result = VideoAnalysisResult(
        video_metadata=video_metadata,
        technical_specs=technical_specs,
        gps_data=gps_data,
        dji_metadata=parse_result.dji_specific
    )
    
    return result


if __name__ == '__main__':
    main()
