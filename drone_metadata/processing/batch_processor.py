"""
Batch Processor
===============

Phase 2 batch processing capabilities with parallel processing, progress tracking,
error recovery, and resumption capabilities for processing multiple drone videos.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any, Tuple
import threading
from queue import Queue

from ..ingestion.video_metadata_parser import VideoMetadataParser
from ..analysis.mission_classifier import MissionClassifier
from ..formatters.base_formatter import FormatterConfig
from ..formatters.markdown_formatter import MarkdownFormatter
from ..formatters.thumbnail_generator import ThumbnailGenerator
from ..formatters.semantic_model_exporter import SemanticModelExporter
from ..models import VideoAnalysisResult, VideoMetadata, TechnicalSpecs, GPSData, VideoProcessingBatch

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch processing operations."""
    
    # Processing settings
    max_workers: int = 4
    timeout_per_video: int = 300  # seconds
    retry_attempts: int = 2
    retry_delay: float = 1.0  # seconds between retries
    
    # Progress tracking
    save_progress_interval: int = 10  # Save progress every N videos
    enable_progress_file: bool = True
    progress_file_name: str = "batch_progress.json"
    
    # Error handling
    continue_on_error: bool = True
    max_error_percentage: float = 50.0  # Stop if >50% of videos fail
    
    # Output settings
    overwrite_existing: bool = False
    separate_failed_videos: bool = True
    
    # Resume capabilities
    enable_resume: bool = True
    skip_completed: bool = True


@dataclass 
class VideoProcessingJob:
    """Individual video processing job."""
    
    video_path: str
    job_id: str
    status: str = "pending"  # pending, processing, completed, failed, skipped
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attempts: int = 0
    error_message: Optional[str] = None
    result: Optional[VideoAnalysisResult] = None
    output_files: List[str] = field(default_factory=list)
    
    @property
    def processing_time(self) -> Optional[timedelta]:
        """Get processing duration if available."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "video_path": self.video_path,
            "job_id": self.job_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "attempts": self.attempts,
            "error_message": self.error_message,
            "output_files": self.output_files,
            "processing_time": self.processing_time.total_seconds() if self.processing_time else None
        }


@dataclass
class BatchProgress:
    """Batch processing progress tracking."""
    
    batch_id: str
    total_videos: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    in_progress: int = 0
    
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    jobs: Dict[str, VideoProcessingJob] = field(default_factory=dict)
    
    @property
    def processed(self) -> int:
        """Total processed (completed + failed + skipped)."""
        return self.completed + self.failed + self.skipped
    
    @property
    def remaining(self) -> int:
        """Videos remaining to process."""
        return self.total_videos - self.processed - self.in_progress
    
    @property
    def success_rate(self) -> float:
        """Success rate percentage."""
        if self.processed == 0:
            return 0.0
        return (self.completed / self.processed) * 100
    
    @property
    def completion_percentage(self) -> float:
        """Overall completion percentage."""
        if self.total_videos == 0:
            return 0.0
        return (self.processed / self.total_videos) * 100
    
    def estimate_completion_time(self):
        """Estimate completion time based on current progress."""
        if self.processed == 0 or not self.start_time:
            return
            
        elapsed = datetime.now() - self.start_time
        rate = self.processed / elapsed.total_seconds()  # videos per second
        
        if rate > 0:
            remaining_seconds = self.remaining / rate
            self.estimated_completion = datetime.now() + timedelta(seconds=remaining_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "batch_id": self.batch_id,
            "total_videos": self.total_videos,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "in_progress": self.in_progress,
            "processed": self.processed,
            "remaining": self.remaining,
            "success_rate": self.success_rate,
            "completion_percentage": self.completion_percentage,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "jobs": {job_id: job.to_dict() for job_id, job in self.jobs.items()}
        }


class BatchProcessor:
    """
    Phase 2 batch processor with parallel processing, progress tracking,
    error recovery, and resumption capabilities.
    """
    
    def __init__(self, config: BatchConfig, output_dir: str):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.video_parser = VideoMetadataParser(require_all_dependencies=False)
        self.mission_classifier = MissionClassifier()
        
        # Progress tracking
        self.progress_file = self.output_dir / self.config.progress_file_name
        self.progress_lock = threading.Lock()
        
        # Progress callback for external monitoring
        self.progress_callback: Optional[Callable[[BatchProgress], None]] = None
        
        logger.info(f"BatchProcessor initialized with {self.config.max_workers} workers")
    
    def set_progress_callback(self, callback: Callable[[BatchProgress], None]):
        """Set callback function for progress updates."""
        self.progress_callback = callback
    
    def discover_videos(self, input_paths: List[str]) -> List[str]:
        """
        Discover all video files from input paths.
        
        Args:
            input_paths: List of file or directory paths
            
        Returns:
            List of video file paths
        """
        video_extensions = {'.mp4', '.MP4', '.mov', '.MOV', '.avi', '.AVI'}
        video_files = []
        
        for path_str in input_paths:
            path = Path(path_str)
            
            if path.is_file() and path.suffix in video_extensions:
                video_files.append(str(path))
            elif path.is_dir():
                # Recursively find video files
                for ext in video_extensions:
                    video_files.extend([str(p) for p in path.rglob(f"*{ext}")])
        
        # Remove duplicates and sort
        video_files = sorted(list(set(video_files)))
        logger.info(f"Discovered {len(video_files)} video files")
        
        return video_files
    
    def load_progress(self, batch_id: str) -> Optional[BatchProgress]:
        """Load existing progress from file."""
        if not self.progress_file.exists():
            return None
            
        try:
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                
            if data.get('batch_id') != batch_id:
                logger.warning(f"Progress file batch_id mismatch: {data.get('batch_id')} != {batch_id}")
                return None
            
            # Reconstruct BatchProgress object
            progress = BatchProgress(batch_id=batch_id)
            progress.total_videos = data.get('total_videos', 0)
            progress.completed = data.get('completed', 0)
            progress.failed = data.get('failed', 0)
            progress.skipped = data.get('skipped', 0)
            progress.in_progress = data.get('in_progress', 0)
            
            if data.get('start_time'):
                progress.start_time = datetime.fromisoformat(data['start_time'])
            if data.get('last_update'):
                progress.last_update = datetime.fromisoformat(data['last_update'])
            
            # Reconstruct jobs
            for job_id, job_data in data.get('jobs', {}).items():
                job = VideoProcessingJob(
                    video_path=job_data['video_path'],
                    job_id=job_id,
                    status=job_data.get('status', 'pending'),
                    attempts=job_data.get('attempts', 0),
                    error_message=job_data.get('error_message'),
                    output_files=job_data.get('output_files', [])
                )
                
                if job_data.get('start_time'):
                    job.start_time = datetime.fromisoformat(job_data['start_time'])
                if job_data.get('end_time'):
                    job.end_time = datetime.fromisoformat(job_data['end_time'])
                    
                progress.jobs[job_id] = job
            
            logger.info(f"Loaded progress: {progress.processed}/{progress.total_videos} videos processed")
            return progress
            
        except Exception as e:
            logger.error(f"Failed to load progress file: {e}")
            return None
    
    def save_progress(self, progress: BatchProgress):
        """Save current progress to file."""
        if not self.config.enable_progress_file:
            return
            
        with self.progress_lock:
            try:
                progress.last_update = datetime.now()
                with open(self.progress_file, 'w') as f:
                    json.dump(progress.to_dict(), f, indent=2)
                logger.debug("Progress saved")
            except Exception as e:
                logger.error(f"Failed to save progress: {e}")
    
    def _process_single_video(self, job: VideoProcessingJob) -> VideoProcessingJob:
        """
        Process a single video with error handling and retries.
        
        Args:
            job: Video processing job
            
        Returns:
            Updated job with results
        """
        job.start_time = datetime.now()
        job.status = "processing"
        
        for attempt in range(1, self.config.retry_attempts + 1):
            job.attempts = attempt
            
            try:
                logger.info(f"Processing {Path(job.video_path).name} (attempt {attempt})")
                
                # Step 1: Parse video metadata
                result = self.video_parser.parse_video(job.video_path)
                
                if not result.success:
                    raise Exception(f"Video parsing failed: {result.errors}")
                
                # Step 2: Convert to VideoAnalysisResult
                analysis_result = self._convert_parser_result(result, job.video_path)
                
                # Step 3: Classify mission
                mission_data = self.mission_classifier.classify_video(analysis_result, job.video_path)
                analysis_result.mission_data = mission_data
                
                # Step 4: Generate outputs
                output_files = self._generate_outputs(analysis_result)
                
                # Success
                job.status = "completed"
                job.result = analysis_result
                job.output_files = output_files
                job.end_time = datetime.now()
                
                logger.info(f"Successfully processed {Path(job.video_path).name} in {job.processing_time}")
                return job
                
            except Exception as e:
                error_msg = f"Attempt {attempt} failed: {str(e)}"
                logger.warning(error_msg)
                job.error_message = error_msg
                
                if attempt < self.config.retry_attempts:
                    time.sleep(self.config.retry_delay * attempt)  # Exponential backoff
                else:
                    # Final failure
                    job.status = "failed"
                    job.end_time = datetime.now()
                    logger.error(f"Failed to process {Path(job.video_path).name} after {attempt} attempts")
        
        return job
    
    def _convert_parser_result(self, parser_result, video_path: str) -> VideoAnalysisResult:
        """Convert parser result to VideoAnalysisResult."""
        
        # Extract duration from FFmpeg format info
        duration_seconds = 0.0
        if parser_result.ffmpeg_metadata and 'ffmpeg_format' in parser_result.ffmpeg_metadata:
            duration_seconds = float(parser_result.ffmpeg_metadata['ffmpeg_format'].get('duration', 0))
        
        video_metadata = VideoMetadata(
            filename=Path(video_path).name,
            filepath=video_path,
            filesize_bytes=parser_result.file_info.get('filesize_bytes', 0),
            filesize_mb=parser_result.file_info.get('filesize_mb', 0),
            duration_seconds=duration_seconds
        )
        
        technical_specs = TechnicalSpecs()
        if parser_result.ffmpeg_metadata and 'video_streams' in parser_result.ffmpeg_metadata:
            if parser_result.ffmpeg_metadata['video_streams']:
                video_stream = parser_result.ffmpeg_metadata['video_streams'][0]
                technical_specs.width = video_stream.get('width')
                technical_specs.height = video_stream.get('height')
                technical_specs.framerate = video_stream.get('avg_frame_rate')
                technical_specs.video_codec = video_stream.get('codec_name')
        
        gps_data = None
        if parser_result.gps_data:
            gps_data = GPSData(
                latitude_decimal=parser_result.gps_data.get('latitude'),
                longitude_decimal=parser_result.gps_data.get('longitude'),
                altitude_meters=parser_result.gps_data.get('altitude')
            )
        
        return VideoAnalysisResult(
            video_metadata=video_metadata,
            technical_specs=technical_specs,
            gps_data=gps_data,
            dji_metadata=parser_result.dji_specific.get('dji_specific', {}),
            extraction_success=True
        )
    
    def _generate_outputs(self, result: VideoAnalysisResult) -> List[str]:
        """Generate all output files for a video."""
        formatter_config = FormatterConfig(
            output_directory=str(self.output_dir),
            overwrite_existing=self.config.overwrite_existing
        )
        
        output_files = []
        
        try:
            # Generate thumbnail
            thumbnail_gen = ThumbnailGenerator(formatter_config)
            thumbnail_paths = thumbnail_gen.format_single_video(result)
            output_files.extend([str(p) for p in thumbnail_paths])
            
            # Generate markdown
            markdown_gen = MarkdownFormatter(formatter_config)  
            markdown_paths = markdown_gen.format_single_video(result)
            output_files.extend([str(p) for p in markdown_paths])
            
            # Generate semantic model (for individual videos, just create/append to tables)
            semantic_gen = SemanticModelExporter(formatter_config)
            csv_paths = semantic_gen.format_single_video(result)
            output_files.extend([str(p) for p in csv_paths])
            
        except Exception as e:
            logger.warning(f"Some output generation failed for {result.video_metadata.filename}: {e}")
            # Continue with partial outputs
        
        return output_files
    
    def _update_progress(self, progress: BatchProgress, job: VideoProcessingJob):
        """Update progress counters based on job status."""
        with self.progress_lock:
            if job.status == "completed":
                progress.completed += 1
            elif job.status == "failed":
                progress.failed += 1
            elif job.status == "skipped":
                progress.skipped += 1
            
            progress.in_progress -= 1
            progress.estimate_completion_time()
            
            # Save progress periodically
            if progress.processed % self.config.save_progress_interval == 0:
                self.save_progress(progress)
            
            # Call progress callback if set
            if self.progress_callback:
                self.progress_callback(progress)
    
    def process_batch(self, input_paths: List[str], batch_id: Optional[str] = None) -> BatchProgress:
        """
        Process a batch of videos with parallel processing and progress tracking.
        
        Args:
            input_paths: List of video files or directories
            batch_id: Optional batch identifier for resume capability
            
        Returns:
            BatchProgress with final results
        """
        if not batch_id:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Discover videos
        video_files = self.discover_videos(input_paths)
        if not video_files:
            raise ValueError("No video files found in input paths")
        
        # Load or create progress
        progress = None
        if self.config.enable_resume:
            progress = self.load_progress(batch_id)
        
        if not progress:
            progress = BatchProgress(batch_id=batch_id, total_videos=len(video_files))
            progress.start_time = datetime.now()
            
            # Create jobs
            for i, video_path in enumerate(video_files):
                job_id = f"job_{i:04d}"
                job = VideoProcessingJob(video_path=video_path, job_id=job_id)
                progress.jobs[job_id] = job
        
        logger.info(f"Starting batch {batch_id}: {progress.total_videos} videos, {progress.processed} already processed")
        
        # Filter jobs to process
        jobs_to_process = []
        for job in progress.jobs.values():
            if job.status in ["pending", "failed"] or (job.status == "failed" and job.attempts < self.config.retry_attempts):
                jobs_to_process.append(job)
            elif job.status in ["completed", "skipped"] and self.config.skip_completed:
                continue
            else:
                jobs_to_process.append(job)
        
        if not jobs_to_process:
            logger.info("All videos already processed, nothing to do")
            return progress
        
        logger.info(f"Processing {len(jobs_to_process)} videos with {self.config.max_workers} workers")
        
        # Process videos in parallel
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit jobs
            future_to_job = {}
            for job in jobs_to_process:
                job.status = "processing"
                progress.in_progress += 1
                future = executor.submit(self._process_single_video, job)
                future_to_job[future] = job
            
            # Process completed jobs
            for future in as_completed(future_to_job, timeout=self.config.timeout_per_video * len(jobs_to_process)):
                job = future_to_job[future]
                
                try:
                    updated_job = future.result()
                    progress.jobs[updated_job.job_id] = updated_job
                    self._update_progress(progress, updated_job)
                    
                    # Check error rate
                    if progress.processed > 10 and progress.success_rate < (100 - self.config.max_error_percentage):
                        logger.error(f"Error rate too high: {100-progress.success_rate:.1f}% > {self.config.max_error_percentage}%")
                        if not self.config.continue_on_error:
                            logger.error("Stopping batch processing due to high error rate")
                            break
                    
                except Exception as e:
                    logger.error(f"Unexpected error processing job {job.job_id}: {e}")
                    job.status = "failed"
                    job.error_message = str(e)
                    job.end_time = datetime.now()
                    self._update_progress(progress, job)
        
        # Final progress save
        self.save_progress(progress)
        
        logger.info(f"Batch {batch_id} completed: {progress.completed} successful, {progress.failed} failed, {progress.skipped} skipped")
        
        return progress
    
    def get_batch_summary(self, progress: BatchProgress) -> Dict[str, Any]:
        """Generate a comprehensive batch processing summary."""
        
        total_time = None
        if progress.start_time:
            end_time = progress.last_update or datetime.now()
            total_time = end_time - progress.start_time
        
        # Processing time statistics
        processing_times = []
        successful_jobs = [job for job in progress.jobs.values() if job.status == "completed" and job.processing_time]
        
        if successful_jobs:
            processing_times = [job.processing_time.total_seconds() for job in successful_jobs]
            avg_time = sum(processing_times) / len(processing_times)
            min_time = min(processing_times)
            max_time = max(processing_times)
        else:
            avg_time = min_time = max_time = 0
        
        # Error analysis
        error_types = {}
        for job in progress.jobs.values():
            if job.status == "failed" and job.error_message:
                error_key = job.error_message.split(":")[0]  # Get first part before colon
                error_types[error_key] = error_types.get(error_key, 0) + 1
        
        return {
            "batch_id": progress.batch_id,
            "summary": {
                "total_videos": progress.total_videos,
                "completed": progress.completed,
                "failed": progress.failed,
                "skipped": progress.skipped,
                "success_rate": progress.success_rate,
                "completion_percentage": progress.completion_percentage
            },
            "timing": {
                "total_time_seconds": total_time.total_seconds() if total_time else 0,
                "average_time_per_video": avg_time,
                "min_time_per_video": min_time,
                "max_time_per_video": max_time
            },
            "errors": {
                "error_types": error_types,
                "failed_jobs": [
                    {
                        "video": Path(job.video_path).name,
                        "error": job.error_message,
                        "attempts": job.attempts
                    }
                    for job in progress.jobs.values() 
                    if job.status == "failed"
                ]
            }
        }