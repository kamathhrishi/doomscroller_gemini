"""
YouTube Doomscroller - Trending Video Analyzer
Scrapes YouTube trending videos and analyzes them with Gemini Vision API
No login required - uses public trending page
"""

import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import requests
from io import BytesIO
import threading
import time
import argparse
from pathlib import Path

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Gemini model
vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Lock for thread-safe file operations
save_lock = threading.Lock()

# Configuration
CONCURRENT_WORKERS = 5  # Number of videos to analyze in parallel
MAX_VIDEOS = 50  # Maximum number of videos to scrape (limited to 50)


async def scrape_trending_videos(page, category=''):
    """Scrape YouTube Shorts
    
    Scrapes the YouTube Shorts feed
    """
    print(f"\n{'='*60}")
    print(f"🎬 Scraping YouTube Shorts")
    print('='*60)
    
    # Use YouTube Shorts page
    url = 'https://www.youtube.com/shorts/'
    
    try:
        print(f"📍 Navigating to: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)
        
        # Wait for first short to load
        print("⏳ Waiting for first Short to load...")
        await page.wait_for_timeout(5000)
        
        # Take a screenshot for debugging
        await page.screenshot(path='screenshots/youtube_debug_before.png')
        print("📸 Debug screenshot saved: screenshots/youtube_debug_before.png")
        
        # Extract video data as we navigate
        videos = []
        seen_ids = set()
        
        print(f"\n⬇️  Extracting {MAX_VIDEOS} shorts by navigating...")
        
        for idx in range(MAX_VIDEOS * 2):  # Try more than we need in case of duplicates
            try:
                # Get current URL from address bar
                current_url = page.url
                
                # Extract video ID from current URL
                if '/shorts/' in current_url:
                    video_id = current_url.split('/shorts/')[-1].split('?')[0].split('&')[0]
                    
                    # Skip if we've already seen this video
                    if video_id in seen_ids:
                        print(f"   [{len(videos)+1}] Duplicate, skipping...")
                        await page.keyboard.press('ArrowDown')
                        await page.wait_for_timeout(800)
                        continue
                    
                    seen_ids.add(video_id)
                    full_url = f'https://www.youtube.com/shorts/{video_id}'
                    
                    # Extract data from current short
                    print(f"\n🔍 [{len(videos)+1}/{MAX_VIDEOS}] Extracting: {video_id}")
                    
                    # Try to get title from page
                    title = 'Unknown'
                    try:
                        # Title is often in h2 or meta tags
                        title_element = page.locator('h2.title, ytd-reel-player-overlay-renderer h2, meta[property="og:title"]').first
                        if title_element:
                            if await title_element.get_attribute('content'):
                                title = await title_element.get_attribute('content')
                            else:
                                title = await title_element.inner_text()
                    except:
                        pass
                    
                    if not title or title == 'Unknown':
                        title = f"YouTube Short #{len(videos)+1}"
                    
                    # Try to get channel name
                    channel_name = 'Unknown'
                    try:
                        channel_element = page.locator('ytd-channel-name a, #channel-name, .ytd-reel-player-overlay-renderer #channel-name').first
                        if channel_element:
                            channel_name = await channel_element.inner_text()
                    except:
                        pass
                
                    # Get views if available
                    views = 'Unknown'
                    try:
                        views_element = page.locator('span.view-count, #factoids span').first
                        if views_element:
                            views = await views_element.inner_text()
                    except:
                        pass
                    
                    # Get thumbnail URL (construct from video ID)
                    thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
                    
                    video_data = {
                        'video_id': video_id,
                        'url': full_url,
                        'title': title.strip()[:200] if title else 'Unknown',
                        'channel': channel_name.strip() if channel_name else 'Unknown',
                        'views': views.strip() if views else 'Unknown',
                        'upload_time': 'Unknown',
                        'duration': 'Short (<60s)',
                        'thumbnail_url': thumbnail_url,
                        'category': 'shorts'
                    }
                    
                    videos.append(video_data)
                    print(f"   ✅ {title[:50]}... by {channel_name}")
                    
                    # Stop if we have enough
                    if len(videos) >= MAX_VIDEOS:
                        print(f"\n✅ Collected {MAX_VIDEOS} shorts!")
                        break
                
                # Navigate to next short
                await page.keyboard.press('ArrowDown')
                await page.wait_for_timeout(800)  # Wait for transition
                
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
                # Try to continue to next short
                await page.keyboard.press('ArrowDown')
                await page.wait_for_timeout(800)
                continue
        
        print(f"\n✅ Successfully extracted {len(videos)} shorts")
        return videos
        
    except Exception as e:
        print(f"❌ Error scraping YouTube Shorts: {e}")
        import traceback
        traceback.print_exc()
        return []


async def analyze_video(video_data, index, total):
    """Analyze a single YouTube video using Gemini's video analysis"""
    print(f"\n{'='*60}")
    print(f"🔍 Analyzing video {index}/{total}")
    print(f"📍 Title: {video_data['title']}")
    print('='*60)
    
    analysis_data = video_data.copy()
    analysis_data['timestamp'] = datetime.now().isoformat()
    analysis_data['index'] = index
    
    try:
        # First, download and save thumbnail for display
        print(f"📥 Downloading thumbnail...")
        response = requests.get(video_data['thumbnail_url'], timeout=10)
        
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            thumbnail_path = f'screenshots/youtube_{video_data["video_id"]}.jpg'
            os.makedirs('screenshots', exist_ok=True)
            img.save(thumbnail_path)
            analysis_data['thumbnail_path'] = thumbnail_path
            print(f"💾 Thumbnail saved: {thumbnail_path}")
        
        # Analyze the actual video content with Gemini
        print("🎬 Analyzing video content with Gemini...")
        
        prompt = f"""
You are a professional YouTube content analyst. Analyze this ENTIRE VIDEO in EXTREME DETAIL.

VIDEO METADATA:
- Title: {video_data['title']}
- Channel: {video_data['channel']}
- Views: {video_data['views']}
- Duration: {video_data['duration']}
- Upload Time: {video_data['upload_time']}

# VIDEO CONTENT ANALYSIS

## Content Summary
- **Main Topic**: What is this video about?
- **Key Points**: List 5-10 main points covered
- **Video Structure**: How is the content organized? (intro, sections, conclusion)
- **Pacing**: Fast-paced, slow, moderate?

## Visual Style & Production

### Thumbnail Analysis

## Color Palette & Design
- **Dominant Colors**: List 3-5 main colors with descriptions
- **Color Psychology**: What emotions do these colors evoke?
- **Saturation Level**: High (vibrant), medium, or low (muted)?
- **Contrast**: High contrast for attention or soft/subtle?
- **Color Scheme**: Complementary, analogous, monochromatic, etc.

## Composition & Layout
- **Focal Point**: Where does the eye go first?
- **Text Placement**: Where is text positioned? (top, center, bottom, sides)
- **Subject Position**: Center, rule of thirds, off-center?
- **Background**: Simple, complex, blurred, or detailed?
- **Framing**: Tight crop, wide shot, or medium shot?

## Typography & Text
- **Main Text**: What's the headline/hook text?
- **Font Style**: Bold, outlined, 3D, shadow, neon, modern, etc.?
- **Text Size**: How much of the thumbnail does text occupy?
- **Text Color**: How does it contrast with background?
- **Text Effects**: Stroke, shadow, glow, gradient?
- **Readability**: Is it instantly readable at small size?

## Visual Elements
- **Human Faces**: Any faces? Expressions? (shocked, excited, serious, etc.)
- **Pointing/Arrows**: Directional elements to guide attention?
- **Emojis/Icons**: Any emoji overlays or icons?
- **Objects/Props**: Key objects that tell the story?
- **Branding**: Logos, watermarks, channel branding?

## Video Quality & Editing
- **Video Quality**: Resolution, clarity, professional vs amateur
- **Editing Style**: Jump cuts, smooth transitions, effects used
- **B-Roll Usage**: Stock footage, custom shots, graphics
- **Text Overlays**: Subtitles, captions, emphasis text
- **Music/Sound**: Background music style, sound effects
- **Intro/Outro**: How does video start and end?

## On-Screen Elements
- **Host Presence**: Is there a person on camera? Style/personality?
- **Setting**: Studio, bedroom, outdoor, screen recording?
- **Graphics**: Animations, lower thirds, overlays
- **Demonstration**: Is anything being shown or taught?

## Content Delivery
- **Speaking Style**: Conversational, formal, energetic, calm
- **Script Quality**: Well-scripted vs improvised
- **Information Density**: How much info per minute?
- **Entertainment Value**: Funny, serious, dramatic, educational

# AUDIENCE ENGAGEMENT ANALYSIS

## Hook & Retention
- **First 10 Seconds**: How does video grab attention?
- **Retention Tactics**: Teasers, cliffhangers, chapter markers
- **Call-to-Actions**: Subscribe reminders, links mentioned
- **Engagement Prompts**: Questions asked, comments requested

# CONTENT STRATEGY ANALYSIS

## Title Analysis
- **Hook Type**: Question, number, how-to, controversy, etc.?
- **Keywords**: Main SEO keywords present?
- **Emotional Words**: Words that trigger emotion?
- **Length**: Optimal length for engagement?
- **Caps/Punctuation**: Use of ALL CAPS or exclamation marks?

## Niche & Category
- **Content Type**: Tutorial, entertainment, vlog, review, gaming, etc.?
- **Target Audience**: Who is this for? (age, interests)
- **Trend Alignment**: Following current YouTube trends?
- **Viral Potential**: Elements that could make it viral?

## Engagement Patterns
- **View Count**: Is it performing well?
- **Recency**: Recent upload or older?
- **Channel Authority**: Does the channel look established?

# RECREATION GUIDE

Provide actionable steps to create a similar thumbnail:
- **Thumbnail Creation Tools**: Software/apps to use
- **Color Palette**: Specific colors to use
- **Text Overlay Strategy**: Font choices and placement
- **Visual Elements**: What to include in the thumbnail
- **Composition Tips**: How to arrange elements
- **Attention Grabbers**: Techniques to make it click-worthy

# COMPETITIVE ANALYSIS

- **Similar Content**: What other videos compete in this space?
- **Differentiation**: What makes this stand out?
- **Improvement Opportunities**: What could be better?

Return ONLY valid JSON in this format:
{{
  "content_summary": {{
    "main_topic": "what the video is about",
    "key_points": ["point1", "point2", "point3"],
    "video_structure": "description",
    "pacing": "fast/medium/slow",
    "overall_description": "3-sentence summary"
  }},
  
  "visual_production": {{
    "video_quality": "1080p/4K/amateur/professional",
    "editing_style": "description",
    "b_roll_usage": "description",
    "text_overlays": "description",
    "music_sound": "description",
    "intro_outro": "description"
  }},
  
  "on_screen_elements": {{
    "host_presence": "description or none",
    "setting": "description",
    "graphics": "description",
    "demonstration": "what's being shown"
  }},
  
  "content_delivery": {{
    "speaking_style": "description",
    "script_quality": "high/medium/low",
    "information_density": "high/medium/low",
    "entertainment_value": "high/medium/low"
  }},
  
  "engagement_tactics": {{
    "hook": "first 10 seconds description",
    "retention_tactics": ["tactic1", "tactic2"],
    "calls_to_action": ["cta1", "cta2"],
    "engagement_prompts": ["prompt1", "prompt2"]
  }},
  
  "thumbnail_analysis": {{
    "color_palette": {{
      "dominant_colors": ["color1", "color2", "color3"],
      "color_psychology": "emotion description",
      "saturation": "high/medium/low",
      "contrast": "high/low",
      "color_scheme": "type"
    }},
    "composition": {{
      "focal_point": "description",
      "text_placement": "location",
      "subject_position": "description",
      "background": "description",
      "framing": "type"
    }},
    "typography": {{
      "main_text": "headline text found in thumbnail",
      "font_style": "description",
      "text_size": "large/medium/small",
      "text_color": "color",
      "text_effects": "description",
      "readability": "high/medium/low"
    }},
    "visual_elements": {{
      "faces": "description of faces and expressions",
      "arrows_pointing": true/false,
      "emojis_icons": ["list of emojis/icons"],
      "objects_props": ["key objects"],
      "branding": "description"
    }},
    "click_factors": {{
      "curiosity_gap": "description",
      "emotional_trigger": "emotion",
      "visual_contrast": "description",
      "pattern_interruption": "what's unusual",
      "value_proposition": "promised benefit"
    }}
  }},
  
  "title_analysis": {{
    "hook_type": "question/number/how-to/etc",
    "keywords": ["keyword1", "keyword2"],
    "emotional_words": ["word1", "word2"],
    "length": "character count and assessment",
    "special_formatting": "caps, punctuation, etc"
  }},
  
  "content_strategy": {{
    "content_type": "tutorial/entertainment/etc",
    "target_audience": "description",
    "trend_alignment": "description",
    "viral_potential": "high/medium/low with explanation",
    "niche": "specific niche"
  }},
  
  "engagement_analysis": {{
    "view_performance": "analysis based on views",
    "recency_factor": "analysis based on upload time",
    "channel_authority": "assessment"
  }},
  
  "recreation_guide": {{
    "thumbnail_tools": ["tool1", "tool2"],
    "color_palette_to_use": ["specific colors"],
    "text_strategy": "detailed text overlay approach",
    "visual_elements_needed": ["elements to include"],
    "composition_tips": "arrangement advice",
    "attention_techniques": ["technique1", "technique2"]
  }},
  
  "competitive_insights": {{
    "similar_content": "description",
    "differentiation": "what makes it unique",
    "improvements": ["suggestion1", "suggestion2"]
  }},
  
  "overall_assessment": {{
    "thumbnail_quality": "1-10 rating",
    "title_quality": "1-10 rating",
    "overall_click_potential": "1-10 rating",
    "key_strengths": ["strength1", "strength2"],
    "key_weaknesses": ["weakness1", "weakness2"]
  }}
}}

Analyze the ENTIRE video deeply. Watch it all and provide specific, actionable insights.
"""
        
        # Analyze with Gemini Vision using thumbnail
        # Note: Direct YouTube URL analysis requires different setup
        # For now, we'll analyze the thumbnail which still gives great insights
        print("🤖 Analyzing thumbnail with Gemini Vision...")
        response = vision_model.generate_content([prompt, img])
        
        # Add small delay to avoid rate limits
        time.sleep(1)
        
        # Parse the response
        if hasattr(response, 'text'):
            response_text = response.text.strip()
        else:
            response_text = str(response).strip()
        
        # Try to extract JSON from response
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        elif '```' in response_text:
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        
        # Parse JSON
        gemini_analysis = json.loads(response_text)
        
        # Merge analysis into data
        analysis_data.update(gemini_analysis)
        analysis_data['gemini_raw_response'] = response_text
        
        print(f"✅ Analysis complete!")
        return analysis_data
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Response: {response_text[:500]}")
        analysis_data['error'] = 'JSON parse error'
        analysis_data['raw_response'] = response_text
        return analysis_data
        
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        analysis_data['error'] = str(e)
        return analysis_data


async def analyze_videos_parallel(videos, concurrent_workers=CONCURRENT_WORKERS):
    """Analyze multiple videos in parallel"""
    print(f"\n🚀 Starting parallel analysis with {concurrent_workers} workers...")
    
    all_results = []
    semaphore = asyncio.Semaphore(concurrent_workers)
    
    async def analyze_with_semaphore(video, index, total):
        async with semaphore:
            return await analyze_video(video, index, total)
    
    tasks = [
        analyze_with_semaphore(video, i+1, len(videos))
        for i, video in enumerate(videos)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            print(f"❌ Task failed: {result}")
        else:
            all_results.append(result)
    
    return all_results


def save_analysis(videos_data, account_id=None):
    """Save analysis to JSON file
    
    Args:
        videos_data: List of analyzed videos
        account_id: Optional account ID to save to specific account folder
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Determine save directory based on account
    if account_id:
        save_dir = Path(f"data/accounts/{account_id}")
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / "screenshots").mkdir(exist_ok=True)
        filename = save_dir / f'youtube_analysis_{timestamp}.json'
        print(f"💾 Saving to account folder: {save_dir}")
    else:
        filename = f'youtube_analysis_{timestamp}.json'
        print(f"💾 Saving to root directory (generic account)")
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'total_videos': len(videos_data),
        'successful': len([v for v in videos_data if 'error' not in v]),
        'failed': len([v for v in videos_data if 'error' in v]),
        'videos': videos_data
    }
    
    with save_lock:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Analysis saved to: {filename}")
    return filename


async def main(account_id=None):
    """Main function to run the YouTube scraper
    
    Args:
        account_id: Optional account ID to save results to specific account folder
    """
    print("\n" + "="*60)
    print("🎬 YouTube Doomscroller Starting...")
    if account_id:
        print(f"📁 Account ID: {account_id}")
    print("="*60)
    
    async with async_playwright() as p:
        # Launch browser
        print("\n🌐 Launching browser...")
        browser = await p.chromium.launch(headless=False)  # Set to True for headless
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # Scrape videos from home page
            videos = await scrape_trending_videos(page)
            
            if not videos:
                print("❌ No videos found!")
                return
            
            print(f"\n📊 Found {len(videos)} videos to analyze (limited to max {MAX_VIDEOS})")
            
            # Close browser before analysis
            await browser.close()
            
            # Analyze videos in parallel
            analyzed_videos = await analyze_videos_parallel(videos)
            
            # Save results
            save_analysis(analyzed_videos, account_id=account_id)
            
            print("\n" + "="*60)
            print("✅ YouTube Doomscroller Complete!")
            print(f"📊 Analyzed {len(analyzed_videos)} videos")
            print(f"✅ Successful: {len([v for v in analyzed_videos if 'error' not in v])}")
            print(f"❌ Failed: {len([v for v in analyzed_videos if 'error' in v])}")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
        finally:
            if browser.is_connected():
                await browser.close()


if __name__ == "__main__":
    """
    Run YouTube scraper with optional account targeting
    
    Examples:
        python youtube_scraper.py                           # Save to root (generic account)
        python youtube_scraper.py --account acc_1729380000  # Save to protein cookies account
    """
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='YouTube Doomscroller - Scrape and analyze YouTube Shorts',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--account',
        type=str,
        default=None,
        help='Account ID to save results to specific account folder (e.g., acc_1729380000)'
    )
    
    args = parser.parse_args()
    
    # Run the main function with account_id
    asyncio.run(main(account_id=args.account))

