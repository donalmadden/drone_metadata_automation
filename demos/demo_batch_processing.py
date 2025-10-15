#!/usr/bin/env python3
"""
Simple Demo: Phase 2 Batch Processing

This is a simplified test to demonstrate the batch processing capabilities.
"""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from drone_metadata.processing import BatchProcessor, BatchConfig


def simple_batch_test():
    """Run a simple batch processing test."""
    print("🚀 SIMPLE BATCH PROCESSING DEMO")
    print("=" * 50)
    
    # Configuration - conservative settings for testing
    config = BatchConfig(
        max_workers=1,  # Single worker to avoid issues
        timeout_per_video=60,  # 1 minute timeout
        retry_attempts=1,
        save_progress_interval=1,
        enable_resume=True,
        continue_on_error=True,
        overwrite_existing=True  # Overwrite for testing
    )
    
    # Paths
    test_paths = [r"C:\Users\donal\Downloads\aug_2025\8D"]
    output_dir = r"C:\Users\donal\drone_metadata_automation\simple_batch_output"
    
    print(f"📁 Input: {test_paths[0]}")
    print(f"📁 Output: {output_dir}")
    print(f"⚙️  Config: {config.max_workers} worker, overwrite enabled")
    
    # Initialize processor
    processor = BatchProcessor(config, output_dir)
    
    # Discover videos first
    video_files = processor.discover_videos(test_paths)
    print(f"🎬 Discovered {len(video_files)} videos:")
    for i, video in enumerate(video_files, 1):
        print(f"   {i}. {Path(video).name}")
    
    if not video_files:
        print("❌ No videos found")
        return
    
    try:
        # Process batch
        print(f"\n🔄 Starting batch processing...")
        batch_id = "simple_demo"
        
        progress = processor.process_batch(test_paths, batch_id)
        
        print(f"\n✅ Batch processing completed!")
        print(f"📊 Results:")
        print(f"   Total: {progress.total_videos}")
        print(f"   Completed: {progress.completed}")
        print(f"   Failed: {progress.failed}")
        print(f"   Success rate: {progress.success_rate:.1f}%")
        
        # Show generated files
        output_path = Path(output_dir)
        if output_path.exists():
            files = list(output_path.rglob("*.*"))
            print(f"\n📄 Generated {len(files)} files:")
            for f in files[:10]:  # Show first 10
                rel_path = f.relative_to(output_path)
                print(f"   📄 {rel_path} ({f.stat().st_size} bytes)")
            if len(files) > 10:
                print(f"   ... and {len(files)-10} more")
        
        # Show progress file content
        progress_file = output_path / "batch_progress.json"
        if progress_file.exists():
            print(f"\n📋 Progress file: {progress_file.stat().st_size} bytes")
        
        return True
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Batch processing interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Batch processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main demo function.""" 
    result = simple_batch_test()
    
    if result:
        print(f"\n🎉 Demo completed successfully!")
        print(f"\n💡 Next steps:")
        print(f"1. Check the output directory for all generated files")
        print(f"2. Look at thumbnails/ subdirectory for thumbnail images")  
        print(f"3. Review markdown files for video documentation")
        print(f"4. Examine CSV files for semantic data model")
        print(f"5. Check batch_progress.json for progress tracking")
    else:
        print(f"\n⚠️  Demo had issues - check the logs above")
    
    print(f"\n🔧 Manual testing command:")
    print(f"   processor = BatchProcessor(BatchConfig(max_workers=2), 'output_dir')")
    print(f"   progress = processor.process_batch(['video_directory'])")


if __name__ == "__main__":
    main()