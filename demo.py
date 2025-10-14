#!/usr/bin/env python3
"""
Demo script for the Drone Metadata Automation System

This script demonstrates the key capabilities of the system with sample data
and provides a quick verification that the implementation works correctly.
"""

import os
import tempfile
import json
import dataclasses
from datetime import datetime, timedelta
from pathlib import Path

from drone_metadata import DroneMetadataProcessor
from drone_metadata.ingestion.directory_scanner import DirectoryScanner


def create_sample_data():
    """Create sample flight data for testing purposes."""
    
    # Create temporary directory structure
    temp_dir = Path(tempfile.mkdtemp(prefix="drone_demo_"))
    
    # Create bay directory structure
    bay_dir = temp_dir / "8B-7F"
    bay_dir.mkdir()
    
    angles_dir = bay_dir / "angles"
    angles_dir.mkdir()
    
    # Create sample airdata CSV
    csv_content = """
datetime(utc) | latitude | longitude | altitude(feet) | mileage(feet) | height_above_takeoff(feet) | satellites | speed(mph) | battery_percent | isPhoto | isVideo
2025-08-27 18:49:23 | 46.013245 | 13.250621 | 1246.8 | 0.0 | 0.0 | 16 | 0.0 | 85 | 0 | 0
2025-08-27 18:49:24 | 46.013256 | 13.250634 | 1246.9 | 3.2 | 0.1 | 16 | 1.2 | 85 | 0 | 0
2025-08-27 18:49:25 | 46.013267 | 13.250647 | 1247.1 | 6.8 | 0.3 | 16 | 2.1 | 84 | 1 | 0
2025-08-27 18:49:26 | 46.013278 | 13.250660 | 1247.4 | 10.7 | 0.6 | 16 | 2.8 | 84 | 0 | 1
2025-08-27 18:49:27 | 46.013289 | 13.250673 | 1247.8 | 15.1 | 1.0 | 16 | 3.2 | 83 | 0 | 0
""".strip()
    
    csv_file = bay_dir / "MP4-0581-Aug-27th-2025-11-49AM_20250827_1149-Flight-Airdata.csv"
    csv_file.write_text(csv_content)
    
    # Create sample SRT file
    srt_content = """1
00:00:00,000 --> 00:00:00,040
<font size="28">FrameCnt: 1, DiffTime: 40ms
2025-08-27 18:49:23
[latitude: 46.013245] [longitude: 13.250621] [rel_alt: 0.00 abs_alt: 1246.80] 
[gb_pitch: -30.0] [gb_roll: 0.0] [gb_yaw: 45.2] </font>

2
00:00:00,040 --> 00:00:00,080
<font size="28">FrameCnt: 2, DiffTime: 40ms
2025-08-27 18:49:23
[latitude: 46.013256] [longitude: 13.250634] [rel_alt: 0.10 abs_alt: 1246.90] 
[gb_pitch: -30.0] [gb_roll: 0.0] [gb_yaw: 45.3] </font>

3
00:00:00,080 --> 00:00:00,120
<font size="28">FrameCnt: 3, DiffTime: 40ms
2025-08-27 18:49:23
[latitude: 46.013267] [longitude: 13.250647] [rel_alt: 0.30 abs_alt: 1247.10] 
[gb_pitch: -30.0] [gb_roll: 0.0] [gb_yaw: 45.4] </font>
"""
    
    srt_file = bay_dir / "DJI_0001.SRT"
    srt_file.write_text(srt_content)
    
    # Create sample flight record
    flight_record_content = """
[2025-08-27 18:49:20] Aircraft armed
[2025-08-27 18:49:23] Takeoff initiated
[2025-08-27 18:49:25] Climbing to inspection altitude
[2025-08-27 18:52:15] Landing initiated
[2025-08-27 18:52:20] Aircraft disarmed
"""
    
    flight_record_file = bay_dir / "FlightRecord_20250827_184920.txt"
    flight_record_file.write_text(flight_record_content)
    
    # Create dummy media files
    video_file = bay_dir / "DJI_0001.MP4"
    video_file.write_text("# Dummy video file for demo")
    
    photo_file = angles_dir / "DJI_0001.JPG"
    photo_file.write_text("# Dummy photo file for demo")
    
    print(f"📁 Sample data created in: {temp_dir}")
    print(f"📂 Bay directory: {bay_dir}")
    return temp_dir


def demonstrate_directory_scanning(flight_dir):
    """Demonstrate the directory scanning capabilities."""
    print("\n🔍 DIRECTORY SCANNING DEMO")
    print("=" * 50)
    
    scanner = DirectoryScanner()
    scan_result = scanner.scan_flight_directory(str(flight_dir))
    
    print(f"✅ Directory scanned: {flight_dir}")
    print(f"📊 Data sources found:")
    print(f"   - CSV files: {len(scan_result.airdata_csv_files)} file(s)")
    for file_path in scan_result.airdata_csv_files:
        print(f"     • {Path(file_path).name}")
    print(f"   - SRT files: {len(scan_result.srt_files)} file(s)")
    for file_path in scan_result.srt_files:
        print(f"     • {Path(file_path).name}")
    print(f"   - Media files: {len(scan_result.media_files)} file(s)")
    for file_path in scan_result.media_files[:3]:  # Show only first 3
        print(f"     • {Path(file_path).name}")
    if len(scan_result.media_files) > 3:
        print(f"     • ... and {len(scan_result.media_files) - 3} more")
    print(f"   - Flight records: {len(scan_result.flight_record_files)} file(s)")
    for file_path in scan_result.flight_record_files:
        print(f"     • {Path(file_path).name}")
    
    print(f"🏗️  Bay identified: {scan_result.bay_identifier}")
    print(f"📋 Inspection type: {scan_result.inspection_type}")
    
    # Calculate completeness score
    total_sources = len(scan_result.airdata_csv_files) + len(scan_result.srt_files) + len(scan_result.media_files)
    completeness = min(1.0, total_sources / 3.0)  # Simple heuristic
    print(f"⚠️  Completeness: {completeness:.1%}")
    
    return scan_result


def demonstrate_processing(flight_dir):
    """Demonstrate the main processing pipeline."""
    print("\n⚙️  PROCESSING PIPELINE DEMO")
    print("=" * 50)
    
    # Initialize processor
    processor = DroneMetadataProcessor()
    
    print("🚀 Starting processing...")
    start_time = datetime.now()
    
    # Process the flight directory
    try:
        report = processor.process_flight_directory(str(flight_dir))
        processing_time = datetime.now() - start_time
        
        print(f"✅ Processing completed in {processing_time.total_seconds():.1f}s")
        print("\n📊 FLIGHT REPORT SUMMARY")
        print("-" * 30)
        
        print(f"Flight ID: {report.flight_id}")
        print(f"Generated: {report.timestamp_generated.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if report.bay_mapping:
            print(f"Bay: {report.bay_mapping.bay_id} (confidence: {report.bay_mapping.confidence_score:.1%})")
        
        if report.flight_metrics:
            metrics = report.flight_metrics
            print(f"Max Altitude: {metrics.max_altitude:.1f} ft")
            print(f"Total Distance: {metrics.total_distance:.3f} miles")
            print(f"Battery Used: {metrics.battery_consumed:.1f}%")
            print(f"GPS Quality: {metrics.gps_quality_avg:.1f} satellites")
        
        if report.quality_score:
            quality = report.quality_score
            print(f"Quality Grade: {quality.get_grade()} ({quality.overall_score:.1%})")
        
        print(f"Media Events: {len(report.media_summary.coverage_events)}")
        print(f"Anomalies: {len(report.anomalies)}")
        
        return report
        
    except Exception as e:
        print(f"❌ Processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def demonstrate_output_formats(report, output_dir):
    """Demonstrate different output formats."""
    print("\n📄 OUTPUT FORMATS DEMO")
    print("=" * 50)
    
    if not report:
        print("⚠️  No report available for output demonstration")
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # JSON output
    json_file = output_path / f"{report.flight_id}_report.json"
    with open(json_file, 'w') as f:
        report_dict = dataclasses.asdict(report)
        json.dump(report_dict, f, indent=2, default=str)
    print(f"✅ JSON report saved: {json_file}")
    
    # CSV output (simplified metrics)
    csv_file = output_path / f"{report.flight_id}_metrics.csv"
    csv_lines = [
        "metric,value,unit",
        f"flight_id,{report.flight_id},",
        f"max_altitude,{report.flight_metrics.max_altitude if report.flight_metrics else 0},feet",
        f"total_distance,{report.flight_metrics.total_distance if report.flight_metrics else 0},miles",
        f"quality_score,{report.quality_score.overall_score if report.quality_score else 0},percent",
        f"media_events,{len(report.media_summary.coverage_events)},count"
    ]
    
    csv_file.write_text('\n'.join(csv_lines))
    print(f"✅ CSV metrics saved: {csv_file}")
    
    # Markdown summary
    md_file = output_path / f"{report.flight_id}_summary.md"
    md_content = f"""# Flight Report Summary

**Flight ID:** {report.flight_id}  
**Generated:** {report.timestamp_generated.strftime('%Y-%m-%d %H:%M:%S UTC')}

## Flight Metrics
- **Max Altitude:** {report.flight_metrics.max_altitude if report.flight_metrics else 'N/A'} ft
- **Total Distance:** {report.flight_metrics.total_distance if report.flight_metrics else 'N/A'} miles  
- **Battery Consumed:** {report.flight_metrics.battery_consumed if report.flight_metrics else 'N/A'}%
- **GPS Quality:** {report.flight_metrics.gps_quality_avg if report.flight_metrics else 'N/A'} satellites

## Quality Assessment
- **Overall Score:** {report.quality_score.overall_score if report.quality_score else 'N/A':.1%}
- **Grade:** {report.quality_score.get_grade() if report.quality_score else 'N/A'}

## Bay Information
- **Bay ID:** {report.bay_mapping.bay_id if report.bay_mapping else 'Unknown'}
- **Confidence:** {report.bay_mapping.confidence_score if report.bay_mapping else 'N/A':.1%}

## Media & Events
- **Media Events:** {len(report.media_summary.coverage_events)}
- **Anomalies Detected:** {len(report.anomalies)}

---
*Generated by Drone Metadata Automation System*
"""
    
    md_file.write_text(md_content)
    print(f"✅ Markdown summary saved: {md_file}")
    
    print(f"\n📁 All outputs saved to: {output_path}")


def main():
    """Main demo function."""
    print("🚁 DRONE METADATA AUTOMATION SYSTEM - DEMO")
    print("=" * 60)
    print("This demo showcases the key capabilities of the system:")
    print("1. Directory scanning and data discovery")
    print("2. Multi-source data processing")
    print("3. Automated report generation")
    print("4. Multiple output formats")
    print()
    
    try:
        # Create sample data
        flight_dir = create_sample_data()
        
        # Demonstrate scanning
        scan_result = demonstrate_directory_scanning(flight_dir / "8B-7F")
        
        # Demonstrate processing  
        report = demonstrate_processing(flight_dir / "8B-7F")
        
        # Demonstrate outputs
        output_dir = flight_dir / "demo_outputs"
        demonstrate_output_formats(report, output_dir)
        
        print("\n🎉 DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"📁 Demo files location: {flight_dir}")
        print("💡 Try processing your own flight directories using:")
        print(f'   drone-metadata process "{flight_dir}"')
        print("📚 For more information, see the README.md file")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")


if __name__ == "__main__":
    main()
