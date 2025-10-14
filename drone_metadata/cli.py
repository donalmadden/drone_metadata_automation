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
    
    # Show expected directory structure
    click.echo(f"\n📁 Expected Directory Structure:")
    click.echo(f"   flight_directory/")
    click.echo(f"   ├── *.csv (airdata files)")
    click.echo(f"   ├── *.srt (subtitle files)")
    click.echo(f"   ├── *.mp4, *.jpg (media files)")
    click.echo(f"   └── *.txt (flight records)")


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


if __name__ == '__main__':
    main()
