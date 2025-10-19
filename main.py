"""
Instagram AI Doomscroller
Automated Instagram trend analysis using Browser Use + Gemini
"""

import asyncio
import time
from browser_use import Agent, ChatGoogle
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
import argparse

# Load environment variables
load_dotenv()

# Setup detailed logging
def setup_logging():
    """Setup comprehensive logging for Playwright conversion"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"instagram_scraper_{timestamp}.log"
    
    # Create logger
    logger = logging.getLogger("InstagramScraper")
    logger.setLevel(logging.DEBUG)
    
    # File handler - detailed logs
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - important messages only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"=== Logging initialized - Log file: {log_file} ===")
    return logger

# Initialize logger
logger = setup_logging()

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

class InstagramDoomscroller:
    """
    AI agent that automatically browses Instagram and analyzes trending content
    """
    
    def __init__(self, account_id=None):
        # Using gemini-2.0-flash-lite for better rate limits and availability
        self.llm = ChatGoogle(model='gemini-2.0-flash-lite')
        self.results = {}
        self.username = INSTAGRAM_USERNAME
        self.password = INSTAGRAM_PASSWORD
        self.logger = logging.getLogger("InstagramScraper")
        self.account_id = account_id
        
        # Setup save directory based on account
        if account_id:
            self.save_dir = Path(f"data/accounts/{account_id}")
            self.save_dir.mkdir(parents=True, exist_ok=True)
            (self.save_dir / "screenshots").mkdir(exist_ok=True)
            self.logger.info(f"Saving to account folder: {self.save_dir}")
        else:
            self.save_dir = Path(".")
            self.logger.info("Saving to root directory (generic account)")
        
        self.logger.info("=" * 80)
        self.logger.info("InstagramDoomscroller initialized")
        self.logger.info(f"Model: gemini-2.0-flash-lite")
        self.logger.info(f"Username: {self.username}")
        self.logger.info("=" * 80)
        
    async def login_to_instagram(self):
        """
        Automatically log in to Instagram using credentials from .env
        """
        if not self.username or not self.password:
            print("❌ Instagram credentials not found in .env file")
            print("Please add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to your .env file")
            return False
            
        # First, try to log in
        login_agent = Agent(
            task=f"""
            Go to instagram.com and log in with these credentials:
            Username: {self.username}
            Password: {self.password}
            
            Login steps:
            1. Click on the username/email field
            2. Type: {self.username}
            3. Click on the password field  
            4. Type: {self.password}
            5. Click the "Log In" button
            6. Wait for the page to load completely
            
            After login:
            7. If there's a "Not Now" button for saving login info, click it
            8. If there's a "Turn on Notifications" popup, click "Not Now"
            9. If there's a "Save Your Login Info" popup, click "Not Now"
            10. Navigate to instagram.com/explore
            11. Wait for the Explore page to load
            """,
            llm=self.llm,
        )
        
        print("🔐 Logging into Instagram...")
        result = await login_agent.run()
        
        # Check if 2FA is needed by looking for 2FA elements
        check_2fa_agent = Agent(
            task="""
            Check if there's a 2FA (Two-Factor Authentication) screen visible.
            Look for:
            - "Enter confirmation code" text
            - "Two-factor authentication" text
            - A code input field
            - "Confirm" or "Submit" button for 2FA
            
            If you see 2FA elements, respond with "2FA_REQUIRED"
            If you don't see 2FA elements and you're on the main feed, respond with "LOGIN_SUCCESS"
            """,
            llm=self.llm,
        )
        
        check_result = await check_2fa_agent.run()
        
        # Handle case where API call fails due to rate limiting
        if check_result and check_result.final_result() and "2FA_REQUIRED" in check_result.final_result():
            print("🔐 2FA detected! Please enter your 2FA code:")
            twofa_code = input("Enter 2FA code: ").strip()
            
            # Handle 2FA
            twofa_agent = Agent(
                task=f"""
                You are on Instagram's 2FA screen. Enter the 2FA code: {twofa_code}
                
                Steps:
                1. Click on the code input field
                2. Type: {twofa_code}
                3. Click "Confirm" or "Submit" button
                4. Wait for the page to load
                5. If there's a "Not Now" button for saving login info, click it
                6. If there's a "Turn on Notifications" popup, click "Not Now"
                7. Navigate to instagram.com/explore
                8. Wait for the Explore page to load
                """,
                llm=self.llm,
            )
            
            print("🔐 Entering 2FA code...")
            await twofa_agent.run()
        else:
            # If API call failed due to rate limiting, assume login was successful
            print("⚠️ API rate limited - assuming login was successful")
        
        print("✓ Login complete\n")
        return True
        
    async def scroll_and_explore(self):
        """
        Navigate to Explore tab and perform detailed analysis of individual posts
        """
        agent = Agent(
            task="""
            You are on Instagram's Explore page. Perform detailed analysis of the trending content:
            
            1. Scroll through the Explore feed slowly
            2. For each interesting post (especially videos/Reels), click on it to open in detail
            3. Analyze the post thoroughly:
               - Read the full caption
               - Check all hashtags used
               - Note engagement metrics (likes, comments, shares)
               - Analyze the content type and style
               - Look at the creator's profile info
            4. Go back to the Explore feed (click back arrow or swipe back)
            5. Continue to the next post and repeat
            6. Do this for at least 15-20 posts, focusing on the most engaging ones
            
            This detailed analysis will give us deep insights into what makes content viral.
            """,
            llm=self.llm,
        )
        
        print("🔍 Performing detailed post analysis on Explore page...")
        result = await agent.run()
        print("✓ Detailed post analysis complete\n")
        return result
    
    async def analyze_trending_posts(self):
        """
        Analyze posts to identify trending content
        """
        agent = Agent(
            task="""
            You are on Instagram's Explore tab. Perform a detailed analysis of the posts you've examined.
            
            Based on your detailed examination of individual posts, provide comprehensive analysis:
            
            For each post you analyzed in detail, extract:
            1. Content type: video, image, or carousel
            2. Full caption (not just first 50 characters)
            3. Exact engagement metrics (likes, comments, shares, saves)
            4. All hashtags used (complete list)
            5. Creator's follower count (if visible)
            6. Posting time/date (if visible)
            7. Content length (for videos: exact seconds)
            8. Visual style (filters, editing, colors)
            9. Audio/music used (for videos)
            10. Call-to-action in caption
            11. Main topic/theme
            12. Engagement rate (likes/followers ratio if possible)
            
            Then provide deep insights:
            - What content types get the most engagement?
            - Which hashtags are most effective?
            - What posting times work best?
            - What visual styles are trending?
            - What audio/music is popular?
            - What captions get the most engagement?
            - What patterns in successful creators?
            
            Format as detailed JSON with comprehensive data:
            {
                "detailed_posts": [
                    {
                        "rank": 1,
                        "type": "video",
                        "duration": "15 seconds",
                        "likes": "125K",
                        "comments": "1.2K",
                        "shares": "500",
                        "saves": "2.1K",
                        "creator_followers": "50K",
                        "posting_time": "7:30 PM",
                        "full_caption": "Complete caption text here...",
                        "hashtags": ["#ai", "#tech", "#coding", "#innovation"],
                        "visual_style": "bright colors, fast cuts",
                        "audio": "trending sound - original audio",
                        "cta": "Follow for more tech tips",
                        "topic": "AI technology",
                        "engagement_rate": "2.5%"
                    }
                ],
                "deep_insights": {
                    "content_performance": "15-30 second videos get 3x more engagement",
                    "hashtag_strategy": "Mix of niche and broad hashtags works best",
                    "posting_timing": "Evening posts (6-9 PM) perform 40% better",
                    "visual_trends": "Bright, high-contrast visuals trending",
                    "audio_trends": "Original audio outperforms trending sounds",
                    "caption_patterns": "Questions in captions increase comments by 60%",
                    "creator_insights": "Micro-influencers (10K-100K) have highest engagement rates"
                }
            }
            """,
            llm=self.llm,
        )
        
        print("📊 Performing comprehensive post analysis...")
        result = await agent.run()
        self.results['posts_analysis'] = result.final_result()
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.save_dir / f'instagram_trends_{timestamp}.json'
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'analysis': result.final_result()
            }, f, indent=2)
        
        print(f"✓ Analysis complete and saved\n")
        return result
    
    async def analyze_reels(self):
        """
        Deep dive into Reels/videos to understand what makes them viral
        """
        agent = Agent(
            task="""
            You are on Instagram's Explore tab. Perform a deep dive analysis of Reels/video content.
            
            Click on and analyze the top 5 most popular Reels in detail:
            
            For each Reel, click on it and analyze:
            1. Exact video length (precise seconds)
            2. Hook analysis (first 3 seconds frame-by-frame)
            3. Editing breakdown:
               - Cut frequency (cuts per second)
               - Transition types (hard cuts, dissolves, wipes)
               - Text overlay usage and placement
               - Effects used (slow motion, speed ramps, filters)
            4. Audio analysis:
               - Music type (trending sound, original, licensed)
               - Audio quality and mixing
               - Voice-over usage
               - Sound effects
            5. Visual style deep dive:
               - Color palette and grading
               - Lighting style
               - Camera angles and movements
               - Aspect ratio and framing
            6. Engagement metrics:
               - Likes, comments, shares, saves
               - View count (if visible)
               - Completion rate indicators
            7. Creator analysis:
               - Follower count
               - Posting frequency
               - Content niche
            8. Caption and hashtag strategy
            9. Call-to-action effectiveness
            
            Provide granular insights:
            - Optimal video length with data backing
            - Most effective hook patterns with examples
            - Trending editing techniques with specific details
            - Audio strategy recommendations
            - Visual style trends with color codes/styles
            - Creator size vs engagement correlation
            - Best practices for each content type
            
            Format as detailed analysis with specific recommendations.
            """,
            llm=self.llm,
        )
        
        print("🎥 Performing deep dive Reels analysis...")
        result = await agent.run()
        self.results['reels_analysis'] = result.final_result()
        print("✓ Deep dive Reels analysis complete\n")
        return result
    
    async def track_hashtags(self):
        """
        Find and analyze trending hashtags
        """
        agent = Agent(
            task="""
            You are on Instagram's Explore tab. Perform comprehensive hashtag analysis.
            
            Click on posts and analyze hashtag usage patterns:
            
            For each post you examine, analyze:
            1. All hashtags used (complete list)
            2. Hashtag placement in caption
            3. Hashtag mix (niche vs broad, branded vs generic)
            4. Post performance correlation with hashtag strategy
            5. Creator's hashtag consistency across posts
            
            Then analyze trending hashtags by:
            1. Clicking on individual hashtags to see:
               - Total post count
               - Recent post frequency
               - Top posts in that hashtag
               - Content variety in hashtag
            2. Categorizing hashtags by:
               - Industry/niche
               - Size (micro vs macro)
               - Growth trend (rising vs stable)
               - Content type suitability
            3. Identifying patterns:
               - Most effective hashtag combinations
               - Optimal number of hashtags per post
               - Best hashtag placement strategies
               - Emerging vs established hashtags
            
            Provide granular insights:
            - Top 15 trending hashtags with detailed metrics
            - Hashtag strategy recommendations by content type
            - Emerging hashtag trends to watch
            - Optimal hashtag mix formulas
            - Industry-specific hashtag insights
            - Best practices for hashtag research
            
            Format as comprehensive hashtag analysis with actionable strategies.
            """,
            llm=self.llm,
        )
        
        print("🏷️ Performing comprehensive hashtag analysis...")
        result = await agent.run()
        self.results['hashtags'] = result.final_result()
        print("✓ Comprehensive hashtag analysis complete\n")
        return result
    
    async def run_full_analysis(self):
        """
        Run complete Instagram trend analysis in a single browser session
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING FULL ANALYSIS")
        self.logger.info("=" * 80)
        
        print("""
╔══════════════════════════════════════════════════╗
║     Instagram AI Doomscroller                    ║
║     Powered by Browser Use + Gemini              ║
╚══════════════════════════════════════════════════╝
        """)
        
        # Single agent that handles everything in one session
        analysis_agent = Agent(
            task=f"""
            Complete Instagram analysis workflow in one session:
            
            STEP 1 - LOGIN:
            Go to instagram.com and log in with these credentials:
            Username: {self.username}
            Password: {self.password}
            
            Login steps:
            1. Wait 5 seconds for the page to fully load
            2. Look for the username/email input field (it might be an input box with placeholder "Phone number, username, or email")
            3. Click on the username field
            4. Type: {self.username}
            5. Look for the password input field (it might be an input box with placeholder "Password")
            6. Click on the password field
            7. Type: {self.password}
            8. Look for the "Log In" button and click it
            9. Wait 5 seconds for the page to load completely
            
            After login:
            10. If there's a "Not Now" button for saving login info, click it
            11. If there's a "Turn on Notifications" popup, click "Not Now"
            12. If there's a "Save Your Login Info" popup, click "Not Now"
            13. Navigate to instagram.com/explore
            14. Wait for the Explore page to load
            
            IMPORTANT: If login fails after 3 attempts, stop and report the issue.
            
            STEP 2 - CHECK FOR 2FA:
            If you see a 2FA screen with code input field, respond with "2FA_REQUIRED" and wait for user input.
            If you're successfully on the Explore page, continue to Step 3.
            
            STEP 3 - URL EXTRACTION WITH LIMITS:
            Extract post URLs from the Explore page with the following limits:
            - Maximum 50 scroll steps
            - Maximum 20 URLs collected
            - Stop when EITHER limit is reached
            
            EXTRACTION PROCESS:
            1. Initialize counters: scroll_count = 0, total_urls = 0
            2. Look at posts currently visible on the Explore page
            3. Extract post URLs using: extract(query: "a[href*='/p/']", extract_links: True)
            4. Add extracted URLs to your collection (avoid duplicates)
            5. Update total_urls counter
            
            REPEAT UNTIL LIMIT REACHED:
            6. If total_urls >= 20 OR scroll_count >= 50, STOP and go to PHASE 4
            7. Scroll down ONE page
            8. Increment scroll_count by 1
            9. Wait 2 seconds for posts to load
            10. Extract new post URLs using: extract(query: "a[href*='/p/']", extract_links: True)
            11. Add to collection (avoid duplicates)
            12. Update total_urls counter
            13. Go back to step 6
            
            IMPORTANT: Track your progress as you go:
            - After each scroll, report: "Scroll X/50, URLs collected: Y/20" (replace X and Y with actual numbers)
            - When you hit a limit, report which limit was reached
            
            SAVE URLS:
            14. Convert all relative URLs to full URLs by adding "https://www.instagram.com" prefix
            15. Save all collected URLs to a file named "post_urls.txt"
            16. Format as: https://www.instagram.com/p/[POST_ID]/
            17. Report final count: "Collected X URLs after Y scroll steps" (replace X and Y with actual numbers)
            
            PHASE 4 - ANALYZE EACH POST:
            Now analyze ALL the collected URLs (up to 20):
            
            For each URL in your collected list:
            A) NAVIGATE TO POST:
               - Navigate to the post URL
               - Wait 3-5 seconds for it to load
               - If it doesn't load, skip to next post
            
            B) ANALYZE POST CONTENT:
               - Read the FULL CAPTION (main post caption only, not comments)
               - Check ALL HASHTAGS used in the caption
               - Note engagement metrics (likes count, comments count, shares)
               - Analyze the content type and style (video, image, carousel)
               - Look at creator's profile info (username, follower count)
               - Note the post URL
               - EXTRACT ALL COMMENTS: Read all visible comments and their like counts
            
            C) RECORD DATA:
               - Save all extracted data for this post
               - Move to the next post URL
            
            PHASE 5 - COMPLETE ANALYSIS:
            After analyzing all collected posts (up to 20), provide comprehensive insights and save results.
            
            IMPORTANT: After each scroll, STOP and extract links. Don't keep scrolling endlessly.
            
            STEP 5 - EXTRACT AND ANALYZE DATA:
            As you analyze each post, immediately extract and record:
            
            A) POST LINKS COLLECTION:
            First, create a list of post URLs you found:
            - Post URL 1: [URL]
            - Post URL 2: [URL]
            - Post URL 3: [URL]
            - etc.
            
            B) INDIVIDUAL POST ANALYSIS:
            For each post you successfully analyze, extract:
            - Post URL
            - Post type (video, image, carousel)
            - Duration (for videos)
            - Likes count, comments count, shares count
            - Creator username and follower count
            - Posting time
            - Full caption text (main post caption only, not comments)
            - All hashtags used in the caption
            - Visual style description
            - Audio/music used
            - Call-to-action in caption
            - Main topic/theme
            - Engagement rate (likes/followers ratio)
            - EXTRACT: Individual comments and their like counts
            
            TEXT EXTRACTION FROM IMAGES (OCR):
            - Extract ALL text visible within the actual post image(s), including:
              * Text overlays on images/videos
              * Text written on signs, documents, screens, or objects
              * Text in memes, quotes, or graphics
              * Text on products, packaging, or labels
              * Text in infographics or charts
              * Any handwritten or printed text visible in the image
              * Text in video thumbnails or first frames
              * Text in carousel images (analyze each image separately)
              * Text in stickers, emojis with text, or annotations
              * Text in backgrounds, walls, or environmental elements
              * Text in clothing, accessories, or personal items
              * Text in food packaging, menus, or restaurant signs
              * Text in books, magazines, or reading materials
              * Text in computer screens, phones, or digital displays
              * Text in vehicles, buildings, or street signs
              * Any other text visible anywhere in the image
            
            For each piece of text found, note:
              - The exact text content
              - Where it appears in the image (top, bottom, center, etc.)
              - Font style if distinguishable (bold, italic, handwritten, etc.)
              - Text color if visible
              - Size relative to other elements (large, small, etc.)
              - Whether it's part of the main content or background
            
            C) PROGRESS TRACKING:
            Keep track of:
            - How many post links you collected
            - How many posts you successfully analyzed
            - Which posts failed to load
            - What types of content you're seeing
            - Any patterns you notice
            
            B) VIRAL REELS INSIGHTS:
            For video content, analyze:
            - Hook analysis (first 3 seconds)
            - Visual editing techniques
            - Audio and music trends
            - Caption strategies
            - Engagement patterns
            - Creator insights
            
            C) HASHTAG TRENDS:
            Track and analyze:
            - Most popular hashtags
            - Niche vs broad hashtag performance
            - Hashtag placement strategies
            - Emerging hashtag trends
            - Industry-specific insights
            
            STEP 5 - GENERATE INSIGHTS:
            Provide comprehensive insights on:
            - What content types get the most engagement
            - Which hashtags are most effective
            - What posting times work best
            - What visual styles are trending
            - What audio/music is popular
            - What captions get the most engagement
            - What patterns in successful creators
            
            STEP 6 - FINAL OUTPUT:
            At the end, provide a comprehensive summary including:
            
            1. POST LINKS COLLECTED:
            - List all the post URLs you found
            - Show how many links you collected total
            
            2. DETAILED POST ANALYSIS:
            - List each post you successfully analyzed with all extracted data
            - Include post URL, type, engagement metrics, captions, hashtags, etc.
            - Show what you found in each post
            
            3. PROGRESS SUMMARY:
            - How many post links you collected
            - How many posts you successfully analyzed
            - How many failed to load
            - What types of content you saw
            - Any patterns or trends noticed
            
            4. INSIGHTS AND RECOMMENDATIONS:
            - What content types get the most engagement
            - Which hashtags are most effective
            - What posting times work best
            - What visual styles are trending
            - What audio/music is popular
            - What captions get the most engagement
            - What patterns in successful creators
            
            Format everything as detailed JSON with comprehensive data and actionable insights.
            
            Complete all steps in this single session without disconnecting the browser.
            """,
            llm=self.llm,
        )
        
        print("🚀 Starting comprehensive Instagram analysis...")
        self.logger.info("Starting analysis agent execution")
        
        # Retry logic for rate limiting and login issues
        max_retries = 3
        retry_delay = 60  # 60 seconds between retries
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1}/{max_retries}")
                print(f"🔄 Attempt {attempt + 1}/{max_retries}")
                
                start_time = time.time()
                result = await analysis_agent.run()
                elapsed_time = time.time() - start_time
                
                self.logger.info(f"Agent execution completed in {elapsed_time:.2f} seconds")
                
                if result and result.final_result():
                    self.logger.info("Analysis completed successfully")
                    self.logger.debug(f"Result type: {type(result)}")
                    self.logger.debug(f"Result length: {len(str(result.final_result()))} characters")
                    
                    print("\n" + "="*60)
                    print("✅ ANALYSIS COMPLETE!")
                    print("="*60)
                    print("📊 Results:")
                    print(result.final_result())
                    
                    # Save results
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"instagram_trends_{timestamp}.json"
                    
                    self.logger.info(f"Saving results to {filename}")
                    
                    try:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(result.final_result())
                        
                        file_size = os.path.getsize(filename)
                        self.logger.info(f"Results saved successfully - File size: {file_size} bytes")
                        print(f"💾 Results saved to: {filename}")
                        
                        # Also save a detailed log of the result
                        self.logger.debug("=" * 80)
                        self.logger.debug("FULL RESULT CONTENT:")
                        self.logger.debug(result.final_result())
                        self.logger.debug("=" * 80)
                        
                    except Exception as e:
                        self.logger.error(f"Error saving results: {e}", exc_info=True)
                        print(f"❌ Error saving results: {e}")
                    
                    self.logger.info("Full analysis completed successfully")
                    return result
                else:
                    self.logger.warning(f"Analysis failed on attempt {attempt + 1} - No result returned")
                    print(f"❌ Analysis failed on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"Waiting {retry_delay} seconds before retry")
                        print(f"⏳ Waiting {retry_delay} seconds before retry...")
                        await asyncio.sleep(retry_delay)
                    
            except Exception as e:
                self.logger.error(f"Error on attempt {attempt + 1}: {e}", exc_info=True)
                print(f"❌ Error on attempt {attempt + 1}: {e}")
                
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    self.logger.warning("Rate limit exceeded - Will retry")
                    print("🚫 Rate limit exceeded. Waiting before retry...")
                    if attempt < max_retries - 1:
                        self.logger.info(f"Waiting {retry_delay} seconds before retry")
                        print(f"⏳ Waiting {retry_delay} seconds before retry...")
                        await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(f"Non-rate-limit error: {e}")
                    print(f"❌ Non-rate-limit error: {e}")
                    break
        
        self.logger.error("Analysis failed after all retries")
        print("❌ Analysis failed after all retries")
        return None

    async def analyze_extracted_urls(self, urls_file="post_urls.txt"):
        """
        Analyze posts from extracted URLs using fresh browser sessions
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING URL ANALYSIS")
        self.logger.info(f"Reading URLs from: {urls_file}")
        self.logger.info("=" * 80)
        
        print("🔍 Analyzing extracted post URLs...")
        
        # Read URLs from file
        try:
            with open(urls_file, 'r') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
            self.logger.info(f"Successfully read {len(urls)} URLs from file")
            self.logger.debug(f"URLs: {urls}")
        except FileNotFoundError:
            self.logger.error(f"File {urls_file} not found")
            print(f"❌ File {urls_file} not found. Please run URL extraction first.")
            return None
        
        print(f"📋 Found {len(urls)} URLs to analyze")
        
        results = []
        successful_count = 0
        failed_count = 0
        
        for i, url in enumerate(urls):  # Analyze all collected URLs (up to 50)
            self.logger.info(f"Analyzing post {i+1}/{len(urls)}")
            self.logger.info(f"URL: {url}")
            print(f"🔍 Analyzing post {i+1}/{len(urls)}: {url}")
            
            # Create fresh agent for each URL
            analysis_agent = Agent(
                task=f"""
                Analyze this Instagram post: {url}
                
                Navigate to the URL and extract:
                1. Post type (video, image, carousel)
                2. Full caption text (main post caption only, not comments)
                3. All hashtags used in the caption
                4. Engagement metrics (likes count, comments count, shares)
                5. Creator username and follower count
                6. Content style and visual description
                7. Audio/music used (if any)
                8. Call-to-action in caption
                9. Main topic/theme
                10. Posting time (if visible)
                
                TEXT EXTRACTION FROM IMAGES (OCR):
                11. Extract ALL text visible within the actual post image(s), including:
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
                
                EXTRACT: Individual comments and their like counts
                
                Format the analysis as JSON with all extracted data including text_in_images array.
                """,
                llm=self.llm,
            )
            
            try:
                start_time = time.time()
                result = await analysis_agent.run()
                elapsed_time = time.time() - start_time
                
                self.logger.debug(f"Analysis completed in {elapsed_time:.2f} seconds")
                
                if result and result.final_result():
                    results.append({
                        "url": url,
                        "analysis": result.final_result()
                    })
                    successful_count += 1
                    self.logger.info(f"Successfully analyzed post {i+1}")
                    self.logger.debug(f"Result: {result.final_result()[:500]}...")  # Log first 500 chars
                    print(f"✅ Successfully analyzed post {i+1}")
                else:
                    failed_count += 1
                    self.logger.warning(f"Failed to analyze post {i+1} - No result returned")
                    print(f"❌ Failed to analyze post {i+1}")
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error analyzing post {i+1}: {e}", exc_info=True)
                print(f"❌ Error analyzing post {i+1}: {e}")
            
            # Small delay between requests
            await asyncio.sleep(2)
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.save_dir / f"instagram_analysis_{timestamp}.json"
        
        self.logger.info(f"Analysis complete - Success: {successful_count}, Failed: {failed_count}")
        self.logger.info(f"Saving results to {filename}")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            file_size = os.path.getsize(filename)
            self.logger.info(f"Results saved successfully - File size: {file_size} bytes")
            print(f"💾 Analysis results saved to: {filename}")
        except Exception as e:
            self.logger.error(f"Error saving results: {e}", exc_info=True)
            print(f"❌ Error saving results: {e}")
        
        return results

    async def analyze_posts_agent(self, urls_file="post_urls.txt"):
        """
        Separate agent to analyze posts from extracted URLs
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING POST ANALYSIS WITH SEPARATE AGENT")
        self.logger.info(f"Reading URLs from: {urls_file}")
        self.logger.info("=" * 80)
        
        print("🔍 Starting post analysis with separate agent...")
        
        # Read URLs from file
        try:
            with open(urls_file, 'r') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
            self.logger.info(f"Successfully read {len(urls)} URLs from file")
        except FileNotFoundError:
            self.logger.error(f"File {urls_file} not found")
            print(f"❌ File {urls_file} not found. Please run URL extraction first.")
            return None
        
        # Convert relative URLs to full URLs if needed
        full_urls = []
        for url in urls:
            if url.startswith('/p/'):
                full_url = f"https://www.instagram.com{url}"
                full_urls.append(full_url)
                self.logger.debug(f"Converted relative URL: {url} -> {full_url}")
            elif url.startswith('https://www.instagram.com/p/'):
                full_urls.append(url)
                self.logger.debug(f"Using full URL: {url}")
            else:
                self.logger.warning(f"Skipping invalid URL format: {url}")
                print(f"⚠️ Skipping invalid URL format: {url}")
        
        urls = full_urls
        
        self.logger.info(f"Total valid URLs to analyze: {len(urls)}")
        self.logger.debug(f"URLs list: {urls}")
        print(f"📋 Found {len(urls)} URLs to analyze")
        
        # Create analysis agent
        analysis_agent = Agent(
            task=f"""
            Analyze Instagram posts from these URLs (up to 50 URLs): {urls}
            
            For each URL, navigate to the post and extract:
            
            1. POST TYPE: video, image, or carousel
            2. FULL CAPTION: main post caption only (not comments)
            3. HASHTAGS: all hashtags used in the caption
            4. ENGAGEMENT: likes count, comments count, shares count
            5. CREATOR INFO: username and follower count
            6. CONTENT STYLE: visual description and style
            7. AUDIO/MUSIC: what audio is used (if any)
            8. CALL-TO-ACTION: any CTA in the caption
            9. TOPIC/THEME: main subject of the post
            10. POSTING TIME: when it was posted (if visible)
            
            TEXT EXTRACTION FROM IMAGES (OCR):
            11. Extract ALL text visible within the actual post image(s), including:
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
            
            EXTRACT: Individual comments and their like counts
            
            After analyzing all posts, provide:
            - Detailed analysis of each post
            - Trends and patterns across posts
            - Hashtag insights
            - Content type performance
            - Engagement patterns
            - Creator insights
            - Text in images trends and patterns
            
            Format everything as comprehensive JSON with actionable insights including text_in_images array for each post.
            """,
            llm=self.llm,
        )
        
        self.logger.info("Starting analysis agent execution")
        
        try:
            start_time = time.time()
            result = await analysis_agent.run()
            elapsed_time = time.time() - start_time
            
            self.logger.info(f"Agent execution completed in {elapsed_time:.2f} seconds")
            
            if result and result.final_result():
                self.logger.info("Post analysis completed successfully")
                self.logger.debug(f"Result length: {len(str(result.final_result()))} characters")
                print("✅ Post analysis completed successfully!")
                
                # Save results
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = self.save_dir / f"instagram_analysis_{timestamp}.json"
                
                self.logger.info(f"Saving results to {filename}")
                
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(result.final_result())
                    
                    file_size = os.path.getsize(filename)
                    self.logger.info(f"Results saved successfully - File size: {file_size} bytes")
                    print(f"💾 Analysis results saved to: {filename}")
                    
                    # Log full result
                    self.logger.debug("=" * 80)
                    self.logger.debug("FULL RESULT CONTENT:")
                    self.logger.debug(result.final_result())
                    self.logger.debug("=" * 80)
                    
                except Exception as e:
                    self.logger.error(f"Error saving results: {e}", exc_info=True)
                    print(f"❌ Error saving results: {e}")
                
                return result
            else:
                self.logger.warning("Post analysis failed - No result returned")
                print("❌ Post analysis failed")
                return None
        except Exception as e:
            self.logger.error(f"Error during analysis: {e}", exc_info=True)
            print(f"❌ Error during analysis: {e}")
            return None


async def quick_analysis():
    """
    Quick 5-minute analysis - just the essentials
    """
    print("""
╔══════════════════════════════════════════════════╗
║     Quick Instagram Analysis                     ║
║     Fast trending content summary                ║
╚══════════════════════════════════════════════════╝
    """)
    
    llm = ChatGoogle(model='gemini-2.5-flash')
    username = INSTAGRAM_USERNAME
    password = INSTAGRAM_PASSWORD
    
    if not username or not password:
        print("❌ Instagram credentials not found in .env file")
        print("Please add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to your .env file")
        return
    
    # Login first
    login_agent = Agent(
        task=f"""
        Go to instagram.com
        
        Log in to Instagram with these credentials:
        Username: {username}
        Password: {password}
        
        Steps to follow:
        1. Click on the username/email field
        2. Type: {username}
        3. Click on the password field  
        4. Type: {password}
        5. Click the "Log In" button
        6. Wait for the page to load completely
        
        After login:
        7. If there's a "Not Now" button for saving login info, click it
        8. If there's a "Turn on Notifications" popup, click "Not Now"
        9. If there's a "Save Your Login Info" popup, click "Not Now"
        10. Navigate directly to instagram.com/explore
        11. Wait for the Explore page to load completely
        """,
        llm=llm,
    )
    
    print("🔐 Logging into Instagram...")
    await login_agent.run()
    
    # Check if 2FA is needed
    check_2fa_agent = Agent(
        task="""
        Check if there's a 2FA (Two-Factor Authentication) screen visible.
        Look for:
        - "Enter confirmation code" text
        - "Two-factor authentication" text
        - A code input field
        - "Confirm" or "Submit" button for 2FA
        
        If you see 2FA elements, respond with "2FA_REQUIRED"
        If you don't see 2FA elements and you're on the main feed, respond with "LOGIN_SUCCESS"
        """,
        llm=llm,
    )
    
    check_result = await check_2fa_agent.run()
    
    if "2FA_REQUIRED" in check_result.final_result():
        print("🔐 2FA detected! Please enter your 2FA code:")
        twofa_code = input("Enter 2FA code: ").strip()
        
        # Handle 2FA
        twofa_agent = Agent(
            task=f"""
            You are on Instagram's 2FA screen. Enter the 2FA code: {twofa_code}
            
            Steps:
            1. Click on the code input field
            2. Type: {twofa_code}
            3. Click "Confirm" or "Submit" button
            4. Wait for the page to load
            5. If there's a "Not Now" button for saving login info, click it
            6. If there's a "Turn on Notifications" popup, click "Not Now"
            7. Navigate directly to instagram.com/explore
            8. Wait for the Explore page to load completely
            """,
            llm=llm,
        )
        
        print("🔐 Entering 2FA code...")
        await twofa_agent.run()
    
    print("✓ Login complete\n")
    
    # Now do the analysis
    agent = Agent(
        task="""
        You are now on Instagram's Explore tab (logged in and already navigated to instagram.com/explore).
        
        Quick task: Scroll through the Explore feed and give me a brief summary:
        
        1. Look at the first 15-20 posts
        2. Identify what content is getting the most engagement
        3. What topics are trending right now?
        4. Videos or images - which performs better?
        5. Any patterns you notice?
        
        Give me a concise 5-point summary of what's trending on Instagram RIGHT NOW.
        Be specific and actionable.
        """,
        llm=llm,
    )
    
    print("🚀 Running quick analysis...\n")
    result = await agent.run()
    
    print("\n" + "="*60)
    print("📊 QUICK ANALYSIS RESULTS:")
    print("="*60)
    print(result.final_result())
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'quick_analysis_{timestamp}.txt', 'w') as f:
        f.write(f"Instagram Quick Analysis - {datetime.now().isoformat()}\n\n")
        f.write(result.final_result())
    
    print(f"\n✓ Results saved to: quick_analysis_{timestamp}.txt")
    
    return result


async def main(account_id=None):
    """
    Main entry point - choose your analysis mode
    
    Args:
        account_id: Optional account ID to save results to specific account folder
    """
    logger.info("=" * 80)
    logger.info("MAIN FUNCTION STARTED")
    if account_id:
        logger.info(f"Account ID: {account_id}")
    logger.info("=" * 80)
    
    # OPTION 1: Quick Analysis (5-10 minutes)
    # Uncomment to use:
    # await quick_analysis(account_id)
    
    # OPTION 2: Full Analysis (15-20 minutes)
    # Comprehensive analysis with posts, reels, and hashtags
    logger.info("Running full analysis mode")
    scroller = InstagramDoomscroller(account_id=account_id)
    result = await scroller.run_full_analysis()
    
    logger.info("=" * 80)
    logger.info("MAIN FUNCTION COMPLETED")
    logger.info("=" * 80)
    
    return result

async def extract_urls_only():
    """
    Extract URLs only - first step
    """
    scroller = InstagramDoomscroller()
    print("🔍 Step 1: Extracting post URLs...")
    await scroller.run_full_analysis()

async def analyze_urls_only():
    """
    Analyze extracted URLs - second step
    """
    scroller = InstagramDoomscroller()
    print("🔍 Step 2: Analyzing extracted URLs...")
    await scroller.analyze_extracted_urls()

async def analyze_posts_only():
    """
    Analyze posts using separate agent - second step
    """
    scroller = InstagramDoomscroller()
    print("🔍 Step 2: Analyzing posts with separate agent...")
    await scroller.analyze_posts_agent()


if __name__ == "__main__":
    """
    Setup instructions:
    
    1. Create .env file with:
       GOOGLE_API_KEY=your_gemini_api_key_here
       INSTAGRAM_USERNAME=your_instagram_username
       INSTAGRAM_PASSWORD=your_instagram_password
    
    2. Run: python main.py [--account ACCOUNT_ID]
    
    3. The script will automatically:
       - Open a browser
       - Log into Instagram using your credentials
       - Detect if 2FA is needed
       - If 2FA appears, prompt you to enter the code via command line
       - Start analyzing trending content
       - Save results to account-specific folder (if --account provided)
    
    Examples:
        python main.py                           # Save to root (generic account)
        python main.py --account acc_1729380000  # Save to protein cookies account
    
    Fully automated - just enter 2FA code in terminal if needed!
    """
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Instagram Doomscroller - Automated Instagram trend analysis',
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