"""
YouTube Account Scraper for Shorts
Scrapes YouTube Shorts from specific channels and saves to CSV with AI analysis
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

class YouTubeAccountScraper:
    def __init__(self, account_id='generic'):
        """Initialize the scraper for a specific account"""
        self.account_id = account_id
        self.save_dir = f'data/accounts/{account_id}' if account_id != 'generic' else '.'
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Progress tracking
        self.progress_file = os.path.join(self.save_dir, 'youtube_scraping_progress.json')
        self.progress_data = self.load_progress()
        self.progress_lock = threading.Lock()  # Thread-safe progress saving
        
        print(f"🎯 Scraping YouTube Shorts for account: {account_id}")
        print(f"💾 Save directory: {self.save_dir}")
    
    def load_progress(self):
        """Load progress from previous run if exists"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    print(f"📂 Found previous progress: {len(progress.get('completed_channels', []))} channels, {progress.get('total_videos', 0)} videos")
                    return progress
            except Exception as e:
                print(f"⚠️ Could not load progress: {e}")
        return {
            'completed_channels': [],
            'completed_videos': [],
            'total_videos': 0,
            'last_channel': None,
            'all_videos': []
        }
    
    def save_progress(self, channel=None, video=None):
        """Save incremental progress (thread-safe)"""
        with self.progress_lock:
            try:
                if channel:
                    if channel not in self.progress_data['completed_channels']:
                        self.progress_data['completed_channels'].append(channel)
                    self.progress_data['last_channel'] = channel
                
                if video:
                    video_id = video['url'].split('/')[-1]
                    if video_id not in self.progress_data['completed_videos']:
                        self.progress_data['completed_videos'].append(video_id)
                        self.progress_data['all_videos'].append(video)
                        self.progress_data['total_videos'] = len(self.progress_data['all_videos'])
                
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(self.progress_data, f, indent=2, ensure_ascii=False)
                
            except Exception as e:
                print(f"⚠️ Could not save progress: {e}")
    
    def clear_progress(self):
        """Clear progress file to start fresh"""
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)
            print("🗑️ Progress file cleared")
    
    def scrape_channel_shorts(self, page, channel_url, num_shorts=8):
        """Scrape shorts from a specific YouTube channel - just extract URLs!"""
        channel_name = channel_url.split('@')[1].split('/')[0]
        print(f"\n📺 Scraping @{channel_name}...")
        
        try:
            # Navigate to channel shorts page
            page.goto(channel_url, wait_until='networkidle', timeout=30000)
            time.sleep(5)  # Give more time to load
            
            # Scroll to load more shorts
            print(f"   📜 Loading shorts...")
            for i in range(5):  # Scroll more times
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(2)
            
            # Take screenshot for debugging
            os.makedirs('screenshots', exist_ok=True)
            screenshot_path = f'screenshots/youtube_channel_{channel_name}.png'
            page.screenshot(path=screenshot_path)
            print(f"   📸 Screenshot saved: {screenshot_path}")
            
            # Try multiple selectors
            short_links = []
            selectors = [
                'a#thumbnail[href*="/shorts/"]',
                'a[href*="/shorts/"]',
                'ytd-rich-item-renderer a[href*="/shorts/"]',
                'ytd-grid-video-renderer a[href*="/shorts/"]'
            ]
            
            for selector in selectors:
                links = page.query_selector_all(selector)
                if links:
                    print(f"   ✓ Found {len(links)} shorts using selector: {selector}")
                    short_links = links
                    break
            
            if not short_links:
                print(f"   ⚠️ No shorts found with any selector!")
                print(f"   💡 Check screenshot at: {screenshot_path}")
                
                # Debug: print all links with "shorts" in them
                all_links = page.query_selector_all('a')
                shorts_links_debug = [link.get_attribute('href') for link in all_links if link.get_attribute('href') and '/shorts/' in link.get_attribute('href')]
                print(f"   🔍 Debug: Found {len(shorts_links_debug)} links with '/shorts/' in href")
                if shorts_links_debug:
                    print(f"   🔍 Sample links: {shorts_links_debug[:3]}")
                
                return []
            
            print(f"   ✓ Total shorts found: {len(short_links)}")
            
            # Limit to requested number
            short_links = short_links[:num_shorts]
            
            shorts = []
            for idx, link in enumerate(short_links, 1):
                try:
                    short_url = link.get_attribute('href')
                    if not short_url.startswith('http'):
                        short_url = f"https://www.youtube.com{short_url}"
                    
                    print(f"  [{idx}/{len(short_links)}] Analyzing: {short_url}")
                    
                    # Just extract the URL and analyze it directly with Gemini!
                    short_data = self.analyze_short_url(channel_name, short_url)
                    if short_data:
                        shorts.append(short_data)
                        # Save progress after each short
                        self.save_progress(video=short_data)
                        print(f"      💾 Progress saved ({len(self.progress_data['all_videos'])} total videos)")
                    
                    time.sleep(1)  # Small delay between analyses
                    
                except Exception as e:
                    print(f"    ⚠️ Error analyzing short: {e}")
                    continue
            
            print(f"✓ Analyzed {len(shorts)} shorts from @{channel_name}")
            
        except Exception as e:
            print(f"❌ Error scraping channel {channel_name}: {e}")
        
        return shorts
    
    def analyze_short_url(self, channel_name, video_url):
        """Analyze a YouTube Short URL directly with Gemini - no page opening needed!"""
        try:
            print(f"      🤖 Analyzing with Gemini API...")
            
            short_data = {
                'channel': channel_name,
                'url': video_url,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Use Gemini 2.0 to analyze the YouTube URL directly!
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            video_prompt = """
Watch this YouTube Short completely and provide a comprehensive analysis.

# EXTRACT & ANALYZE:

1. **Basic Info**
   - Title
   - Description
   - Hashtags used
   - Video duration

2. **Content Breakdown**
   - What happens in the video? (scene by scene)
   - Main message or value proposition
   - Hook in first 3 seconds

3. **Visual Elements**
   - Text overlays (exact text, timing, position)
   - Camera angles and shots
   - Lighting style
   - Color grading/filters
   - Composition

4. **Audio Analysis**
   - Background music style
   - Voiceover (if any)
   - Sound effects
   - Overall audio mood

5. **Editing Techniques**
   - Cuts and transitions
   - Speed effects (slow-mo/fast forward)
   - Zoom or pan effects
   - Text animations

6. **Engagement Strategy**
   - What emotion does it trigger?
   - Why would someone watch till the end?
   - What makes it shareable?
   - Call-to-action

7. **Target Audience**
   - Who is this for?
   - What problem does it solve?
   - What niche does it serve?

8. **Recreation Guide**
   - Equipment needed
   - Setup requirements
   - Shot list
   - Editing tips
   - Key elements to replicate

Return as JSON:
{
  "title": "...",
  "description": "...",
  "hashtags": ["#tag1", "#tag2"],
  "duration": "...",
  "content_breakdown": "...",
  "hook": "...",
  "visual_elements": {
    "text_overlays": [...],
    "camera_style": "...",
    "lighting": "...",
    "colors": [...]
  },
  "audio": {
    "music": "...",
    "voiceover": "...",
    "mood": "..."
  },
  "editing": {
    "techniques": [...],
    "pacing": "..."
  },
  "engagement": {
    "emotion": "...",
    "hook_strength": "...",
    "shareability": "..."
  },
  "audience": {
    "target": "...",
    "problem_solved": "...",
    "niche": "..."
  },
  "recreation": {
    "equipment": "...",
    "setup": "...",
    "key_elements": [...]
  }
}
"""
            
            # Pass the YouTube URL directly to Gemini!
            response = model.generate_content([video_prompt, video_url])
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
            
            # Parse the JSON response
            try:
                analysis = json.loads(response_text)
                
                # Add all fields to short_data
                short_data['title'] = analysis.get('title', '')
                short_data['description'] = analysis.get('description', '')
                short_data['hashtags'] = analysis.get('hashtags', [])
                short_data['duration'] = analysis.get('duration', '')
                short_data['content_breakdown'] = analysis.get('content_breakdown', '')
                short_data['hook'] = analysis.get('hook', '')
                short_data['visual_elements'] = analysis.get('visual_elements', {})
                short_data['audio_analysis'] = analysis.get('audio', {})
                short_data['editing_techniques'] = analysis.get('editing', {})
                short_data['engagement_strategy'] = analysis.get('engagement', {})
                short_data['target_audience'] = analysis.get('audience', {})
                short_data['recreation_guide'] = analysis.get('recreation', {})
                short_data['gemini_raw_response'] = response_text
                
                print(f"      ✅ Analysis complete: {short_data['title'][:50]}...")
                
            except json.JSONDecodeError as e:
                print(f"      ⚠️ Could not parse JSON: {e}")
                short_data['gemini_raw_response'] = response_text
                short_data['parse_error'] = str(e)
            
            return short_data
            
        except Exception as e:
            print(f"      ❌ Analysis failed: {e}")
            return {
                'channel': channel_name,
                'url': video_url,
                'error': str(e),
                'scraped_at': datetime.now().isoformat()
            }
    
    def extract_short_data(self, page, channel_name, video_url):
        """Extract comprehensive data from a single YouTube Short with Gemini URL analysis"""
        try:
            short_data = {
                'channel': channel_name,
                'url': video_url,
                'title': '',
                'description': '',
                'hashtags': [],
                'views': 0,
                'likes': 0,
                'comments_count': 0,
                'top_comments': [],
                'duration': '',
                'scraped_at': datetime.now().isoformat()
            }
            
            # Wait for content to load
            time.sleep(2)
            
            # Extract title
            try:
                title_elem = page.query_selector('h1.ytd-watch-metadata yt-formatted-string')
                if title_elem:
                    short_data['title'] = title_elem.inner_text().strip()
            except:
                pass
            
            # Extract description
            try:
                desc_elem = page.query_selector('ytd-text-inline-expander#description-inline-expander')
                if desc_elem:
                    short_data['description'] = desc_elem.inner_text().strip()
                    
                    # Extract hashtags from description
                    import re
                    hashtags = re.findall(r'#(\w+)', short_data['description'])
                    short_data['hashtags'] = hashtags
            except:
                pass
            
            # Extract views
            try:
                view_selectors = [
                    'span.view-count',
                    'ytd-video-view-count-renderer span'
                ]
                for selector in view_selectors:
                    view_elem = page.query_selector(selector)
                    if view_elem:
                        view_text = view_elem.inner_text()
                        # Parse views (handle K, M, B suffixes)
                        view_str = view_text.split()[0].replace(',', '')
                        if 'K' in view_str:
                            short_data['views'] = int(float(view_str.replace('K', '')) * 1000)
                        elif 'M' in view_str:
                            short_data['views'] = int(float(view_str.replace('M', '')) * 1000000)
                        elif 'B' in view_str:
                            short_data['views'] = int(float(view_str.replace('B', '')) * 1000000000)
                        else:
                            short_data['views'] = int(view_str) if view_str.isdigit() else 0
                        break
            except:
                pass
            
            # Extract likes
            try:
                like_button = page.query_selector('like-button-view-model button[aria-label*="like"]')
                if like_button:
                    like_text = like_button.get_attribute('aria-label')
                    import re
                    like_match = re.search(r'(\d+[KMB]?)', like_text)
                    if like_match:
                        like_str = like_match.group(1)
                        if 'K' in like_str:
                            short_data['likes'] = int(float(like_str.replace('K', '')) * 1000)
                        elif 'M' in like_str:
                            short_data['likes'] = int(float(like_str.replace('M', '')) * 1000000)
                        else:
                            short_data['likes'] = int(like_str) if like_str.isdigit() else 0
            except:
                pass
            
            # Extract top comments
            try:
                comment_elements = page.query_selector_all('ytd-comment-thread-renderer #content-text')
                comments_list = []
                for elem in comment_elements[:3]:  # Top 3 comments
                    comment_text = elem.inner_text().strip()
                    if len(comment_text) > 10:
                        comments_list.append(comment_text)
                short_data['top_comments'] = comments_list
                short_data['comments_count'] = len(comment_elements)
            except:
                pass
            
            print(f"      ✓ Extracted: {len(short_data['title'])} chars title, {short_data['views']} views, {short_data['likes']} likes")
            
            # NOW DO COMPREHENSIVE VIDEO ANALYSIS USING DIRECT YOUTUBE URL
            print(f"      🤖 Analyzing video with Gemini API (direct URL)...")
            try:
                # Gemini 2.0 can analyze YouTube URLs directly!
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                
                video_prompt = """
Watch this YouTube Short completely and analyze it in EXTREME DETAIL to help recreate viral content.

# COMPREHENSIVE VIDEO ANALYSIS

## 1. CONTENT BREAKDOWN
- What happens in the video? (describe scene by scene)
- What is the main message or value proposition?
- How long is it and what's the pacing?

## 2. HOOK ANALYSIS (First 3 Seconds)
- What's the opening shot/frame?
- What text or visual grabs attention immediately?
- What makes someone stop scrolling?

## 3. TEXT & CAPTIONS
- ALL text overlays (exact text, timing, position)
- Subtitle/caption style
- Text animation effects
- Font styles and colors

## 4. VISUAL STYLE
- Camera angles used
- Lighting setup (natural/studio/ring light)
- Color grading/filters
- Shot composition
- B-roll or cutaways

## 5. AUDIO ANALYSIS
- Background music style
- Voiceover tone and style
- Sound effects used
- Audio pacing

## 6. EDITING TECHNIQUES
- Cuts and transitions
- Speed ramping (slow-mo/fast forward)
- Zoom effects
- Split screen or overlays

## 7. ENGAGEMENT FACTORS
- What triggers emotion (humor, curiosity, inspiration)?
- What's the "aha" moment or payoff?
- Why would someone like/comment/share?

## 8. TARGET AUDIENCE
- Who is this for?
- What problem does it solve?
- What interest/niche does it serve?

## 9. RECREATION GUIDE
- Equipment list (camera, lighting, mic)
- Location/setup requirements
- Shot list with timings
- Editing software recommendations
- Text overlay specifications
- Music/audio recommendations

Return ONLY valid JSON with all details."""
                
                # Pass the YouTube URL directly to Gemini!
                response = model.generate_content([video_prompt, video_url])
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
                
                # Parse and add vision data
                try:
                    vision_data = json.loads(response_text)
                    short_data['text_in_video'] = vision_data.get('text_in_video', [])
                    short_data['visual_analysis'] = vision_data.get('visual_analysis', {})
                    short_data['strategy_analysis'] = vision_data.get('strategy', {})
                    short_data['recreation_guide'] = vision_data.get('recreation_guide', {})
                    short_data['gemini_raw_response'] = response_text
                    
                    # Update title if vision found better one
                    if vision_data.get('title') and len(vision_data['title']) > len(short_data['title']):
                        short_data['title'] = vision_data['title']
                    
                    print(f"      ✅ Vision analysis complete")
                    if short_data.get('text_in_video'):
                        print(f"         📖 Found {len(short_data['text_in_video'])} text elements")
                    if short_data.get('visual_analysis'):
                        print(f"         🎨 Visual style analyzed")
                    
                except json.JSONDecodeError as e:
                    print(f"      ⚠️ Could not parse vision JSON: {e}")
                    short_data['gemini_raw_response'] = response_text
                    
            except Exception as e:
                print(f"      ❌ Vision analysis failed: {e}")
                short_data['vision_error'] = str(e)
            
            return short_data
            
        except Exception as e:
            print(f"    ⚠️ Error extracting short data: {e}")
            return None
    
    def analyze_single_video(self, video, idx, total):
        """Analyze a single video (for parallel execution)"""
        try:
            print(f"  [{idx}/{total}] Analyzing video from @{video['channel']}...")
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            video_prompt = f"""Deeply analyze this YouTube Short:

Channel: @{video['channel']}
Title: {video['title']}
Description: {video['description']}
Hashtags: {', '.join(video['hashtags'])}
Views: {video['views']}
Likes: {video['likes']}
Comments: {video['comments_count']}
Top Comments: {json.dumps(video['top_comments'])}

Provide detailed analysis:
1. Content Analysis: What is this short about? What value does it provide?
2. Hook & Engagement: How does it capture attention in first 3 seconds?
3. Target Audience: Who is this for? What problem does it solve?
4. Hashtag Strategy: Are hashtags relevant and effective?
5. Engagement Rate: How well is it performing?
6. Key Takeaway: What makes this short work?

Be specific and actionable."""

            response = model.generate_content(video_prompt)
            return {
                'video_url': video['url'],
                'channel': video['channel'],
                'title_preview': video['title'][:100],
                'analysis': response.text
            }
            
        except Exception as e:
            print(f"      ⚠️ Error analyzing video: {e}")
            return {
                'video_url': video['url'],
                'channel': video['channel'],
                'analysis': f"Analysis failed: {str(e)}"
            }
    
    def analyze_videos_with_gemini(self, videos, max_workers=5):
        """Analyze videos using Gemini AI with parallel processing"""
        print(f"\n🤖 Analyzing {len(videos)} videos with Gemini (parallel mode with {max_workers} workers)...")
        
        try:
            # Step 1: Analyze each video individually in parallel
            individual_analyses = []
            print("\n📝 Performing individual video analysis in parallel...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_video = {
                    executor.submit(self.analyze_single_video, video, idx, len(videos)): video 
                    for idx, video in enumerate(videos, 1)
                }
                
                for future in as_completed(future_to_video):
                    try:
                        result = future.result()
                        individual_analyses.append(result)
                        print(f"      ✓ Completed {len(individual_analyses)}/{len(videos)}")
                    except Exception as e:
                        print(f"      ❌ Task failed: {e}")
            
            print(f"\n✅ Individual analysis complete: {len(individual_analyses)}/{len(videos)} videos analyzed")
            
            # Step 2: Aggregate analysis
            print("\n📊 Performing aggregate analysis...")
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            aggregate_prompt = f"""Based on these {len(videos)} YouTube Shorts from protein cookie/healthy snack channels, provide comprehensive insights:

Videos Summary:
{json.dumps([{
    'channel': v['channel'],
    'title': v['title'],
    'hashtags': v['hashtags'],
    'views': v['views'],
    'likes': v['likes'],
    'comments': v['comments_count']
} for v in videos], indent=2)}

Provide analysis:

1. **Content Themes & Patterns**
2. **Engagement Analysis** 
3. **Hashtag Strategy**
4. **Audience Insights**
5. **Competitive Insights**
6. **Actionable Recommendations**

Be specific, data-driven, and actionable."""

            aggregate_response = model.generate_content(aggregate_prompt)
            
            full_analysis = {
                'aggregate_insights': aggregate_response.text,
                'individual_video_analyses': individual_analyses,
                'total_videos_analyzed': len(videos),
                'channels_analyzed': list(set([v['channel'] for v in videos]))
            }
            
            print("✓ Deep analysis complete")
            return full_analysis
            
        except Exception as e:
            print(f"❌ Error analyzing videos: {e}")
            return {
                'aggregate_insights': f"Analysis failed: {str(e)}",
                'individual_video_analyses': [],
                'error': str(e)
            }
    
    def save_to_csv(self, videos, analysis, channels):
        """Save scraped videos to CSV with comprehensive fields"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = os.path.join(self.save_dir, f'youtube_shorts_{timestamp}.csv')
        
        # Write videos CSV with all fields
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            if videos:
                fieldnames = [
                    'channel', 'url', 'title', 'description', 'hashtags', 'duration',
                    'content_breakdown', 'hook', 'visual_elements', 'audio_analysis',
                    'editing_techniques', 'engagement_strategy', 'target_audience',
                    'recreation_guide', 'scraped_at'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                
                for video in videos:
                    video_copy = video.copy()
                    
                    # Format lists as strings
                    if isinstance(video.get('hashtags'), list):
                        video_copy['hashtags'] = ', '.join(video['hashtags'])
                    
                    # Convert dict/list fields to JSON strings for CSV
                    for field in ['visual_elements', 'audio_analysis', 'editing_techniques', 
                                 'engagement_strategy', 'target_audience', 'recreation_guide']:
                        if field in video and isinstance(video[field], (dict, list)):
                            video_copy[field] = json.dumps(video[field], ensure_ascii=False)
                    
                    writer.writerow(video_copy)
        
        print(f"💾 Saved {len(videos)} videos to {csv_filename}")
        
        # Save analysis
        analysis_filename = os.path.join(self.save_dir, f'youtube_shorts_analysis_{timestamp}.json')
        analysis_data = {
            'timestamp': timestamp,
            'account_id': self.account_id,
            'scraped_channels': channels,
            'total_videos': len(videos),
            'analysis': analysis,
            'videos': videos
        }
        
        with open(analysis_filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved analysis to {analysis_filename}")
        
        return csv_filename, analysis_filename
    
    def scrape_channels(self, channel_urls, num_shorts_per_channel=8):
        """Main scraping function for multiple channels"""
        print(f"\n🚀 Starting YouTube Shorts Scraper")
        print(f"📋 Channels to scrape: {len(channel_urls)}")
        print(f"📊 Shorts per channel: {num_shorts_per_channel}")
        
        # Check for previous progress
        if self.progress_data['total_videos'] > 0:
            print(f"\n🔄 RESUME MODE")
            print(f"   Already scraped: {len(self.progress_data['completed_channels'])} channels")
            print(f"   Already scraped: {self.progress_data['total_videos']} videos")
            
            resume = input("   Continue from where you left off? (y/n): ").lower().strip()
            if resume != 'y':
                print("   Starting fresh...")
                self.clear_progress()
                self.progress_data = self.load_progress()
            else:
                print("   Resuming previous session...")
        
        all_videos = self.progress_data.get('all_videos', [])
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            
            # Scrape each channel
            for channel_url in channel_urls:
                channel_name = channel_url.split('@')[1].split('/')[0]
                
                # Skip if already completed
                if channel_name in self.progress_data['completed_channels']:
                    print(f"\n⏭️ Skipping @{channel_name} (already completed)")
                    continue
                
                print(f"\n📍 Starting channel: @{channel_name}")
                shorts = self.scrape_channel_shorts(page, channel_url, num_shorts_per_channel)
                all_videos.extend(shorts)
                
                # Mark channel as completed
                self.save_progress(channel=channel_name)
                print(f"✅ Completed @{channel_name} ({len(shorts)} shorts)")
                
                time.sleep(3)  # Rate limiting
            
            browser.close()
        
        # Analyze videos
        if all_videos:
            analysis = self.analyze_videos_with_gemini(all_videos)
            
            # Save to CSV
            csv_file, analysis_file = self.save_to_csv(all_videos, analysis, 
                                                       [url.split('@')[1].split('/')[0] for url in channel_urls])
            
            print(f"\n✅ Scraping complete!")
            print(f"📊 Total videos scraped: {len(all_videos)}")
            print(f"💾 CSV file: {csv_file}")
            print(f"💾 Analysis file: {analysis_file}")
            
            # Clear progress
            self.clear_progress()
            print("🗑️ Progress cleared (scraping complete)")
            
            return csv_file, analysis_file
        else:
            print("\n❌ No videos scraped")
            return None, None


def main():
    parser = argparse.ArgumentParser(description='Scrape YouTube Shorts from channels')
    parser.add_argument('--account', type=str, default='generic',
                      help='Account ID for organizing scraped data')
    parser.add_argument('--shorts', type=int, default=8,
                      help='Number of shorts to scrape per channel')
    
    args = parser.parse_args()
    
    # Default channels for protein cookies/healthy snacks
    default_channels = [
        'https://www.youtube.com/@healthyveganeating/shorts',
        'https://www.youtube.com/@MissFitAndNerdy/shorts',
        'https://www.youtube.com/@NutritionFactsOrg/shorts',
        'https://www.youtube.com/@theplantslant2431/shorts',
        'https://www.youtube.com/@Iricksnackz/shorts',
        'https://www.youtube.com/@myproteinpantry/shorts',
        'https://www.youtube.com/@ShayClick/shorts'
    ]
    
    print(f"📱 YouTube Shorts Scraper")
    print(f"🎯 Account: {args.account}")
    print(f"👥 Scraping {len(default_channels)} channels")
    
    scraper = YouTubeAccountScraper(account_id=args.account)
    scraper.scrape_channels(default_channels, num_shorts_per_channel=args.shorts)


if __name__ == '__main__':
    main()

