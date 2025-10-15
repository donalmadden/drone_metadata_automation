"""
Mission Classifier
==================

This module provides intelligent classification of drone videos into mission types
based on file paths, metadata, and configuration files.

Phase 2 Implementation: Automatic categorization into box/safety/overview/survey missions.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from ..models import MissionType, MissionData, VideoAnalysisResult, GPSData

logger = logging.getLogger(__name__)


@dataclass
class ClassificationRule:
    """Single classification rule with pattern matching and confidence scoring."""
    
    name: str
    mission_type: MissionType
    
    # Pattern matching rules
    filename_patterns: List[str] = field(default_factory=list)
    directory_patterns: List[str] = field(default_factory=list)
    
    # GPS/metadata based rules  
    altitude_range: Optional[Tuple[float, float]] = None  # (min, max) in meters
    duration_range: Optional[Tuple[float, float]] = None  # (min, max) in seconds
    
    # DJI metadata rules
    dji_metadata_keywords: List[str] = field(default_factory=list)
    
    # Confidence scoring
    base_confidence: float = 0.5
    pattern_weight: float = 0.4
    metadata_weight: float = 0.3
    gps_weight: float = 0.3
    
    def evaluate_filename(self, filename: str) -> float:
        """Evaluate filename against patterns, return confidence score."""
        if not self.filename_patterns:
            return 0.0
            
        score = 0.0
        for pattern in self.filename_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                score = max(score, 0.8)  # High confidence for filename matches
                
        return score
    
    def evaluate_directory(self, directory_path: str) -> float:
        """Evaluate directory path against patterns, return confidence score."""
        if not self.directory_patterns:
            return 0.0
            
        score = 0.0
        for pattern in self.directory_patterns:
            if re.search(pattern, directory_path, re.IGNORECASE):
                score = max(score, 0.7)  # Good confidence for directory matches
                
        return score
    
    def evaluate_metadata(self, result: VideoAnalysisResult) -> float:
        """Evaluate video metadata, return confidence score."""
        score = 0.0
        
        # Check altitude range
        if self.altitude_range and result.gps_data and result.gps_data.altitude_meters:
            min_alt, max_alt = self.altitude_range
            altitude = result.gps_data.altitude_meters
            if min_alt <= altitude <= max_alt:
                score += 0.3
        
        # Check duration range
        if self.duration_range and result.video_metadata.duration_seconds:
            min_dur, max_dur = self.duration_range
            duration = result.video_metadata.duration_seconds
            if min_dur <= duration <= max_dur:
                score += 0.3
                
        # Check DJI metadata keywords
        if self.dji_metadata_keywords and result.dji_metadata:
            for keyword in self.dji_metadata_keywords:
                for key, value in result.dji_metadata.items():
                    if keyword.lower() in str(key).lower() or keyword.lower() in str(value).lower():
                        score += 0.2
                        break
        
        return min(score, 1.0)
    
    def calculate_confidence(self, filename: str, directory_path: str, 
                           result: VideoAnalysisResult) -> float:
        """Calculate overall confidence score for this rule."""
        filename_score = self.evaluate_filename(filename)
        directory_score = self.evaluate_directory(directory_path)
        metadata_score = self.evaluate_metadata(result)
        
        # Weighted combination
        total_score = (
            self.base_confidence +
            filename_score * self.pattern_weight +
            directory_score * self.pattern_weight +
            metadata_score * self.metadata_weight
        )
        
        return min(total_score, 1.0)


class MissionClassifier:
    """
    Intelligent mission classification system for drone videos.
    
    Classifies videos into mission types based on:
    - File path patterns (directory structure, filenames)
    - Video metadata (duration, GPS, technical specs)
    - DJI-specific metadata
    - User-defined classification rules
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.classification_rules = self._initialize_default_rules()
        self.manual_classifications = {}  # filename -> MissionType overrides
        
        # Load custom rules if provided
        if config and "classification_rules" in config:
            self._load_custom_rules(config["classification_rules"])
            
        logger.info(f"MissionClassifier initialized with {len(self.classification_rules)} rules")
    
    def _initialize_default_rules(self) -> List[ClassificationRule]:
        """Initialize default classification rules for BOX and SAFETY missions."""
        
        rules = []
        
        # BOX mission rules
        rules.append(ClassificationRule(
            name="Box Mission - Directory Pattern",
            mission_type=MissionType.BOX,
            directory_patterns=[r"box", r"container", r"cargo"],
            filename_patterns=[r"box", r"container"],
            altitude_range=(5.0, 50.0),  # Typical box inspection altitude
            duration_range=(30.0, 300.0),  # 30 seconds to 5 minutes
            base_confidence=0.7
        ))
        
        # SAFETY mission rules
        rules.append(ClassificationRule(
            name="Safety Mission - Directory Pattern",
            mission_type=MissionType.SAFETY,
            directory_patterns=[r"safety", r"inspection", r"hazard"],
            filename_patterns=[r"safety", r"inspection", r"hazard", r"check"],
            altitude_range=(2.0, 30.0),  # Lower altitude for safety checks
            duration_range=(60.0, 600.0),  # 1-10 minutes
            base_confidence=0.7
        ))
        
        # Bay-specific rules for BOX missions
        rules.append(ClassificationRule(
            name="Bay Box Analysis",
            mission_type=MissionType.BOX,
            directory_patterns=[r"\\d+[A-Z]-\\d+[A-Z]", r"\\d+[A-Z]"],  # e.g., 8B-7F, 8D
            base_confidence=0.5,
            pattern_weight=0.6  # Higher weight for bay patterns
        ))
        
        return rules
    
    def _load_custom_rules(self, custom_rules_config: Dict[str, Any]):
        """Load custom classification rules from configuration."""
        # Implementation for loading custom rules from config
        # This allows users to define their own classification patterns
        logger.info(f"Loading {len(custom_rules_config)} custom classification rules")
        pass
    
    def classify_video(self, result: VideoAnalysisResult, 
                      video_path: Optional[str] = None) -> MissionData:
        """
        Classify a single video into a mission type.
        
        Args:
            result: Video analysis result with metadata
            video_path: Optional full path to video file for directory analysis
            
        Returns:
            MissionData with classification results
        """
        filename = result.video_metadata.filename
        directory_path = str(Path(video_path).parent) if video_path else ""
        
        # Check for manual override
        if filename in self.manual_classifications:
            mission_type = self.manual_classifications[filename]
            return MissionData(
                mission_type=mission_type,
                classification_confidence=1.0,
                classification_method="manual_override",
                mission_notes=f"Manual classification override for {filename}"
            )
        
        # Evaluate all rules and find best match
        best_match = None
        best_confidence = 0.0
        
        for rule in self.classification_rules:
            confidence = rule.calculate_confidence(filename, directory_path, result)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = rule
        
        # Set minimum confidence threshold
        min_confidence = self.config.get("min_classification_confidence", 0.3)
        
        if best_match and best_confidence >= min_confidence:
            mission_type = best_match.mission_type
            method = f"rule:{best_match.name}"
        else:
            # Default to BOX if no confident match
            mission_type = MissionType.BOX
            method = "default_box"
            best_confidence = 0.3
        
        # Extract additional mission data
        mission_data = MissionData(
            mission_type=mission_type,
            classification_confidence=best_confidence,
            classification_method=method
        )
        
        # Try to extract bay designation from directory path
        bay_match = re.search(r'(\\d+[A-Z]-\\d+[A-Z]|\\d+[A-Z])', directory_path)
        if bay_match:
            mission_data.bay_designation = bay_match.group(1)
        
        # Extract flight parameters from metadata if available
        if result.gps_data and result.gps_data.altitude_meters:
            mission_data.max_altitude = result.gps_data.altitude_meters
            
        if result.video_metadata.duration_seconds:
            # Estimate flight distance (rough approximation)
            # Assume average speed of 10 mph for estimation
            duration_hours = result.video_metadata.duration_seconds / 3600.0
            mission_data.flight_distance = duration_hours * 10.0  # miles
        
        logger.info(f"Classified {filename} as {mission_type.value} "
                   f"(confidence: {best_confidence:.2f}, method: {method})")
        
        return mission_data
    
    def classify_batch(self, results: List[VideoAnalysisResult], 
                      video_paths: Optional[List[str]] = None) -> List[MissionData]:
        """
        Classify a batch of videos.
        
        Args:
            results: List of video analysis results
            video_paths: Optional list of video file paths
            
        Returns:
            List of MissionData classifications
        """
        if video_paths and len(video_paths) != len(results):
            logger.warning("Mismatch between results and paths count, proceeding without paths")
            video_paths = None
        
        classifications = []
        
        for i, result in enumerate(results):
            video_path = video_paths[i] if video_paths else None
            mission_data = self.classify_video(result, video_path)
            classifications.append(mission_data)
        
        # Log batch statistics
        mission_counts = {}
        for classification in classifications:
            mission_type = classification.mission_type.value
            mission_counts[mission_type] = mission_counts.get(mission_type, 0) + 1
        
        logger.info(f"Batch classification complete: {dict(mission_counts)}")
        
        return classifications
    
    def add_manual_classification(self, filename: str, mission_type: MissionType):
        """Add manual classification override for specific file."""
        self.manual_classifications[filename] = mission_type
        logger.info(f"Added manual classification: {filename} -> {mission_type.value}")
    
    def get_classification_statistics(self, classifications: List[MissionData]) -> Dict[str, Any]:
        """Generate statistics for a set of classifications."""
        
        total_count = len(classifications)
        if total_count == 0:
            return {}
        
        # Count by mission type
        mission_counts = {}
        confidence_sum = 0.0
        high_confidence_count = 0
        
        for classification in classifications:
            mission_type = classification.mission_type.value
            mission_counts[mission_type] = mission_counts.get(mission_type, 0) + 1
            confidence_sum += classification.classification_confidence
            
            if classification.classification_confidence >= 0.7:
                high_confidence_count += 1
        
        return {
            "total_videos": total_count,
            "mission_distribution": mission_counts,
            "average_confidence": confidence_sum / total_count,
            "high_confidence_percentage": (high_confidence_count / total_count) * 100,
            "unknown_count": mission_counts.get("unknown", 0),
            "classified_percentage": ((total_count - mission_counts.get("unknown", 0)) / total_count) * 100
        }
    
    def export_classifications(self, results: List[VideoAnalysisResult], 
                             classifications: List[MissionData],
                             output_path: str):
        """Export classifications to CSV file for review and editing."""
        
        import csv
        from pathlib import Path
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'filename', 'mission_type', 'confidence', 'method', 
                'bay_designation', 'duration_sec', 'altitude_m', 'notes'
            ])
            
            # Data
            for result, classification in zip(results, classifications):
                writer.writerow([
                    result.video_metadata.filename,
                    classification.mission_type.value,
                    f"{classification.classification_confidence:.3f}",
                    classification.classification_method or "",
                    classification.bay_designation or "",
                    result.video_metadata.duration_seconds or "",
                    classification.max_altitude or "",
                    classification.mission_notes or ""
                ])
        
        logger.info(f"Classifications exported to {output_file}")
    
    def get_classifier_info(self) -> Dict[str, Any]:
        """Get information about the classifier configuration."""
        
        rule_info = []
        for rule in self.classification_rules:
            rule_info.append({
                "name": rule.name,
                "mission_type": rule.mission_type.value,
                "filename_patterns": len(rule.filename_patterns),
                "directory_patterns": len(rule.directory_patterns),
                "base_confidence": rule.base_confidence
            })
        
        return {
            "total_rules": len(self.classification_rules),
            "manual_overrides": len(self.manual_classifications),
            "supported_mission_types": [mt.value for mt in MissionType],
            "rules": rule_info,
            "config": self.config
        }