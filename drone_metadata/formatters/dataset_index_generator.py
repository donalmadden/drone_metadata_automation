"""
Dataset Index Generator
=======================

This module provides the DatasetIndexGenerator class for generating
master dataset index files and documentation similar to the 
DATASET_INDEX.md file in Pilot04_Field_Test_April_25.
"""

from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .base_formatter import BaseFormatter, FormatterError
from ..models import VideoAnalysisResult, VideoProcessingBatch, MissionType


class DatasetIndexGenerator(BaseFormatter):
    """
    Formatter for generating master dataset index files and documentation.
    
    This formatter creates comprehensive dataset documentation including:
    - DATASET_INDEX.md (master overview file)
    - README.md files for mission directories
    - Statistical summaries
    - File inventories
    - Processing reports
    
    Note: This is a basic implementation for Phase 1.
    Full implementation will be expanded in Phase 2.
    """
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return [".md", ".txt"]
    
    def format_single_video(self, result: VideoAnalysisResult) -> List[Path]:
        """
        Generate dataset index for a single video.
        
        Args:
            result: Video analysis result to format
            
        Returns:
            List of paths to generated documentation files
        """
        # For single videos, we'll create a simple dataset summary
        return self.format_batch(VideoProcessingBatch(
            batch_id="single_video",
            processing_start=datetime.now(),
            video_results=[result]
        ))
    
    def format_batch(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Generate comprehensive dataset index for a batch of videos.
        
        Args:
            batch: Batch of video analysis results to format
            
        Returns:
            List of paths to generated documentation files
        """
        if not batch.video_results:
            return []
        
        self._log_processing_start("dataset index generation", f"batch of {len(batch.video_results)} videos")
        
        try:
            output_paths = []
            
            # Generate main dataset index
            index_path = self._generate_dataset_index(batch)
            if index_path:
                output_paths.append(index_path)
            
            # Generate mission-specific README files
            mission_readmes = self._generate_mission_readmes(batch)
            output_paths.extend(mission_readmes)
            
            # Generate processing report
            report_path = self._generate_processing_report(batch)
            if report_path:
                output_paths.append(report_path)
            
            self._log_processing_complete("dataset index generation", "batch", Path(self.config.output_directory))
            return output_paths
            
        except Exception as e:
            error_msg = f"Failed to generate dataset index: {str(e)}"
            self._log_processing_error("dataset index generation", "batch", error_msg)
            raise FormatterError(error_msg)
    
    def _generate_dataset_index(self, batch: VideoProcessingBatch) -> Path:
        """
        Generate the main DATASET_INDEX.md file.
        
        Args:
            batch: Batch of video analysis results
            
        Returns:
            Path to generated DATASET_INDEX.md file
        """
        index_path = self._get_output_path("DATASET_INDEX.md")
        
        # Check if file exists and handle accordingly
        if self._check_file_exists(index_path):
            return index_path
        
        # Calculate statistics
        stats = self._calculate_dataset_statistics(batch.video_results)
        
        # Build markdown content
        lines = []
        
        # Header
        lines.append("# Drone Video Dataset Index")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Total Videos**: {len(batch.video_results)}")
        lines.append(f"**Processing Success Rate**: {batch.get_success_rate():.1f}%")
        lines.append("")
        
        # Dataset Overview
        lines.append("## Dataset Overview")
        lines.append("")
        lines.append("This dataset contains drone inspection videos with extracted metadata,")
        lines.append("GPS coordinates, technical specifications, and mission classifications.")
        lines.append("")
        
        # Statistics Summary
        lines.append("## Statistics Summary")
        lines.append("")
        lines.append(f"- **Total Duration**: {stats['total_duration']}")
        lines.append(f"- **Total File Size**: {stats['total_size_mb']:.2f} MB")
        lines.append(f"- **Average File Size**: {stats['avg_size_mb']:.2f} MB")
        lines.append(f"- **Videos with GPS**: {stats['videos_with_gps']} ({stats['gps_percentage']:.1f}%)")
        lines.append(f"- **Unique Resolutions**: {len(stats['resolutions'])}")
        lines.append("")
        
        # Mission Breakdown
        if stats['missions']:
            lines.append("## Mission Breakdown")
            lines.append("")
            for mission_type, count in stats['missions'].items():
                percentage = (count / len(batch.video_results)) * 100
                lines.append(f"- **{mission_type.title()}**: {count} videos ({percentage:.1f}%)")
            lines.append("")
        
        # Technical Specifications
        lines.append("## Technical Specifications")
        lines.append("")
        lines.append("### Resolutions")
        for resolution, count in stats['resolutions'].items():
            lines.append(f"- **{resolution}**: {count} videos")
        lines.append("")
        
        if stats['codecs']:
            lines.append("### Video Codecs")
            for codec, count in stats['codecs'].items():
                lines.append(f"- **{codec}**: {count} videos")
            lines.append("")
        
        # File Inventory
        lines.append("## File Inventory")
        lines.append("")
        lines.append("### Video Files")
        lines.append("")
        
        for result in batch.video_results:
            video = result.video_metadata
            duration = video.get_duration_formatted()
            size = f"{video.filesize_mb:.1f}MB"
            mission = result.mission_data.mission_type.value if result.mission_data else "unknown"
            gps_status = "GPS" if result.has_gps() else "No GPS"
            
            lines.append(f"- `{video.filename}` - {duration}, {size}, {mission}, {gps_status}")
        
        lines.append("")
        
        # Processing Information
        lines.append("## Processing Information")
        lines.append("")
        lines.append(f"- **Batch ID**: {batch.batch_id}")
        lines.append(f"- **Processing Start**: {batch.processing_start.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if batch.processing_end:
            duration = batch.get_processing_duration()
            lines.append(f"- **Processing End**: {batch.processing_end.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"- **Total Processing Time**: {duration.total_seconds():.2f} seconds")
        
        lines.append(f"- **Successful Extractions**: {batch.successful_count}")
        lines.append(f"- **Failed Extractions**: {batch.failed_count}")
        lines.append("")
        
        # Errors and Warnings
        if batch.batch_errors:
            lines.append("## Processing Errors")
            lines.append("")
            for error in batch.batch_errors:
                lines.append(f"- {error}")
            lines.append("")
        
        if batch.batch_warnings:
            lines.append("## Processing Warnings")
            lines.append("")
            for warning in batch.batch_warnings:
                lines.append(f"- {warning}")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This dataset index was generated by drone_metadata_automation*")
        lines.append("*For individual video documentation, see the corresponding .md files*")
        
        # Write to file
        content = "\n".join(lines)
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return index_path
    
    def _generate_mission_readmes(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Generate README.md files for each mission type.
        
        Args:
            batch: Batch of video analysis results
            
        Returns:
            List of paths to generated README files
        """
        mission_files = []
        
        # Group videos by mission type
        missions = {}
        for result in batch.video_results:
            if result.mission_data:
                mission_type = result.mission_data.mission_type
            else:
                mission_type = MissionType.UNKNOWN
            
            if mission_type not in missions:
                missions[mission_type] = []
            missions[mission_type].append(result)
        
        # Generate README for each mission
        for mission_type, results in missions.items():
            readme_path = self._get_output_path(f"{mission_type.value}_README.md")
            
            if self._check_file_exists(readme_path):
                mission_files.append(readme_path)
                continue
            
            # Create mission-specific README content
            content = self._generate_mission_readme_content(mission_type, results)
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            mission_files.append(readme_path)
        
        return mission_files
    
    def _generate_mission_readme_content(self, mission_type: MissionType, results: List[VideoAnalysisResult]) -> str:
        """Generate README content for a specific mission type."""
        lines = []
        
        # Header
        lines.append(f"# {mission_type.value.title()} Mission Videos")
        lines.append("")
        lines.append(f"This directory contains {len(results)} videos classified as '{mission_type.value}' missions.")
        lines.append("")
        
        # Mission statistics
        total_duration = sum(r.video_metadata.duration_seconds or 0 for r in results)
        total_size = sum(r.video_metadata.filesize_mb for r in results)
        gps_count = sum(1 for r in results if r.has_gps())
        
        mins = int(total_duration // 60)
        secs = int(total_duration % 60)
        
        lines.append("## Mission Statistics")
        lines.append("")
        lines.append(f"- **Video Count**: {len(results)}")
        lines.append(f"- **Total Duration**: {mins}m {secs}s")
        lines.append(f"- **Total Size**: {total_size:.2f} MB")
        lines.append(f"- **Videos with GPS**: {gps_count} ({(gps_count/len(results)*100):.1f}%)")
        lines.append("")
        
        # Video listing
        lines.append("## Video Files")
        lines.append("")
        
        for result in results:
            video = result.video_metadata
            duration = video.get_duration_formatted()
            size = f"{video.filesize_mb:.1f}MB"
            gps_status = "GPS" if result.has_gps() else "No GPS"
            
            lines.append(f"### {video.filename}")
            lines.append("")
            lines.append(f"- **Duration**: {duration}")
            lines.append(f"- **Size**: {size}")
            lines.append(f"- **GPS**: {gps_status}")
            
            if result.technical_specs.width and result.technical_specs.height:
                lines.append(f"- **Resolution**: {result.technical_specs.width}x{result.technical_specs.height}")
            
            lines.append("")
        
        lines.append("---")
        lines.append("")
        lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines)
    
    def _generate_processing_report(self, batch: VideoProcessingBatch) -> Path:
        """
        Generate a detailed processing report.
        
        Args:
            batch: Batch of video analysis results
            
        Returns:
            Path to generated processing report
        """
        report_path = self._get_output_path("PROCESSING_REPORT.txt")
        
        if self._check_file_exists(report_path):
            return report_path
        
        lines = []
        lines.append("DRONE METADATA PROCESSING REPORT")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Batch ID: {batch.batch_id}")
        lines.append("")
        
        # Summary
        lines.append("PROCESSING SUMMARY")
        lines.append("-" * 20)
        lines.append(f"Total Videos: {len(batch.video_results)}")
        lines.append(f"Successful: {batch.successful_count}")
        lines.append(f"Failed: {batch.failed_count}")
        lines.append(f"Success Rate: {batch.get_success_rate():.1f}%")
        lines.append("")
        
        # Detailed results
        lines.append("DETAILED RESULTS")
        lines.append("-" * 20)
        
        for i, result in enumerate(batch.video_results, 1):
            video = result.video_metadata
            lines.append(f"{i:2d}. {video.filename}")
            lines.append(f"    Status: {'SUCCESS' if result.extraction_success else 'FAILED'}")
            lines.append(f"    Size: {video.filesize_mb:.2f} MB")
            lines.append(f"    Duration: {video.get_duration_formatted()}")
            
            if result.extraction_errors:
                lines.append(f"    Errors: {len(result.extraction_errors)}")
                for error in result.extraction_errors[:2]:  # Show first 2 errors
                    lines.append(f"      - {error}")
            
            lines.append("")
        
        # Write report
        content = "\n".join(lines)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return report_path
    
    def _calculate_dataset_statistics(self, results: List[VideoAnalysisResult]) -> Dict[str, Any]:
        """Calculate comprehensive dataset statistics."""
        stats = {
            'total_duration': 0,
            'total_size_mb': 0,
            'avg_size_mb': 0,
            'videos_with_gps': 0,
            'gps_percentage': 0,
            'resolutions': {},
            'codecs': {},
            'missions': {}
        }
        
        total_duration_seconds = 0
        
        for result in results:
            video = result.video_metadata
            specs = result.technical_specs
            
            # Duration and size
            if video.duration_seconds:
                total_duration_seconds += video.duration_seconds
            stats['total_size_mb'] += video.filesize_mb
            
            # GPS
            if result.has_gps():
                stats['videos_with_gps'] += 1
            
            # Resolutions
            if specs.width and specs.height:
                resolution = f"{specs.width}x{specs.height}"
                stats['resolutions'][resolution] = stats['resolutions'].get(resolution, 0) + 1
            
            # Codecs
            if specs.video_codec:
                codec = specs.video_codec
                stats['codecs'][codec] = stats['codecs'].get(codec, 0) + 1
            
            # Missions
            if result.mission_data:
                mission = result.mission_data.mission_type.value
                stats['missions'][mission] = stats['missions'].get(mission, 0) + 1
        
        # Calculate derived statistics
        mins = int(total_duration_seconds // 60)
        secs = int(total_duration_seconds % 60)
        stats['total_duration'] = f"{mins}m {secs}s"
        
        if results:
            stats['avg_size_mb'] = stats['total_size_mb'] / len(results)
            stats['gps_percentage'] = (stats['videos_with_gps'] / len(results)) * 100
        
        return stats
    
    def get_formatter_info(self) -> dict:
        """Get information about this formatter."""
        info = super().get_formatter_info()
        info.update({
            "phase": "Phase 1 (Basic Implementation)",
            "generated_files": [
                "DATASET_INDEX.md",
                "{mission}_README.md files",
                "PROCESSING_REPORT.txt"
            ],
            "future_features": [
                "Interactive HTML reports",
                "Geographic visualization maps",
                "Statistical charts and graphs",
                "Export to multiple formats",
                "Template customization",
                "Automated report scheduling"
            ]
        })
        return info