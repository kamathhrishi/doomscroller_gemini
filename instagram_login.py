"""
Simple Instagram Login Script using Playwright
Logs into Instagram using credentials from .env file
Uses Gemini Vision API to analyze post screenshots
"""

import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import re
import glob
import google.generativeai as genai
from PIL import Image
import threading

# Load environment variables
load_dotenv()

INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Gemini Vision model
vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Lock for thread-safe file operations
save_lock = threading.Lock()

# Configuration
CONCURRENT_WORKERS = 5  # Number of posts to analyze in parallel (adjustable: 1-10)


async def extract_comments_and_likes(page):
    """Extract all visible comments and their like counts"""
    comments_data = []
    
    try:
        # Wait for comments to load
        await page.wait_for_timeout(2000)
        
        # Look for comment elements - Instagram uses various selectors
        comment_selectors = [
            'article div[role="button"] span',
            'article span[dir="auto"]',
            'div[data-testid="comment"]',
            'article div[style*="word-wrap"] span',
            'article div[style*="word-break"] span'
        ]
        
        comments_found = False
        for selector in comment_selectors:
            try:
                comment_elements = await page.locator(selector).all()
                if comment_elements:
                    comments_found = True
                    print(f"📝 Found {len(comment_elements)} comment elements using selector: {selector}")
                    break
            except:
                continue
        
        if not comments_found:
            print("⚠️ No comments found with standard selectors, trying alternative approach...")
            # Try to find comments by looking for text that's not the caption
            try:
                # Look for spans that contain text but are not the main caption
                all_spans = await page.locator('span').all()
                for span in all_spans:
                    try:
                        text = await span.inner_text()
                        if text and len(text) > 10 and not text.startswith('@') and '#' not in text:
                            # This might be a comment
                            comments_data.append({
                                'text': text,
                                'likes': 'Unknown',
                                'author': 'Unknown'
                            })
                    except:
                        continue
            except:
                pass
        
        # Try to extract like counts for comments
        like_selectors = [
            'button[aria-label*="like"]',
            'button[aria-label*="Like"]',
            'span[aria-label*="like"]',
            'span[aria-label*="Like"]'
        ]
        
        for i, comment in enumerate(comments_data):
            try:
                # Look for like button near this comment
                for like_selector in like_selectors:
                    like_elements = await page.locator(like_selector).all()
                    if like_elements and i < len(like_elements):
                        like_text = await like_elements[i].get_attribute('aria-label')
                        if like_text:
                            # Extract number from aria-label like "123 likes"
                            import re
                            numbers = re.findall(r'\d+', like_text)
                            if numbers:
                                comment['likes'] = numbers[0]
                                break
            except:
                pass
        
        print(f"✅ Extracted {len(comments_data)} comments")
        
    except Exception as e:
        print(f"❌ Error extracting comments: {e}")
    
    return comments_data


async def analyze_post(page, url, index, total):
    """Analyze a single Instagram post"""
    print(f"\n{'='*60}")
    print(f"🔍 Analyzing post {index}/{total}")
    print(f"📍 URL: {url}")
    print('='*60)
    
    post_data = {
        'url': url,
        'timestamp': datetime.now().isoformat(),
        'index': index
    }
    
    try:
        # Navigate to post - just wait for basic loading
        await page.goto(url, timeout=30000)
        
        # Wait a bit for content to render
        await page.wait_for_timeout(3000)
        
        # Extract comments and their likes
        print("💬 Extracting comments and likes...")
        comments_data = await extract_comments_and_likes(page)
        post_data['comments'] = comments_data
        
        # Take screenshot
        screenshot_path = f'screenshots/post_{index}.png'
        try:
            os.makedirs('screenshots', exist_ok=True)
            await page.screenshot(path=screenshot_path, full_page=False)
            post_data['screenshot'] = screenshot_path
            print(f"📸 Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"❌ Screenshot failed: {e}")
            post_data['error'] = 'Screenshot failed'
            return post_data
        
        # Analyze screenshot with Gemini Vision
        print("🤖 Analyzing with Gemini Vision API...")
        try:
            # Load the screenshot
            img = Image.open(screenshot_path)
            
            # Create a detailed prompt for Gemini
            prompt = """
You are a professional Instagram content analyst. Analyze this post screenshot in EXTREME DETAIL to help recreate viral content.

# BASIC INFORMATION
1. **Caption**: Full caption text (word-for-word)
2. **Hashtags**: All hashtags used
3. **Engagement**: Likes, comments, shares, saves (if visible)
4. **Creator**: Username and any visible follower count
5. **Post Type**: Video (with play icon), Image, Carousel (multiple images icon)
6. **Timestamp**: When posted (if visible)
7. **Comments**: All visible comments and their like counts (if any)

# TEXT EXTRACTION FROM IMAGES (OCR)
8. **Text Within Images**: Extract ALL text visible within the actual post image(s), including:
   - Text overlays on images/videos
   - Text written on signs, documents, screens, or objects
   - Text in memes, quotes, or graphics
   - Text on products, packaging, or labels
   - Text in infographics or charts
   - Any handwritten or printed text visible in the image
   - Text in video thumbnails or first frames
   - Text in carousel images (analyze each image separately)
   - Text in stickers, emojis with text, or annotations
   - Text in backgrounds, walls, or environmental elements
   - Text in clothing, accessories, or personal items
   - Text in food packaging, menus, or restaurant signs
   - Text in books, magazines, or reading materials
   - Text in computer screens, phones, or digital displays
   - Text in vehicles, buildings, or street signs
   - Any other text visible anywhere in the image

   For each piece of text found, note:
   - The exact text content
   - Where it appears in the image (top, bottom, center, etc.)
   - Font style if distinguishable (bold, italic, handwritten, etc.)
   - Text color if visible
   - Size relative to other elements (large, small, etc.)
   - Whether it's part of the main content or background

# VISUAL DESIGN ANALYSIS (THIS IS CRITICAL!)

## Color Palette
- **Dominant Colors**: List the 3-5 main colors with hex codes or descriptions (e.g., "vibrant orange #FF6B35", "soft pink", "navy blue")
- **Color Temperature**: Warm, cool, or neutral tones?
- **Color Saturation**: High saturation (vibrant), low saturation (muted/pastel), or desaturated (grayscale)?
- **Color Mood**: What emotion do the colors evoke? (energetic, calm, luxurious, playful, etc.)

## Composition & Layout
- **Subject Placement**: Center, rule of thirds, off-center? Where is the main focus?
- **Framing**: Close-up, medium shot, wide shot, aerial view?
- **Orientation**: Portrait, landscape, or square?
- **Negative Space**: How much empty/background space? Minimalist or busy?
- **Layering**: Foreground, middle ground, background elements?

## Visual Style & Aesthetics
- **Photography/Design Style**: Minimalist, maximalist, flat lay, lifestyle, professional studio, candid, moody, bright & airy, vintage, modern, etc.
- **Lighting**: Natural light, artificial, studio lighting, golden hour, backlit, harsh shadows, soft diffused, dramatic?
- **Filters/Editing**: Heavy filters, natural/unfiltered, high contrast, low contrast, vintage grain, HDR, black & white, specific preset style?
- **Sharpness**: Crystal sharp, soft focus, bokeh background blur?

## Typography & Text Overlays
- **Text Presence**: Is there text overlaid on the image?
- **Font Style**: Sans-serif, serif, script, bold, thin, handwritten, etc.
- **Text Placement**: Top, bottom, center, corner?
- **Text Color**: What color and how does it contrast with background?
- **Text Effects**: Drop shadow, outline, background box, gradient?

## Content Elements
- **Main Subject**: What is the primary focus? (person, product, landscape, food, etc.)
- **Props/Objects**: What objects/props are visible?
- **Setting/Background**: Indoor, outdoor, studio, specific location?
- **Human Elements**: People visible? How many? Poses? Expressions? Fashion/clothing style?
- **Brand Elements**: Logos, products, packaging visible?

## Visual Patterns & Trends
- **Composition Pattern**: Grid pattern, symmetry, leading lines, diagonal composition?
- **Repetition**: Repeated elements or patterns?
- **Texture**: Smooth, rough, organic, geometric?
- **Depth**: Flat 2D or three-dimensional depth?

## Video-Specific (if applicable)
- **Thumbnail Style**: First frame analysis
- **Play Button Position**: Center or off-center?
- **Duration**: If visible, how long is the video?
- **Motion Indicators**: Any signs of what the video contains?

# CONTENT STRATEGY ANALYSIS
- **Hook/Attention Grabber**: What grabs attention first?
- **Emotional Appeal**: What emotion is being targeted? (inspiration, humor, FOMO, curiosity, desire, etc.)
- **Target Audience**: Who is this content for? (demographics, interests)
- **Content Category**: Fashion, food, travel, tech, lifestyle, business, education, entertainment, etc.
- **Call-to-Action**: Any CTA in caption or image?
- **Trend Alignment**: Does this follow current visual trends?

# RECREATION INSTRUCTIONS
Provide a step-by-step guide to recreate this post:
- Camera/equipment needed
- Lighting setup
- Editing steps (filters, adjustments)
- Props/materials needed
- Composition tips

Return ONLY valid JSON in this format:
{
  "caption": "full text",
  "hashtags": ["#tag1", "#tag2"],
  "likes": "count",
  "comments": "count",
  "type": "video/image/carousel",
  "creator": "username",
  "timestamp": "when posted",
  "comments_data": [
    {
      "text": "comment text",
      "likes": "like count",
      "author": "username"
    }
  ],
  "text_in_images": [
    {
      "text": "exact text content found in image",
      "location": "where it appears (top, bottom, center, etc.)",
      "font_style": "bold, italic, handwritten, etc.",
      "text_color": "color of the text",
      "size": "large, medium, small relative to other elements",
      "context": "main content, background, overlay, etc.",
      "image_number": 1
    }
  ],
  
  "visual_analysis": {
    "color_palette": {
      "dominant_colors": ["color1", "color2", "color3"],
      "temperature": "warm/cool/neutral",
      "saturation": "high/medium/low",
      "mood": "description"
    },
    "composition": {
      "subject_placement": "description",
      "framing": "type",
      "orientation": "portrait/landscape/square",
      "negative_space": "description",
      "layering": "description"
    },
    "style": {
      "photography_style": "description",
      "lighting": "description",
      "filters_editing": "description",
      "sharpness": "description"
    },
    "typography": {
      "has_text_overlay": true/false,
      "font_style": "description",
      "text_placement": "location",
      "text_color": "color",
      "text_effects": "description"
    },
    "content": {
      "main_subject": "description",
      "props_objects": ["item1", "item2"],
      "setting": "description",
      "human_elements": "description",
      "brand_elements": "description"
    },
    "patterns": {
      "composition_pattern": "description",
      "repetition": "description",
      "texture": "description",
      "depth": "description"
    }
  },
  
  "strategy_analysis": {
    "hook": "what grabs attention",
    "emotional_appeal": "emotion targeted",
    "target_audience": "who this is for",
    "content_category": "category",
    "call_to_action": "CTA if any",
    "trend_alignment": "how it follows trends"
  },
  
  "recreation_guide": {
    "equipment": "what you need",
    "lighting_setup": "how to light it",
    "editing_steps": "post-processing steps",
    "props_materials": "what to gather",
    "composition_tips": "how to frame it"
  }
}

Analyze DEEPLY. Provide specific details that would allow someone to recreate this exact aesthetic.
"""
            
            # Send to Gemini Vision
            response = vision_model.generate_content([prompt, img])
            
            # Parse the response
            response_text = response.text.strip()
            
            # Try to extract JSON from response
            # Sometimes Gemini wraps JSON in ```json ... ```
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                response_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Parse JSON
            try:
                gemini_data = json.loads(response_text)
                
                # Add ALL Gemini's analysis to post_data
                post_data['caption'] = gemini_data.get('caption')
                post_data['hashtags'] = gemini_data.get('hashtags', [])
                post_data['likes'] = gemini_data.get('likes')
                post_data['comments_info'] = gemini_data.get('comments')
                post_data['type'] = gemini_data.get('type')
                post_data['creator'] = gemini_data.get('creator')
                post_data['timestamp'] = gemini_data.get('timestamp')
                
                # Text extraction from images (OCR)
                post_data['text_in_images'] = gemini_data.get('text_in_images', [])
                
                # Visual analysis
                post_data['visual_analysis'] = gemini_data.get('visual_analysis', {})
                post_data['strategy_analysis'] = gemini_data.get('strategy_analysis', {})
                post_data['recreation_guide'] = gemini_data.get('recreation_guide', {})
                
                post_data['gemini_raw_response'] = response_text
                
                print("✅ Gemini Vision Analysis Complete:")
                if post_data['creator']:
                    print(f"   👤 Creator: {post_data['creator']}")
                if post_data['caption']:
                    print(f"   📝 Caption: {post_data['caption'][:80]}{'...' if len(post_data['caption']) > 80 else ''}")
                if post_data['hashtags']:
                    print(f"   🏷️  Hashtags: {', '.join(post_data['hashtags'][:3])}...")
                if post_data['likes']:
                    print(f"   ❤️  Likes: {post_data['likes']}")
                if post_data['type']:
                    print(f"   🎬 Type: {post_data['type']}")
                
                # Display extracted text from images
                if post_data.get('text_in_images'):
                    print(f"   📖 Text in Images ({len(post_data['text_in_images'])} found):")
                    for i, text_item in enumerate(post_data['text_in_images'][:3], 1):  # Show first 3
                        text_preview = text_item.get('text', '')[:50]
                        location = text_item.get('location', 'unknown')
                        print(f"      {i}. \"{text_preview}{'...' if len(text_item.get('text', '')) > 50 else ''}\" ({location})")
                    if len(post_data['text_in_images']) > 3:
                        print(f"      ... and {len(post_data['text_in_images']) - 3} more text elements")
                
                # Visual analysis summary
                if post_data.get('visual_analysis'):
                    va = post_data['visual_analysis']
                    if va.get('color_palette'):
                        colors = va['color_palette'].get('dominant_colors', [])
                        if colors:
                            print(f"   🎨 Colors: {', '.join(colors[:3])}")
                    if va.get('style'):
                        style = va['style'].get('photography_style')
                        if style:
                            print(f"   📸 Style: {style}")
                
                # Strategy summary
                if post_data.get('strategy_analysis'):
                    sa = post_data['strategy_analysis']
                    if sa.get('content_category'):
                        print(f"   📂 Category: {sa['content_category']}")
                    if sa.get('emotional_appeal'):
                        print(f"   💭 Emotion: {sa['emotional_appeal']}")
                
            except json.JSONDecodeError as e:
                print(f"⚠️  Could not parse Gemini JSON response: {e}")
                print(f"   Raw response: {response_text[:200]}...")
                post_data['gemini_raw_response'] = response_text
                post_data['gemini_parse_error'] = str(e)
                
        except Exception as e:
            print(f"❌ Gemini Vision analysis failed: {e}")
            post_data['gemini_error'] = str(e)
        
        print(f"\n✅ Successfully analyzed post {index}/{total}")
        
    except Exception as e:
        print(f"\n❌ Error analyzing post {index}/{total}: {e}")
        post_data['error'] = str(e)
    
    return post_data


def analyze_trends(all_posts):
    """
    Analyze trends across all collected posts using Gemini
    """
    print("\n" + "="*60)
    print("📊 ANALYZING TRENDS ACROSS ALL POSTS")
    print("="*60)
    
    # Prepare summary data for Gemini
    posts_summary = []
    for post in all_posts:
        if 'error' not in post or post.get('visual_analysis'):
            summary = {
                'url': post.get('url'),
                'type': post.get('type'),
                'likes': post.get('likes'),
                'category': post.get('strategy_analysis', {}).get('content_category'),
                'colors': post.get('visual_analysis', {}).get('color_palette', {}).get('dominant_colors', []),
                'style': post.get('visual_analysis', {}).get('style', {}),
                'composition': post.get('visual_analysis', {}).get('composition', {}),
                'emotional_appeal': post.get('strategy_analysis', {}).get('emotional_appeal'),
                'hashtags': post.get('hashtags', []),
                'text_in_images': post.get('text_in_images', [])
            }
            posts_summary.append(summary)
    
    if not posts_summary:
        print("❌ No posts with visual analysis to aggregate")
        return None
    
    print(f"📋 Analyzing {len(posts_summary)} posts for trends...")
    
    # Create comprehensive trend analysis prompt
    trend_prompt = f"""
You are analyzing {len(posts_summary)} Instagram posts to identify VISUAL and CONTENT TRENDS.

Here is the data from all posts:
{json.dumps(posts_summary, indent=2)}

# AGGREGATE TREND ANALYSIS

Analyze ALL posts together and identify:

## 1. COLOR TRENDS
- **Most Popular Colors**: What colors appear most frequently?
- **Color Combinations**: What color palettes are trending?
- **Color Psychology**: What emotions are brands targeting with these colors?
- **Color Temperature Trend**: Are warm, cool, or neutral tones dominating?
- **Saturation Trend**: High saturation (vibrant) vs low saturation (muted/pastel)?

## 2. VISUAL STYLE TRENDS
- **Photography Styles**: Which styles are most common? (minimalist, lifestyle, studio, etc.)
- **Lighting Trends**: What lighting setups are popular?
- **Filter/Editing Trends**: Natural vs heavily edited? Specific filter styles?
- **Composition Trends**: Common framing and layout patterns?

## 3. CONTENT CATEGORY TRENDS
- **Top Categories**: What content types dominate? (fashion, food, tech, etc.)
- **Category Insights**: What makes each category's content unique?

## 4. ENGAGEMENT PATTERNS
- **High Performers**: What visual characteristics do highly-liked posts share?
- **Low Performers**: What to avoid?
- **Engagement Drivers**: What visual elements correlate with higher engagement?

## 5. HASHTAG TRENDS
- **Most Used Hashtags**: Which hashtags appear most frequently?
- **Hashtag Patterns**: Broad vs niche, number of hashtags?

## 6. EMOTIONAL APPEAL TRENDS
- **Dominant Emotions**: What emotions are brands/creators targeting?
- **Emotional Strategies**: How are they evoking these emotions visually?

## 7. TEXT IN IMAGES TRENDS (OCR ANALYSIS)
- **Text Usage Patterns**: How often do posts include text within images?
- **Text Types**: What types of text are most common? (quotes, captions, labels, etc.)
- **Text Placement**: Where is text typically placed in images? (top, bottom, center)
- **Text Styles**: What font styles and colors are trending?
- **Text Content Themes**: What topics or messages are conveyed through image text?
- **Text Engagement**: Do posts with text in images get more engagement?
- **Text Overlay Trends**: Popular text overlay techniques and styles

## 8. TREND CLUSTERS
Group similar posts together and identify distinct visual "trends" or "aesthetics":
- Trend 1: [Name] - Description, examples, characteristics
- Trend 2: [Name] - Description, examples, characteristics
- etc.

## 8. ACTIONABLE RECOMMENDATIONS
Based on all trends, provide:
- **Color Palette Recommendations**: Specific colors to use
- **Visual Style Recommendations**: Which styles to adopt
- **Content Strategy**: What to post for maximum engagement
- **Recreation Blueprint**: Step-by-step guide to create trending content

Return ONLY valid JSON:
{{
  "color_trends": {{
    "most_popular_colors": ["color1", "color2", "color3"],
    "trending_combinations": [["color1", "color2"], ["color3", "color4"]],
    "color_psychology": "analysis",
    "temperature_trend": "warm/cool/neutral dominance",
    "saturation_trend": "high/medium/low dominance"
  }},
  
  "visual_style_trends": {{
    "dominant_photography_styles": ["style1", "style2"],
    "lighting_trends": "description",
    "editing_trends": "description",
    "composition_trends": "description"
  }},
  
  "content_trends": {{
    "top_categories": ["category1", "category2"],
    "category_insights": "analysis"
  }},
  
  "engagement_patterns": {{
    "high_performer_traits": ["trait1", "trait2"],
    "low_performer_traits": ["trait1", "trait2"],
    "engagement_drivers": "analysis"
  }},
  
  "hashtag_trends": {{
    "most_used": ["#tag1", "#tag2", "#tag3"],
    "patterns": "analysis"
  }},
  
  "emotional_trends": {{
    "dominant_emotions": ["emotion1", "emotion2"],
    "visual_strategies": "how these emotions are conveyed"
  }},
  
  "text_in_images_trends": {{
    "text_usage_frequency": "percentage of posts with text in images",
    "common_text_types": ["quotes", "captions", "labels", "etc"],
    "text_placement_trends": "where text is typically placed",
    "text_style_trends": "popular font styles and colors",
    "text_content_themes": "common topics in image text",
    "text_engagement_correlation": "do posts with text get more engagement?",
    "text_overlay_techniques": "popular text overlay styles"
  }},
  
  "trend_clusters": [
    {{
      "name": "Trend Name",
      "description": "detailed description",
      "example_posts": ["url1", "url2"],
      "characteristics": {{
        "colors": ["colors"],
        "style": "style",
        "composition": "composition",
        "mood": "mood"
      }}
    }}
  ],
  
  "recommendations": {{
    "color_palette": ["specific colors with hex if possible"],
    "visual_style": "which styles to use",
    "content_strategy": "what to post",
    "recreation_blueprint": {{
      "step1": "description",
      "step2": "description",
      "step3": "description"
    }}
  }}
}}

Be SPECIFIC and ACTIONABLE. This analysis should enable someone to create viral content.
"""
    
    try:
        # Send to Gemini for trend analysis
        print("🤖 Sending to Gemini for trend aggregation...")
        response = vision_model.generate_content(trend_prompt)
        response_text = response.text.strip()
        
        # Extract JSON
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        elif '```' in response_text:
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        
        # Parse trends
        trends = json.loads(response_text)
        
        print("\n✅ TREND ANALYSIS COMPLETE!")
        print("="*60)
        
        # Print summary
        if trends.get('color_trends'):
            print("\n🎨 COLOR TRENDS:")
            ct = trends['color_trends']
            if ct.get('most_popular_colors'):
                print(f"   Most Popular: {', '.join(ct['most_popular_colors'][:5])}")
            if ct.get('temperature_trend'):
                print(f"   Temperature: {ct['temperature_trend']}")
        
        if trends.get('visual_style_trends'):
            print("\n📸 VISUAL STYLE TRENDS:")
            vst = trends['visual_style_trends']
            if vst.get('dominant_photography_styles'):
                print(f"   Styles: {', '.join(vst['dominant_photography_styles'][:3])}")
        
        if trends.get('content_trends'):
            print("\n📂 CONTENT TRENDS:")
            ct = trends['content_trends']
            if ct.get('top_categories'):
                print(f"   Top Categories: {', '.join(ct['top_categories'][:5])}")
        
        if trends.get('text_in_images_trends'):
            print("\n📖 TEXT IN IMAGES TRENDS:")
            tit = trends['text_in_images_trends']
            if tit.get('text_usage_frequency'):
                print(f"   Usage: {tit['text_usage_frequency']}")
            if tit.get('common_text_types'):
                print(f"   Common Types: {', '.join(tit['common_text_types'][:3])}")
            if tit.get('text_placement_trends'):
                print(f"   Placement: {tit['text_placement_trends']}")
        
        if trends.get('trend_clusters'):
            print(f"\n🎯 IDENTIFIED {len(trends['trend_clusters'])} DISTINCT TRENDS:")
            for i, cluster in enumerate(trends['trend_clusters'][:5], 1):
                print(f"   {i}. {cluster.get('name', 'Unnamed')}: {cluster.get('description', '')[:80]}...")
        
        print("="*60)
        
        return trends
        
    except Exception as e:
        print(f"❌ Trend analysis failed: {e}")
        return None


def save_progress(all_results, trends=None):
    """Save analysis progress to files (thread-safe)"""
    with save_lock:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save main results file
        results_file = f'instagram_analysis_{timestamp}.json'
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_posts': len(all_results),
            'successful': sum(1 for r in all_results if 'error' not in r or r.get('caption') is not None),
            'failed': sum(1 for r in all_results if 'error' in r and r.get('caption') is None),
            'posts': all_results,
            'aggregated_trends': trends
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return results_file


def save_unprocessed_urls(all_urls, processed_urls):
    """Save list of URLs that haven't been processed yet (thread-safe)"""
    with save_lock:
        unprocessed = [url for url in all_urls if url not in processed_urls]
        
        with open('instagram_unprocessed_urls.txt', 'w') as f:
            for url in unprocessed:
                f.write(url + '\n')
        
        print(f"💾 Saved {len(unprocessed)} unprocessed URLs to: instagram_unprocessed_urls.txt")
        return unprocessed


def load_existing_urls():
    """Load previously collected URLs if available"""
    if os.path.exists('instagram_explore_urls.txt'):
        with open('instagram_explore_urls.txt', 'r') as f:
            urls = set(line.strip() for line in f if line.strip())
        print(f"📂 Loaded {len(urls)} existing URLs from previous run")
        return urls
    return set()


def load_processed_urls():
    """Load URLs that have already been analyzed"""
    processed = set()
    
    # Look for existing analysis files
    analysis_files = glob.glob('instagram_analysis_*.json')
    
    if analysis_files:
        # Load the most recent one
        latest_file = max(analysis_files, key=os.path.getmtime)
        print(f"📂 Loading processed URLs from: {latest_file}")
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for post in data.get('posts', []):
                    if post.get('url'):
                        processed.add(post['url'])
            print(f"✅ Found {len(processed)} already processed URLs")
        except Exception as e:
            print(f"⚠️  Could not load previous results: {e}")
    
    return processed


async def analyze_post_worker(context, url, index, total, all_results, processed_urls, post_urls_list):
    """Worker function to analyze a single post in parallel"""
    # Create a new page for this worker
    page = await context.new_page()
    
    try:
        # Analyze the post with retry logic
        max_retries = 2
        result = None
        
        for attempt in range(max_retries):
            try:
                result = await analyze_post(page, url, index, total)
                
                # If successful (no error or minor error), break
                if 'error' not in result or result.get('caption') is not None:
                    break
                    
                # If first attempt failed, retry
                if attempt < max_retries - 1:
                    print(f"   ⚠️  Retry attempt {attempt + 2}/{max_retries}...")
                    await page.wait_for_timeout(2000)
                    
            except Exception as e:
                print(f"   ❌ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"   ⚠️  Retrying...")
                    await page.wait_for_timeout(2000)
                else:
                    result = {
                        'url': url,
                        'timestamp': datetime.now().isoformat(),
                        'index': index,
                        'error': str(e)
                    }
        
        if result:
            # Thread-safe append to results
            with save_lock:
                all_results.append(result)
                processed_urls.add(url)
            
            # Save progress after each post (incremental save)
            results_file = save_progress(all_results)
            print(f"   💾 Progress saved ({len(all_results)} posts): {results_file}")
            
            # Update unprocessed URLs list
            save_unprocessed_urls(post_urls_list, processed_urls)
        
        return result
        
    finally:
        # Close the page when done
        await page.close()


async def analyze_posts_parallel(context, urls_to_process, post_urls_list, all_results, processed_urls, concurrent_workers=3):
    """Analyze multiple posts in parallel using multiple browser pages"""
    print(f"\n🚀 Starting parallel analysis with {concurrent_workers} concurrent workers")
    
    # Create batches of URLs to process
    total_urls = len(urls_to_process)
    current_index = len(all_results) + 1
    
    # Process URLs in batches
    for batch_start in range(0, total_urls, concurrent_workers):
        batch_end = min(batch_start + concurrent_workers, total_urls)
        batch = urls_to_process[batch_start:batch_end]
        
        print(f"\n📦 Processing batch {batch_start // concurrent_workers + 1} ({batch_start + 1}-{batch_end}/{total_urls})")
        
        # Create tasks for parallel execution
        tasks = []
        for i, url in enumerate(batch):
            index = current_index + batch_start + i
            task = analyze_post_worker(context, url, index, len(post_urls_list), all_results, processed_urls, post_urls_list)
            tasks.append(task)
        
        # Run batch in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Error in parallel task: {result}")
        
        # Small delay between batches to avoid rate limiting
        await asyncio.sleep(2)
    
    print(f"\n✅ Parallel analysis complete! Processed {total_urls} posts")


async def login_to_instagram():
    """Login to Instagram using Playwright"""
    
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("❌ Instagram credentials not found in .env file")
        print("Please add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to your .env file")
        return
    
    # Load existing data if available
    existing_urls = load_existing_urls()
    processed_urls = load_processed_urls()
    
    if processed_urls:
        print(f"🔄 Resume mode: {len(processed_urls)} posts already analyzed")
        resume = input("Do you want to continue from where you left off? (y/n): ").lower().strip()
        if resume != 'y':
            processed_urls = set()
            print("Starting fresh analysis...")
    
    async with async_playwright() as p:
        # Launch browser
        print("🚀 Launching browser...")
        browser = await p.chromium.launch(headless=False)
        
        # Create context with proper viewport and user agent
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Navigate to Instagram
        print("📱 Navigating to Instagram...")
        await page.goto('https://www.instagram.com/')
        await page.wait_for_timeout(3000)
        
        # Handle cookies popup if it appears
        try:
            accept_cookies = page.locator('button:has-text("Allow all cookies")')
            if await accept_cookies.is_visible(timeout=2000):
                print("🍪 Accepting cookies...")
                await accept_cookies.click()
                await page.wait_for_timeout(1000)
        except:
            pass
        
        # Fill in username
        print(f"👤 Entering username: {INSTAGRAM_USERNAME}")
        await page.fill('input[name="username"]', INSTAGRAM_USERNAME)
        await page.wait_for_timeout(500)
        
        # Fill in password
        print("🔒 Entering password...")
        await page.fill('input[name="password"]', INSTAGRAM_PASSWORD)
        await page.wait_for_timeout(500)
        
        # Click login button
        print("🔑 Clicking login button...")
        await page.click('button[type="submit"]')
        
        # Wait for navigation
        print("⏳ Waiting for login...")
        await page.wait_for_timeout(5000)
        
        # Handle "Save Your Login Info" popup
        try:
            not_now_button = page.locator('button:has-text("Not now"), button:has-text("Not Now")')
            if await not_now_button.is_visible(timeout=2000):
                print("💾 Dismissing 'Save Login Info' popup...")
                await not_now_button.first.click()
                await page.wait_for_timeout(1000)
        except:
            pass
        
        # Handle "Turn on Notifications" popup
        try:
            not_now_button = page.locator('button:has-text("Not now"), button:has-text("Not Now")')
            if await not_now_button.is_visible(timeout=2000):
                print("🔔 Dismissing 'Turn on Notifications' popup...")
                await not_now_button.first.click()
                await page.wait_for_timeout(1000)
        except:
            pass
        
        # Check if login was successful
        current_url = page.url
        if 'instagram.com' in current_url and '/accounts/login' not in current_url:
            print("✅ Login successful!")
            print(f"📍 Current URL: {current_url}")
        else:
            print("❌ Login may have failed")
            print(f"📍 Current URL: {current_url}")
            await browser.close()
            return
        
        # Navigate to Explore page
        print("\n🔍 Navigating to Explore page...")
        await page.goto('https://www.instagram.com/explore/')
        await page.wait_for_timeout(3000)
        
        # Collect post URLs by scrolling
        print("📋 Collecting post URLs by scrolling...")
        post_urls = existing_urls.copy()  # Start with any existing URLs
        initial_count = len(post_urls)
        scroll_count = 0
        max_scrolls = 200  # Will scroll up to 200 times to get 500+ posts
        target_posts = 500
        
        print(f"🎯 Target: {target_posts} posts (max {max_scrolls} scrolls)")
        if initial_count > 0:
            print(f"📂 Starting with {initial_count} existing URLs")
        
        output_file = 'instagram_explore_urls.txt'
        
        while len(post_urls) < target_posts and scroll_count < max_scrolls:
            # Extract URLs from current view
            post_links = await page.locator('a[href*="/p/"]').all()
            
            new_urls = 0
            for link in post_links:
                href = await link.get_attribute('href')
                if href and '/p/' in href:
                    # Convert to full URL if needed
                    if href.startswith('/'):
                        full_url = f'https://www.instagram.com{href}'
                    else:
                        full_url = href
                    
                    # Remove query parameters to get clean URL
                    if '?' in full_url:
                        full_url = full_url.split('?')[0]
                    
                    # Add trailing slash if not present
                    if not full_url.endswith('/'):
                        full_url += '/'
                    
                    if full_url not in post_urls:
                        post_urls.add(full_url)
                        new_urls += 1
            
            scroll_count += 1
            print(f"   Scroll {scroll_count}/{max_scrolls}: Found {len(post_urls)} total URLs (+{new_urls} new)")
            
            # Save URLs after each scroll (incremental save)
            output_file = 'instagram_explore_urls.txt'
            with open(output_file, 'w') as f:
                for url in sorted(post_urls):
                    f.write(url + '\n')
            
            # Scroll down to load more posts
            if len(post_urls) < target_posts and scroll_count < max_scrolls:
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await page.wait_for_timeout(2000)  # Wait for new posts to load
        
        print(f"✅ Collected {len(post_urls)} post URLs after {scroll_count} scrolls")
        print(f"💾 URLs saved incrementally to: {output_file}")
        
        # Print first 10 URLs as preview
        print("\n📝 Preview (first 10 URLs):")
        for i, url in enumerate(sorted(post_urls)[:10], 1):
            print(f"   {i}. {url}")
        
        if len(post_urls) > 10:
            print(f"   ... and {len(post_urls) - 10} more")
        
        # Analyze each post
        print("\n" + "="*60)
        print("📊 STARTING POST ANALYSIS")
        print("="*60)
        
        # Load existing results if resuming
        all_results = []
        if processed_urls:
            # Try to load previous results
            analysis_files = glob.glob('instagram_analysis_*.json')
            if analysis_files:
                latest_file = max(analysis_files, key=os.path.getmtime)
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_results = data.get('posts', [])
                    print(f"📂 Loaded {len(all_results)} previous results from {latest_file}")
                except Exception as e:
                    print(f"⚠️  Could not load previous results: {e}")
        
        successful = sum(1 for r in all_results if 'error' not in r or r.get('caption') is not None)
        failed = sum(1 for r in all_results if 'error' in r and r.get('caption') is None)
        
        post_urls_list = sorted(post_urls)
        
        # Filter out already processed URLs
        urls_to_process = [url for url in post_urls_list if url not in processed_urls]
        
        if urls_to_process:
            print(f"📋 {len(urls_to_process)} URLs to process ({len(processed_urls)} already done)")
        else:
            print(f"✅ All {len(post_urls_list)} URLs already processed!")
        
        # Save unprocessed URLs at start
        save_unprocessed_urls(post_urls_list, processed_urls)
        
        # Use parallel processing if there are URLs to process
        if urls_to_process:
            await analyze_posts_parallel(context, urls_to_process, post_urls_list, all_results, processed_urls, CONCURRENT_WORKERS)
        
        # Update stats
        successful = sum(1 for r in all_results if 'error' not in r or r.get('caption') is not None)
        failed = sum(1 for r in all_results if 'error' in r and r.get('caption') is None)
        
        # Analyze trends across all posts
        trends = analyze_trends(all_results)
        
        # Save final results with trends
        results_file = save_progress(all_results, trends)
        
        # Print summary
        print("\n" + "="*60)
        print("📊 FINAL ANALYSIS COMPLETE")
        print("="*60)
        print(f"✅ Total posts analyzed: {len(post_urls_list)}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        
        if trends:
            print(f"\n🎯 TRENDS IDENTIFIED:")
            if trends.get('trend_clusters'):
                print(f"   {len(trends['trend_clusters'])} distinct visual trends found")
            if trends.get('color_trends', {}).get('most_popular_colors'):
                colors = trends['color_trends']['most_popular_colors'][:3]
                print(f"   Top colors: {', '.join(colors)}")
            if trends.get('recommendations'):
                print(f"   ✅ Actionable recommendations generated")
        
        print(f"\n💾 Results saved to: {results_file}")
        print(f"📸 Screenshots saved to: screenshots/")
        print("="*60)
        
        # Keep browser open for 10 seconds so you can see the result
        print("\n⏰ Keeping browser open for 10 seconds...")
        await page.wait_for_timeout(10000)
        
        # Close browser
        await browser.close()
        print("👋 Browser closed")


if __name__ == "__main__":
    asyncio.run(login_to_instagram())

