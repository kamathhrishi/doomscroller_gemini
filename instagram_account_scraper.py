"""
Instagram Account Scraper
Scrapes posts from specific Instagram accounts and saves to CSV
"""

import os
import sys
import json
import csv
import time
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

class InstagramAccountScraper:
    def __init__(self, account_id='generic'):
        """Initialize the scraper for a specific account"""
        self.account_id = account_id
        self.save_dir = f'data/accounts/{account_id}' if account_id != 'generic' else '.'
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Session file paths
        self.session_file = 'instagram_session.json'
        
        # Progress tracking
        self.progress_file = os.path.join(self.save_dir, 'scraping_progress.json')
        self.progress_data = self.load_progress()
        self.progress_lock = threading.Lock()  # Thread-safe progress saving
        
        print(f"🎯 Scraping for account: {account_id}")
        print(f"💾 Save directory: {self.save_dir}")
    
    def load_progress(self):
        """Load progress from previous run if exists"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    print(f"📂 Found previous progress: {progress.get('completed_accounts', 0)} accounts, {progress.get('total_posts', 0)} posts")
                    return progress
            except Exception as e:
                print(f"⚠️ Could not load progress: {e}")
        return {
            'completed_accounts': [],
            'completed_posts': [],
            'total_posts': 0,
            'last_account': None,
            'all_posts': []
        }
    
    def save_progress(self, account=None, post=None):
        """Save incremental progress (thread-safe)"""
        with self.progress_lock:
            try:
                if account:
                    if account not in self.progress_data['completed_accounts']:
                        self.progress_data['completed_accounts'].append(account)
                    self.progress_data['last_account'] = account
                
                if post:
                    post_id = f"{post['username']}_{post['url'].split('/p/')[-1].strip('/')}"
                    if post_id not in self.progress_data['completed_posts']:
                        self.progress_data['completed_posts'].append(post_id)
                        self.progress_data['all_posts'].append(post)
                        self.progress_data['total_posts'] = len(self.progress_data['all_posts'])
                
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(self.progress_data, f, indent=2, ensure_ascii=False)
                
            except Exception as e:
                print(f"⚠️ Could not save progress: {e}")
    
    def clear_progress(self):
        """Clear progress file to start fresh"""
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)
            print("🗑️ Progress file cleared")
    
    def load_session(self):
        """Load existing session if available"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load session: {e}")
        return None
    
    def handle_signup_modal(self, page):
        """Detect and close Instagram sign-up modal/popup if present"""
        try:
            print("🔍 Checking for sign-up modal...")
            
            # Common selectors for Instagram sign-up modals and popups
            signup_selectors = [
                'button[aria-label="Close"]',
                'button[aria-label="Not Now"]', 
                'button:has-text("Not Now")',
                'button:has-text("Not now")',
                'button:has-text("Close")',
                'button:has-text("Skip")',
                'button:has-text("Skip for now")',
                'div[role="dialog"] button[aria-label="Close"]',
                'div[role="dialog"] button:has-text("Not Now")',
                'div[role="dialog"] button:has-text("Close")',
                'svg[aria-label="Close"]',
                'button[class*="close"]',
                'button[class*="dismiss"]',
                'div[class*="modal"] button',
                'div[class*="popup"] button',
                'div[class*="overlay"] button'
            ]
            
            modal_closed = False
            
            # Try each selector with a short timeout
            for selector in signup_selectors:
                try:
                    element = page.query_selector(selector)
                    if element and element.is_visible():
                        print(f"✓ Found sign-up modal with selector: {selector}")
                        element.click()
                        print("✓ Closed sign-up modal")
                        modal_closed = True
                        time.sleep(1)  # Wait for modal to close
                        break
                except Exception as e:
                    continue
            
            # Additional check for "Turn on Notifications" modal
            try:
                notifications_button = page.query_selector('button:has-text("Not Now"), button:has-text("Not now")')
                if notifications_button and notifications_button.is_visible():
                    print("✓ Found notifications modal")
                    notifications_button.click()
                    print("✓ Closed notifications modal")
                    modal_closed = True
                    time.sleep(1)
            except:
                pass
            
            # Check for "Save Login Info" modal
            try:
                save_login_button = page.query_selector('button:has-text("Not Now"), button:has-text("Not now")')
                if save_login_button and save_login_button.is_visible():
                    print("✓ Found save login modal")
                    save_login_button.click()
                    print("✓ Closed save login modal")
                    modal_closed = True
                    time.sleep(1)
            except:
                pass
            
            if not modal_closed:
                print("ℹ️ No sign-up modal detected")
            
            return modal_closed
            
        except Exception as e:
            print(f"⚠️ Error handling sign-up modal: {e}")
            return False
    
    def take_screenshot_after_modal(self, page, username="instagram", step="after_modal"):
        """Take a screenshot after handling modals"""
        try:
            screenshot_dir = os.path.join(self.save_dir, 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(screenshot_dir, f'{username}_{step}_{timestamp}.png')
            
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            print(f"⚠️ Error taking screenshot: {e}")
            return None
    
    def scrape_profile_posts(self, page, username, num_posts=5):
        """Scrape posts from a specific Instagram profile"""
        print(f"\n📸 Scraping @{username}...")
        
        # Navigate to profile
        profile_url = f"https://www.instagram.com/{username}/"
        try:
            page.goto(profile_url, wait_until='networkidle', timeout=30000)
            time.sleep(3)
        except Exception as e:
            print(f"❌ Failed to load profile {username}: {e}")
            return []
        
        # Handle any sign-up modals that might appear
        modal_closed = self.handle_signup_modal(page)
        
        # Take screenshot after handling modals
        if modal_closed:
            self.take_screenshot_after_modal(page, username, "after_modal_close")
        else:
            self.take_screenshot_after_modal(page, username, "no_modal_detected")
        
        # Check if profile exists
        if "Sorry, this page isn't available" in page.content():
            print(f"❌ Profile @{username} not found")
            return []
        
        posts = []
        
        try:
            # Wait for posts grid
            page.wait_for_selector('article a[href*="/p/"]', timeout=10000)
            
            # Get post links
            post_links = page.query_selector_all('article a[href*="/p/"]')
            print(f"✓ Found {len(post_links)} posts on profile")
            
            # Limit to requested number
            post_links = post_links[:num_posts]
            
            for idx, link in enumerate(post_links, 1):
                try:
                    post_url = link.get_attribute('href')
                    if not post_url.startswith('http'):
                        post_url = f"https://www.instagram.com{post_url}"
                    
                    print(f"  [{idx}/{len(post_links)}] Scraping post: {post_url}")
                    
                    # Open post in new page
                    post_page = page.context.new_page()
                    post_page.goto(post_url, wait_until='networkidle', timeout=30000)
                    time.sleep(3)
                    
                    # Take screenshot first for vision analysis
                    screenshot_path = os.path.join(self.save_dir, 'screenshots', f'{username}_post_{idx}.png')
                    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                    post_page.screenshot(path=screenshot_path, full_page=False)
                    
                    # Extract post data with vision analysis
                    post_data = self.extract_post_data(post_page, username, screenshot_path, post_url)
                    if post_data:
                        posts.append(post_data)
                        # Save progress after each post
                        self.save_progress(post=post_data)
                        print(f"      💾 Progress saved ({len(self.progress_data['all_posts'])} total posts)")
                    
                    post_page.close()
                    time.sleep(3)  # Rate limiting
                    
                except Exception as e:
                    print(f"    ⚠️ Error scraping post: {e}")
                    continue
            
            print(f"✓ Scraped {len(posts)} posts from @{username}")
            
        except Exception as e:
            print(f"❌ Error scraping profile {username}: {e}")
        
        return posts
    
    def extract_post_data(self, page, username, screenshot_path, post_url):
        """Extract comprehensive data from a single post with vision analysis"""
        try:
            post_data = {
                'username': username,
                'url': post_url,
                'screenshot': screenshot_path,
                'caption': '',
                'hashtags': [],
                'likes': 0,
                'comments_count': 0,
                'top_comments': [],
                'media_type': 'image',
                'timestamp': '',
                'location': '',
                'mentions': [],
                'scraped_at': datetime.now().isoformat()
            }
            
            # Wait for content to load
            time.sleep(2)
            
            print(f"      📸 Screenshot saved: {screenshot_path}")
            
            # Extract full caption with hashtags
            try:
                # Try multiple selectors for caption
                caption_selectors = [
                    'h1',
                    'span[dir="auto"]',
                    'div[class*="Caption"] span',
                    'article span:has-text("#")'
                ]
                
                caption_text = ''
                for selector in caption_selectors:
                    caption_elem = page.query_selector(selector)
                    if caption_elem:
                        text = caption_elem.inner_text().strip()
                        if len(text) > len(caption_text):
                            caption_text = text
                
                post_data['caption'] = caption_text
                
                # Extract hashtags from caption
                import re
                hashtags = re.findall(r'#(\w+)', caption_text)
                post_data['hashtags'] = hashtags
                
                # Extract mentions
                mentions = re.findall(r'@(\w+)', caption_text)
                post_data['mentions'] = mentions
                
            except Exception as e:
                print(f"      ⚠️ Caption extraction error: {e}")
            
            # Extract likes
            try:
                # Try multiple patterns for likes
                likes_patterns = [
                    'button:has-text("likes")',
                    'a:has-text("likes")',
                    'span:has-text("likes")',
                    'section button span'
                ]
                
                for pattern in likes_patterns:
                    likes_elem = page.query_selector(pattern)
                    if likes_elem:
                        likes_text = likes_elem.inner_text()
                        # Handle K, M suffixes
                        if 'K' in likes_text or 'k' in likes_text:
                            num = float(''.join(filter(lambda x: x.isdigit() or x == '.', likes_text.split()[0])))
                            post_data['likes'] = int(num * 1000)
                        elif 'M' in likes_text or 'm' in likes_text:
                            num = float(''.join(filter(lambda x: x.isdigit() or x == '.', likes_text.split()[0])))
                            post_data['likes'] = int(num * 1000000)
                        else:
                            likes_num = ''.join(filter(str.isdigit, likes_text.split()[0]))
                            if likes_num:
                                post_data['likes'] = int(likes_num)
                        break
            except Exception as e:
                print(f"      ⚠️ Likes extraction error: {e}")
            
            # Extract comments count
            try:
                comments_elem = page.query_selector('span:has-text("comments"), span:has-text("comment")')
                if comments_elem:
                    comments_text = comments_elem.inner_text()
                    comments_num = ''.join(filter(str.isdigit, comments_text.split()[0]))
                    if comments_num:
                        post_data['comments_count'] = int(comments_num)
            except:
                pass
            
            # Extract top comments (first 3)
            try:
                comment_elements = page.query_selector_all('div[role="button"] span')
                comments_list = []
                for elem in comment_elements[:6]:  # Get more to filter
                    comment_text = elem.inner_text().strip()
                    if len(comment_text) > 10 and comment_text not in ['likes', 'Reply', 'View replies']:
                        comments_list.append(comment_text)
                        if len(comments_list) >= 3:
                            break
                post_data['top_comments'] = comments_list
            except:
                pass
            
            # Extract timestamp
            try:
                time_elem = page.query_selector('time')
                if time_elem:
                    post_data['timestamp'] = time_elem.get_attribute('datetime')
            except:
                pass
            
            # Extract location
            try:
                location_elem = page.query_selector('a:has-text("•")')
                if location_elem:
                    post_data['location'] = location_elem.inner_text().strip()
            except:
                pass
            
            # Detect media type
            try:
                if page.query_selector('video'):
                    post_data['media_type'] = 'video'
                elif page.query_selector('button[aria-label*="Next"]'):
                    post_data['media_type'] = 'carousel'
                else:
                    post_data['media_type'] = 'image'
            except:
                pass
            
            print(f"      ✓ Extracted: {len(post_data['caption'])} chars caption, {post_data['likes']} likes, {len(post_data['hashtags'])} hashtags")
            
            # NOW DO COMPREHENSIVE VISION ANALYSIS
            print(f"      🤖 Analyzing with Gemini Vision API...")
            try:
                img = Image.open(screenshot_path)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Use the same comprehensive prompt from instagram_login.py
                vision_prompt = """
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
                
                response = model.generate_content([vision_prompt, img])
                response_text = response.text.strip()
                
                # Extract JSON from response
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif '```' in response_text:
                    json_start = response_text.find('```') + 3
                    json_end = response_text.find('```', json_start)
                    response_text = response_text[json_start:json_end].strip()
                
                # Parse and add all vision data
                try:
                    vision_data = json.loads(response_text)
                    post_data['text_in_images'] = vision_data.get('text_in_images', [])
                    post_data['visual_analysis'] = vision_data.get('visual_analysis', {})
                    post_data['strategy_analysis'] = vision_data.get('strategy_analysis', {})
                    post_data['recreation_guide'] = vision_data.get('recreation_guide', {})
                    post_data['gemini_raw_response'] = response_text
                    
                    # Update caption if vision found better one
                    if vision_data.get('caption') and len(vision_data['caption']) > len(post_data['caption']):
                        post_data['caption'] = vision_data['caption']
                    
                    print(f"      ✅ Vision analysis complete")
                    if post_data.get('text_in_images'):
                        print(f"         📖 Found {len(post_data['text_in_images'])} text elements in image")
                    if post_data.get('visual_analysis', {}).get('color_palette'):
                        colors = post_data['visual_analysis']['color_palette'].get('dominant_colors', [])
                        if colors:
                            print(f"         🎨 Colors: {', '.join(colors[:3])}")
                    
                except json.JSONDecodeError as e:
                    print(f"      ⚠️ Could not parse vision JSON: {e}")
                    post_data['gemini_raw_response'] = response_text
                    post_data['gemini_parse_error'] = str(e)
                    
            except Exception as e:
                print(f"      ❌ Vision analysis failed: {e}")
                post_data['vision_error'] = str(e)
            
            return post_data
            
        except Exception as e:
            print(f"    ⚠️ Error extracting post data: {e}")
            return None
    
    def analyze_single_post(self, post, idx, total):
        """Analyze a single post (for parallel execution)"""
        try:
            print(f"  [{idx}/{total}] Analyzing post from @{post['username']}...")
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            post_prompt = f"""Deeply analyze this Instagram post:

Username: @{post['username']}
Caption: {post['caption']}
Hashtags: {', '.join(post['hashtags'])}
Mentions: {', '.join(post['mentions'])}
Likes: {post['likes']}
Comments: {post['comments_count']}
Top Comments: {json.dumps(post['top_comments'])}
Media Type: {post['media_type']}
Location: {post['location']}

Provide detailed analysis:
1. Content Analysis: What is this post about? What value does it provide?
2. Hook & Engagement: How does it capture attention? Why might people engage?
3. Target Audience: Who is this for? What problem does it solve?
4. Hashtag Strategy: Are hashtags relevant and effective?
5. Engagement Rate: Given the likes/comments, how well is it performing?
6. Key Takeaway: What makes this post work (or not work)?

Be specific and actionable."""

            response = model.generate_content(post_prompt)
            return {
                'post_url': post['url'],
                'username': post['username'],
                'caption_preview': post['caption'][:100],
                'analysis': response.text
            }
            
        except Exception as e:
            print(f"      ⚠️ Error analyzing post: {e}")
            return {
                'post_url': post['url'],
                'username': post['username'],
                'analysis': f"Analysis failed: {str(e)}"
            }
    
    def analyze_posts_with_gemini(self, posts, max_workers=5):
        """Analyze posts using Gemini AI with parallel processing"""
        print(f"\n🤖 Analyzing {len(posts)} posts with Gemini (parallel mode with {max_workers} workers)...")
        
        try:
            # Step 1: Analyze each post individually in parallel
            individual_analyses = []
            print("\n📝 Performing individual post analysis in parallel...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_post = {
                    executor.submit(self.analyze_single_post, post, idx, len(posts)): post 
                    for idx, post in enumerate(posts, 1)
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_post):
                    try:
                        result = future.result()
                        individual_analyses.append(result)
                        print(f"      ✓ Completed {len(individual_analyses)}/{len(posts)}")
                    except Exception as e:
                        print(f"      ❌ Task failed: {e}")
            
            print(f"\n✅ Individual analysis complete: {len(individual_analyses)}/{len(posts)} posts analyzed")
            
            # Step 2: Aggregate analysis across all posts
            print("\n📊 Performing aggregate analysis...")
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            aggregate_prompt = f"""Based on these {len(posts)} Instagram posts from multiple accounts in the protein cookies/low-carb niche, provide comprehensive insights:

Posts Summary:
{json.dumps([{
    'username': p['username'],
    'caption': p['caption'],
    'hashtags': p['hashtags'],
    'likes': p['likes'],
    'comments': p['comments_count'],
    'media_type': p['media_type'],
    'top_comments': p['top_comments']
} for p in posts], indent=2)}

Provide analysis:

1. **Content Themes & Patterns**
   - What are the dominant themes?
   - What types of content appear most frequently?
   - Are there any gaps or opportunities?

2. **Engagement Analysis**
   - Which posts got the highest engagement and why?
   - What content formats work best (video/image/carousel)?
   - What caption styles drive engagement?

3. **Hashtag Strategy**
   - Most effective hashtags used
   - Hashtag volume and relevance
   - Recommendations for hashtag strategy

4. **Audience Insights**
   - Who is engaging with this content?
   - What problems/needs are being addressed?
   - What questions appear in comments?

5. **Competitive Insights**
   - How do different accounts compare?
   - Who has the strongest strategy?
   - What differentiates top performers?

6. **Actionable Recommendations**
   - 5 specific content ideas that would perform well
   - Optimal posting strategy (format, caption style, hashtags)
   - How to stand out in this niche

Be specific, data-driven, and actionable."""

            aggregate_response = model.generate_content(aggregate_prompt)
            aggregate_analysis = aggregate_response.text
            
            # Combine analyses
            full_analysis = {
                'aggregate_insights': aggregate_analysis,
                'individual_post_analyses': individual_analyses,
                'total_posts_analyzed': len(posts),
                'accounts_analyzed': list(set([p['username'] for p in posts]))
            }
            
            print("✓ Deep analysis complete")
            return full_analysis
            
        except Exception as e:
            print(f"❌ Error analyzing posts: {e}")
            return {
                'aggregate_insights': f"Analysis failed: {str(e)}",
                'individual_post_analyses': [],
                'error': str(e)
            }
    
    def save_to_csv(self, posts, analysis, accounts):
        """Save scraped posts to CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = os.path.join(self.save_dir, f'instagram_accounts_{timestamp}.csv')
        
        # Write posts CSV with all fields
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            if posts:
                fieldnames = ['username', 'url', 'caption', 'hashtags', 'mentions', 
                            'likes', 'comments_count', 'top_comments', 'media_type', 
                            'timestamp', 'location', 'scraped_at']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                # Convert lists to strings for CSV
                for post in posts:
                    post_copy = post.copy()
                    post_copy['hashtags'] = ', '.join(post['hashtags'])
                    post_copy['mentions'] = ', '.join(post['mentions'])
                    post_copy['top_comments'] = ' | '.join(post['top_comments'])
                    writer.writerow(post_copy)
        
        print(f"💾 Saved {len(posts)} posts to {csv_filename}")
        
        # Save analysis as separate file
        analysis_filename = os.path.join(self.save_dir, f'instagram_accounts_analysis_{timestamp}.json')
        analysis_data = {
            'timestamp': timestamp,
            'account_id': self.account_id,
            'scraped_accounts': accounts,
            'total_posts': len(posts),
            'analysis': analysis,
            'posts': posts
        }
        
        with open(analysis_filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved analysis to {analysis_filename}")
        
        return csv_filename, analysis_filename
    
    def scrape_accounts(self, usernames, num_posts_per_account=8):
        """Main scraping function for multiple accounts"""
        print(f"\n🚀 Starting Instagram Account Scraper")
        print(f"📋 Accounts to scrape: {', '.join(usernames)}")
        print(f"📊 Posts per account: {num_posts_per_account}")
        
        # Check for previous progress
        if self.progress_data['total_posts'] > 0:
            print(f"\n🔄 RESUME MODE")
            print(f"   Already scraped: {len(self.progress_data['completed_accounts'])} accounts")
            print(f"   Already scraped: {self.progress_data['total_posts']} posts")
            
            resume = input("   Continue from where you left off? (y/n): ").lower().strip()
            if resume != 'y':
                print("   Starting fresh...")
                self.clear_progress()
                self.progress_data = self.load_progress()
            else:
                print("   Resuming previous session...")
        
        # Start with any previously scraped posts
        all_posts = self.progress_data.get('all_posts', [])
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            
            # Load session if exists
            session_data = self.load_session()
            if session_data and 'cookies' in session_data:
                context.add_cookies(session_data['cookies'])
                print("✓ Loaded existing Instagram session")
            else:
                print("⚠️ No session found - you may need to login manually")
            
            page = context.new_page()
            
            # Navigate to Instagram
            page.goto('https://www.instagram.com/', wait_until='networkidle')
            time.sleep(3)
            
            # Handle any sign-up modals that might appear on the main page
            print("🔍 Checking for sign-up modals on main page...")
            modal_closed = self.handle_signup_modal(page)
            
            # Take screenshot after handling modals on main page
            if modal_closed:
                self.take_screenshot_after_modal(page, "main_page", "after_modal_close")
            else:
                self.take_screenshot_after_modal(page, "main_page", "no_modal_detected")
            
            # Check if logged in
            if 'login' in page.url.lower():
                print("\n⚠️ Not logged in! Please login manually in the browser window.")
                print("Press Enter after logging in...")
                input()
                
                # Handle modals again after login
                print("🔍 Checking for modals after login...")
                modal_closed = self.handle_signup_modal(page)
                if modal_closed:
                    self.take_screenshot_after_modal(page, "after_login", "after_modal_close")
                
                # Save session after login
                cookies = context.cookies()
                session_data = {'cookies': cookies}
                with open(self.session_file, 'w') as f:
                    json.dump(session_data, f)
                print("✓ Session saved")
            
            # Scrape each account
            for username in usernames:
                # Skip if already completed
                if username in self.progress_data['completed_accounts']:
                    print(f"\n⏭️ Skipping @{username} (already completed)")
                    continue
                
                print(f"\n📍 Starting account: @{username}")
                posts = self.scrape_profile_posts(page, username, num_posts_per_account)
                all_posts.extend(posts)
                
                # Mark account as completed
                self.save_progress(account=username)
                print(f"✅ Completed @{username} ({len(posts)} posts)")
                
                time.sleep(3)  # Rate limiting between accounts
            
            browser.close()
        
        # Analyze posts
        if all_posts:
            analysis = self.analyze_posts_with_gemini(all_posts)
            
            # Save to CSV
            csv_file, analysis_file = self.save_to_csv(all_posts, analysis, usernames)
            
            print(f"\n✅ Scraping complete!")
            print(f"📊 Total posts scraped: {len(all_posts)}")
            print(f"💾 CSV file: {csv_file}")
            print(f"💾 Analysis file: {analysis_file}")
            
            # Clear progress file after successful completion
            self.clear_progress()
            print("🗑️ Progress cleared (scraping complete)")
            
            return csv_file, analysis_file
        else:
            print("\n❌ No posts scraped")
            return None, None


def main():
    parser = argparse.ArgumentParser(description='Scrape Instagram accounts')
    parser.add_argument('--account', type=str, default='generic',
                      help='Account ID for organizing scraped data')
    parser.add_argument('--posts', type=int, default=8,
                      help='Number of posts to scrape per account')
    
    args = parser.parse_args()
    
    # Default accounts for protein cookies
    default_accounts = [
        'jking2386',
        'lowcarb.india',
        'mickphillips66',
        'jesscutsthecarbs',
        'anasfitmeals',
        'lillianreyactormodel',
        'chunkyfitcookie',
        'mcdprotein',
        'proteincookiebutter'
    ]
    
    print(f"📱 Instagram Account Scraper")
    print(f"🎯 Account: {args.account}")
    print(f"👥 Scraping {len(default_accounts)} accounts")
    
    scraper = InstagramAccountScraper(account_id=args.account)
    scraper.scrape_accounts(default_accounts, num_posts_per_account=args.posts)


if __name__ == '__main__':
    main()

