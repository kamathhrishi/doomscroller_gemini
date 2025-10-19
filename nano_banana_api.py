"""
Nano Banana API Integration (Gemini 2.5 Flash Image)
Google Gemini 2.5 Flash Image API integration for image generation and editing
"""

import os
import json
import asyncio
import base64
import io
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

class NanoBananaAPI:
    """
    Image generation and editing API client using Gemini 2.5 Flash Image (Nano Banana)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Nano Banana (Gemini 2.5 Flash Image) API client
        
        Args:
            api_key: Google API key (if not provided, will use GOOGLE_API_KEY from .env)
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY in .env file")
        
        # Initialize Google GenAI client
        self.client = genai.Client(api_key=self.api_key)
        
        # Model name for Nano Banana (Gemini 2.5 Flash Image)
        self.model_name = "gemini-2.5-flash-image"
        
        # Generation cache to avoid duplicate API calls
        self.generation_cache = {}
        
        # Directory for saving generated images
        self.output_dir = Path("generated_images")
        self.output_dir.mkdir(exist_ok=True)
    
    async def generate_image(self, 
                           prompt: str, 
                           width: int = 1024,
                           height: int = 1024,
                           style: str = "realistic",
                           quality: str = "high",
                           cache_results: bool = True,
                           save_to_disk: bool = True) -> Dict[str, Any]:
        """
        Generate an image using Nano Banana (Gemini 2.5 Flash Image)
        
        Args:
            prompt: Text description of the image to generate
            width: Image width in pixels
            height: Image height in pixels
            style: Image style ("realistic", "artistic", "cartoon", "abstract")
            quality: Image quality ("low", "medium", "high", "ultra")
            cache_results: Whether to cache results for future use
            save_to_disk: Whether to save the image to disk
            
        Returns:
            Image generation result with URL and metadata
        """
        # Check cache first
        cache_key = f"{prompt}_{width}_{height}_{style}_{quality}"
        if cache_results and cache_key in self.generation_cache:
            print("📋 Using cached image generation result")
            return self.generation_cache[cache_key]
        
        print(f"🖼️ Generating image with Nano Banana: {prompt[:50]}...")
        
        try:
            # Enhance prompt with style
            enhanced_prompt = prompt
            if style and style != "realistic":
                enhanced_prompt = f"{prompt}, {style} style"
            
            # Add quality hints
            quality_modifiers = {
                "low": "simple, basic",
                "medium": "detailed",
                "high": "highly detailed, high quality",
                "ultra": "ultra detailed, masterpiece, highest quality"
            }
            if quality in quality_modifiers:
                enhanced_prompt = f"{enhanced_prompt}, {quality_modifiers[quality]}"
            
            # Generate image using Gemini 2.5 Flash Image
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=enhanced_prompt
            )
            
            # Extract image data from response
            image_data = None
            image_path = None
            image_url = None
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        # Check if this part contains image data
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Extract base64 image data
                            image_bytes = part.inline_data.data
                            image_data = base64.b64encode(image_bytes).decode('utf-8')
                            
                            # Save to disk if requested
                            if save_to_disk:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                prompt_safe = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                                filename = f"nano_banana_{prompt_safe}_{timestamp}.png"
                                image_path = self.output_dir / filename
                                
                                # Save the image
                                with open(image_path, 'wb') as f:
                                    f.write(image_bytes)
                                
                                image_url = f"/generated_images/{filename}"
                                print(f"💾 Image saved to: {image_path}")
                            
                            break
            
            if not image_data:
                raise Exception("No image data returned from API")
            
            # Create result
            result = {
                "image_url": image_url or f"data:image/png;base64,{image_data}",
                "image_data": image_data,
                "image_path": str(image_path) if image_path else None,
                "prompt": prompt,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "prompt": prompt,
                    "enhanced_prompt": enhanced_prompt,
                    "width": width,
                    "height": height,
                    "style": style,
                    "quality": quality,
                    "api_used": "nano_banana",
                    "model": self.model_name,
                    "status": "success"
                }
            }
            
            # Cache results
            if cache_results:
                self.generation_cache[cache_key] = result
            
            print("✅ Image generation completed successfully")
            return result
                        
        except Exception as e:
            print(f"❌ Image generation failed: {e}")
            return {
                "error": str(e),
                "prompt": prompt,
                "generated_at": datetime.now().isoformat(),
                "api_used": "nano_banana",
                "status": "error"
            }
    
    async def edit_image(self,
                       prompt: str,
                       image_path: Union[str, Path],
                       save_to_disk: bool = True) -> Dict[str, Any]:
        """
        Edit an existing image using Nano Banana
        
        Args:
            prompt: Text description of how to edit the image
            image_path: Path to the image to edit
            save_to_disk: Whether to save the edited image to disk
            
        Returns:
            Image editing result with URL and metadata
        """
        print(f"✏️ Editing image with Nano Banana: {prompt[:50]}...")
        
        try:
            # Load the image
            image = Image.open(image_path)
            
            # Generate edited image using Gemini 2.5 Flash Image
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[prompt, image]
            )
            
            # Extract image data from response
            image_data = None
            edited_image_path = None
            image_url = None
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_bytes = part.inline_data.data
                            image_data = base64.b64encode(image_bytes).decode('utf-8')
                            
                            if save_to_disk:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                prompt_safe = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                                filename = f"nano_banana_edited_{prompt_safe}_{timestamp}.png"
                                edited_image_path = self.output_dir / filename
                                
                                with open(edited_image_path, 'wb') as f:
                                    f.write(image_bytes)
                                
                                image_url = f"/generated_images/{filename}"
                                print(f"💾 Edited image saved to: {edited_image_path}")
                            
                            break
            
            if not image_data:
                raise Exception("No image data returned from API")
            
            result = {
                "image_url": image_url or f"data:image/png;base64,{image_data}",
                "image_data": image_data,
                "image_path": str(edited_image_path) if edited_image_path else None,
                "prompt": prompt,
                "original_image": str(image_path),
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "prompt": prompt,
                    "api_used": "nano_banana",
                    "model": self.model_name,
                    "operation": "edit",
                    "status": "success"
                }
            }
            
            print("✅ Image editing completed successfully")
            return result
            
        except Exception as e:
            print(f"❌ Image editing failed: {e}")
            return {
                "error": str(e),
                "prompt": prompt,
                "generated_at": datetime.now().isoformat(),
                "api_used": "nano_banana",
                "status": "error"
            }
    
    async def generate_image_batch(self, 
                                 prompts: List[str], 
                                 width: int = 1024,
                                 height: int = 1024,
                                 style: str = "realistic",
                                 quality: str = "high") -> List[Dict[str, Any]]:
        """
        Generate multiple images in batch
        
        Args:
            prompts: List of text descriptions for images
            width: Image width in pixels
            height: Image height in pixels
            style: Image style
            quality: Image quality
            
        Returns:
            List of image generation results
        """
        print(f"🖼️ Generating {len(prompts)} images in batch...")
        
        results = []
        for i, prompt in enumerate(prompts):
            print(f"Generating image {i+1}/{len(prompts)}: {prompt[:50]}...")
            
            result = await self.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                style=style,
                quality=quality
            )
            
            results.append(result)
            
            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(0.5)
        
        print(f"✅ Batch generation complete: {len(results)} images generated")
        return results
    
    async def generate_image_variations(self, 
                                      base_prompt: str,
                                      num_variations: int = 4,
                                      width: int = 1024,
                                      height: int = 1024,
                                      style: str = "realistic") -> List[Dict[str, Any]]:
        """
        Generate multiple variations of the same prompt
        
        Args:
            base_prompt: Base text description
            num_variations: Number of variations to generate
            width: Image width in pixels
            height: Image height in pixels
            style: Image style
            
        Returns:
            List of image generation results
        """
        print(f"🖼️ Generating {num_variations} variations of: {base_prompt[:50]}...")
        
        # Create variations by adding slight modifications
        variations = []
        for i in range(num_variations):
            if i == 0:
                variations.append(base_prompt)
            else:
                # Add variation modifiers
                modifiers = [
                    "with dramatic lighting",
                    "in a different color scheme",
                    "with enhanced details",
                    "with artistic flair",
                    "with cinematic composition"
                ]
                modifier = modifiers[i % len(modifiers)]
                variations.append(f"{base_prompt}, {modifier}")
        
        return await self.generate_image_batch(
            prompts=variations,
            width=width,
            height=height,
            style=style
        )
    
    def get_generation_status(self, generation_id: str) -> Dict[str, Any]:
        """
        Get the status of an image generation
        
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
        Save image generation result to file
        
        Args:
            result: Image generation result
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            prompt_safe = "".join(c for c in result.get("prompt", "image")[:30] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"nano_banana_generation_{prompt_safe}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Image generation result saved to: {filename}")
        return filename
    
    def get_supported_sizes(self) -> List[Dict[str, int]]:
        """Get list of supported image sizes"""
        return [
            {"width": 512, "height": 512, "name": "Square"},
            {"width": 768, "height": 768, "name": "Square HD"},
            {"width": 1024, "height": 1024, "name": "HD Square"},
            {"width": 1024, "height": 768, "name": "Landscape"},
            {"width": 768, "height": 1024, "name": "Portrait"},
            {"width": 1920, "height": 1080, "name": "Full HD Landscape"},
            {"width": 1080, "height": 1920, "name": "Full HD Portrait"},
            {"width": 2048, "height": 2048, "name": "4K Square"}
        ]
    
    def get_supported_styles(self) -> List[str]:
        """Get list of supported image styles"""
        return [
            "realistic", "artistic", "cartoon", "abstract", 
            "photographic", "painting", "sketch", "digital_art",
            "vintage", "modern", "minimalist", "detailed"
        ]
    
    def get_supported_qualities(self) -> List[str]:
        """Get list of supported image qualities"""
        return ["low", "medium", "high", "ultra"]


# Example usage and testing
async def main():
    """
    Example usage of Image Generation API
    """
    print("🚀 Image Generation API Demo (Google Imagen)")
    print("=" * 50)
    
    # Initialize Image Generation client
    try:
        nano_banana = NanoBananaAPI()
        print("✅ Image Generation API client initialized")
    except ValueError as e:
        print(f"❌ Initialization failed: {e}")
        print("Please set GOOGLE_API_KEY in your .env file")
        return
    
    # Example 1: Single image generation
    print("\n🖼️ Example 1: Single Image Generation")
    print("-" * 40)
    
    image_result = await nano_banana.generate_image(
        prompt="A futuristic city with flying cars and neon lights",
        width=1024,
        height=1024,
        style="realistic",
        quality="high"
    )
    
    print("Image generation result:")
    print(json.dumps(image_result, indent=2))
    
    # Save result
    nano_banana.save_generation_result(image_result)
    
    # Example 2: Batch image generation
    print("\n🖼️ Example 2: Batch Image Generation")
    print("-" * 40)
    
    prompts = [
        "A serene mountain landscape at sunrise",
        "A cyberpunk street scene with neon signs",
        "A cute robot playing with a cat"
    ]
    
    batch_results = await nano_banana.generate_image_batch(
        prompts=prompts,
        width=768,
        height=768,
        style="artistic",
        quality="high"
    )
    
    print(f"Generated {len(batch_results)} images")
    
    # Save batch results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(f"nano_banana_batch_{timestamp}.json", 'w') as f:
        json.dump(batch_results, f, indent=2)
    
    # Example 3: Image variations
    print("\n🖼️ Example 3: Image Variations")
    print("-" * 40)
    
    variations = await nano_banana.generate_image_variations(
        base_prompt="A magical forest with glowing mushrooms",
        num_variations=3,
        width=1024,
        height=1024,
        style="artistic"
    )
    
    print(f"Generated {len(variations)} variations")
    
    print("✅ Demo complete")


if __name__ == "__main__":
    asyncio.run(main())
