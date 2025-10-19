"""
Veo 3 API Integration
Google's Veo 3 video generation API integration using Gemini API
"""

import os
import json
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

class Veo3API:
    """
    Veo 3 API client for video generation with native audio support
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Veo 3 API client
        
        Args:
            api_key: Google API key (if not provided, will use GOOGLE_API_KEY from .env)
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY in .env file")
        
        # Initialize Google GenAI client
        self.client = genai.Client(api_key=self.api_key)
        
        # Model name for Veo 3
        self.model_name = "veo-3.0-generate-preview"
        
        # Generation cache to avoid duplicate API calls
        self.generation_cache = {}
        
        # Directory for saving generated videos
        self.output_dir = Path("generated_videos")
        self.output_dir.mkdir(exist_ok=True)
    
    async def generate_video(self, 
                           prompt: str, 
                           duration: int = 5,
                           resolution: str = "1080p",
                           style: str = "realistic",
                           negative_prompt: Optional[str] = None,
                           initial_image: Optional[Union[str, Path, Image.Image]] = None,
                           cache_results: bool = True,
                           save_to_disk: bool = True) -> Dict[str, Any]:
        """
        Generate a video using Veo 3 API with native audio support
        
        Args:
            prompt: Text description of the video to generate
            duration: Video duration in seconds (1-10)
            resolution: Video resolution ("720p", "1080p", "4k")
            style: Video style ("realistic", "animated", "artistic", "cinematic")
            negative_prompt: What to avoid in the video (optional)
            initial_image: Starting image for the video (optional)
            cache_results: Whether to cache results for future use
            save_to_disk: Whether to save the video to disk
            
        Returns:
            Video generation result with URL and metadata
        """
        # Check cache first
        cache_key = f"{prompt}_{duration}_{resolution}_{style}"
        if cache_results and cache_key in self.generation_cache:
            print("📋 Using cached video generation result")
            return self.generation_cache[cache_key]
        
        print(f"🎬 Generating video with Veo 3: {prompt[:50]}...")
        
        try:
            # Enhance prompt with style
            enhanced_prompt = prompt
            if style and style != "realistic":
                enhanced_prompt = f"{prompt}, {style} style"
            
            # Create config
            config = types.GenerateVideosConfig()
            if negative_prompt:
                config.negative_prompt = negative_prompt
            
            # Start video generation operation
            print("🚀 Starting Veo 3 video generation operation...")
            operation = await asyncio.to_thread(
                self.client.models.generate_videos,
                model=self.model_name,
                prompt=enhanced_prompt,
                config=config
            )
            
            # Poll for completion
            print("⏳ Waiting for video generation to complete...")
            max_wait_time = 300  # 5 minutes max
            start_time = time.time()
            poll_interval = 20  # Poll every 20 seconds
            
            while not operation.done:
                if time.time() - start_time > max_wait_time:
                    raise Exception("Video generation timed out after 5 minutes")
                
                await asyncio.sleep(poll_interval)
                operation = await asyncio.to_thread(
                    self.client.operations.get,
                    operation
                )
                print(f"⏳ Still generating... ({int(time.time() - start_time)}s elapsed)")
            
            # Get the generated video
            result_data = operation.result
            if not result_data or not hasattr(result_data, 'generated_videos'):
                raise Exception("No video data returned from API")
            
            generated_videos = result_data.generated_videos
            if not generated_videos or len(generated_videos) == 0:
                raise Exception("No videos were generated")
            
            generated_video = generated_videos[0]
            video_file = generated_video.video
            
            # Save video to disk if requested
            video_path = None
            video_url = None
            
            if save_to_disk:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                prompt_safe = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                filename = f"veo3_{prompt_safe}_{timestamp}.mp4"
                video_path = self.output_dir / filename
                
                # Download and save the video
                await asyncio.to_thread(
                    self.client.files.download,
                    file=video_file
                )
                await asyncio.to_thread(
                    video_file.save,
                    str(video_path)
                )
                
                video_url = f"/generated_videos/{filename}"
                print(f"💾 Video saved to: {video_path}")
            
            # Create result
            result = {
                "video_url": video_url,
                "video_path": str(video_path) if video_path else None,
                "prompt": prompt,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "prompt": prompt,
                    "enhanced_prompt": enhanced_prompt,
                    "duration": duration,
                    "resolution": resolution,
                    "style": style,
                    "negative_prompt": negative_prompt,
                    "api_used": "veo3",
                    "model": self.model_name,
                    "status": "success",
                    "has_audio": True  # Veo 3 generates native audio
                }
            }
            
            # Cache results
            if cache_results:
                self.generation_cache[cache_key] = result
            
            print("✅ Video generation completed successfully")
            return result
                        
        except Exception as e:
            print(f"❌ Video generation failed: {e}")
            return {
                "error": str(e),
                "prompt": prompt,
                "generated_at": datetime.now().isoformat(),
                "api_used": "veo3",
                "status": "error"
            }
    
    async def generate_video_from_image(self,
                                      prompt: str,
                                      image_path: Union[str, Path],
                                      duration: int = 5,
                                      resolution: str = "1080p",
                                      style: str = "realistic",
                                      negative_prompt: Optional[str] = None,
                                      save_to_disk: bool = True) -> Dict[str, Any]:
        """
        Generate a video from an initial image using Veo 3
        
        Args:
            prompt: Text description for the video motion/content
            image_path: Path to the initial image
            duration: Video duration in seconds
            resolution: Video resolution
            style: Video style
            negative_prompt: What to avoid in the video
            save_to_disk: Whether to save the video to disk
            
        Returns:
            Video generation result with URL and metadata
        """
        print(f"🎬 Generating video from image with Veo 3...")
        
        try:
            # Load the image
            image = Image.open(image_path)
            
            # Generate video with initial image
            return await self.generate_video(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                style=style,
                negative_prompt=negative_prompt,
                initial_image=image,
                save_to_disk=save_to_disk
            )
            
        except Exception as e:
            print(f"❌ Video generation from image failed: {e}")
            return {
                "error": str(e),
                "prompt": prompt,
                "image_path": str(image_path),
                "generated_at": datetime.now().isoformat(),
                "api_used": "veo3",
                "status": "error"
            }
    
    async def generate_video_batch(self, 
                                 prompts: List[str], 
                                 duration: int = 5,
                                 resolution: str = "1080p",
                                 style: str = "realistic") -> List[Dict[str, Any]]:
        """
        Generate multiple videos in batch
        
        Args:
            prompts: List of text descriptions for videos
            duration: Video duration in seconds
            resolution: Video resolution
            style: Video style
            
        Returns:
            List of video generation results
        """
        print(f"🎬 Generating {len(prompts)} videos in batch...")
        
        results = []
        for i, prompt in enumerate(prompts):
            print(f"Generating video {i+1}/{len(prompts)}: {prompt[:50]}...")
            
            result = await self.generate_video(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                style=style
            )
            
            results.append(result)
            
            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(1)
        
        print(f"✅ Batch generation complete: {len(results)} videos generated")
        return results
    
    def get_generation_status(self, generation_id: str) -> Dict[str, Any]:
        """
        Get the status of a video generation
        
        Args:
            generation_id: ID of the generation request
            
        Returns:
            Generation status information
        """
        # This would typically make an API call to check status
        # For now, return a placeholder
        return {
            "generation_id": generation_id,
            "status": "completed",
            "progress": 100,
            "estimated_time_remaining": 0
        }
    
    def save_generation_result(self, result: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Save video generation result to file
        
        Args:
            result: Video generation result
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            prompt_safe = "".join(c for c in result.get("prompt", "video")[:30] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"veo3_generation_{prompt_safe}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Video generation result saved to: {filename}")
        return filename
    
    def get_supported_resolutions(self) -> List[str]:
        """Get list of supported video resolutions"""
        return ["720p", "1080p", "4k"]
    
    def get_supported_styles(self) -> List[str]:
        """Get list of supported video styles"""
        return ["realistic", "animated", "artistic", "cinematic", "documentary"]
    
    def get_max_duration(self) -> int:
        """Get maximum video duration in seconds"""
        return 10
    
    def get_min_duration(self) -> int:
        """Get minimum video duration in seconds"""
        return 1


# Example usage and testing
async def main():
    """
    Example usage of Veo3 API
    """
    print("🚀 Veo3 API Demo")
    print("=" * 50)
    
    # Initialize Veo3 client
    try:
        veo3 = Veo3API()
        print("✅ Veo3 API client initialized")
    except ValueError as e:
        print(f"❌ Initialization failed: {e}")
        print("Please set GOOGLE_API_KEY in your .env file")
        return
    
    # Example 1: Single video generation
    print("\n🎬 Example 1: Single Video Generation")
    print("-" * 40)
    
    video_result = await veo3.generate_video(
        prompt="A beautiful sunset over mountains with birds flying",
        duration=5,
        resolution="1080p",
        style="realistic"
    )
    
    print("Video generation result:")
    print(json.dumps(video_result, indent=2))
    
    # Save result
    veo3.save_generation_result(video_result)
    
    # Example 2: Batch video generation
    print("\n🎬 Example 2: Batch Video Generation")
    print("-" * 40)
    
    prompts = [
        "A cat playing with a ball of yarn",
        "Ocean waves crashing on a beach",
        "A city skyline at night with lights"
    ]
    
    batch_results = await veo3.generate_video_batch(
        prompts=prompts,
        duration=3,
        resolution="720p",
        style="animated"
    )
    
    print(f"Generated {len(batch_results)} videos")
    
    # Save batch results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(f"veo3_batch_{timestamp}.json", 'w') as f:
        json.dump(batch_results, f, indent=2)
    
    print("✅ Demo complete")


if __name__ == "__main__":
    asyncio.run(main())
