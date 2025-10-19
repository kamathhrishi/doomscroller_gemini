# Instagram AI Doomscroller 🚀

An AI-powered Instagram analysis bot that automatically browses Instagram, identifies trending content, and analyzes what makes posts go viral. Think of it as your personal Instagram trend researcher that works 24/7.

## 🎯 What You're Building

An intelligent Instagram research assistant that:
- Replaces hours of manual scrolling with automated analysis
- Provides data-driven insights about trending content
- Helps you understand what makes content go viral
- Saves time while giving you competitive intelligence

It's like having a full-time social media analyst working 24/7, but powered by AI and automation!

## 🔍 Core Functionality

### 1. Automated Browsing
- Opens Instagram in a real browser (using your logged-in session)
- Scrolls through the feed like a human would
- Navigates to different sections (Reels, Explore, Hashtags)
- No manual intervention needed - fully autonomous

### 2. Content Analysis
The AI examines posts and extracts:
- **Engagement metrics**: Likes, comments, shares
- **Content type**: Video, image, or carousel
- **Topics/themes**: Fashion, tech, food, AI, memes, etc.
- **Captions**: What text accompanies the post
- **Hashtags**: Which tags are being used
- **Visual elements**: Style, editing, colors

### 3. Trend Detection
Identifies patterns in popular content:
- What type of content gets most engagement (videos vs images)
- Which topics are trending right now
- Optimal video length for virality
- Effective hooks (first 3 seconds of videos)
- Popular music/sounds being used
- Trending hashtags and their post counts

### 4. Data Collection & Storage
- Saves all findings to JSON files with timestamps
- Structured data format for easy analysis
- Can be integrated with Firebase/databases for long-term tracking
- Historical trend analysis over time

## 🛠️ Technical Architecture

```
┌─────────────────────────────────────────┐
│         User Interface / Control        │
│         (Python Script)                 │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│        Browser Use Framework            │
│  (AI-powered browser automation)        │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         OpenAI GPT-4o                   │
│   (Vision + Language Model)             │
│   - Sees the screen (vision)            │
│   - Understands content                 │
│   - Makes decisions                     │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│          Real Browser                   │
│     (Chromium via Playwright)           │
│   - Opens Instagram                     │
│   - Executes clicks/scrolls             │
│   - Captures screenshots                │
└─────────────────────────────────────────┘
```

### How It Works

1. **You give a natural language command**: 
   - "Find trending posts on Instagram"
   - "Analyze the top 10 reels"

2. **Browser Use takes over**:
   - Opens browser and navigates to Instagram
   - Takes screenshots of what's on screen
   - Sends screenshots to OpenAI GPT-4o

3. **OpenAI GPT-4o analyzes**:
   - "Sees" the Instagram feed using vision
   - Identifies posts, buttons, text
   - Decides next action: "scroll down", "click on reel", "read caption"

4. **Actions execute**:
   - Browser performs the action
   - New screenshot taken
   - Loop continues until task complete

5. **Results delivered**:
   - AI summarizes findings
   - Data saved to JSON file
   - Insights presented to you

## 📊 What You Can Do With It

### Content Creators
- Discover what content is currently trending
- Understand what makes posts go viral
- Optimize your content strategy
- Find trending hashtags to use

### Marketers
- Track competitor performance
- Identify emerging trends before they peak
- Analyze audience preferences
- Plan content calendars based on data

### Researchers
- Study social media behavior patterns
- Analyze content virality factors
- Track trend evolution over time
- Generate datasets for ML models

### Personal Use
- Stay updated on trends in your niche
- Find inspiration for content
- Automate your daily Instagram browsing
- Get summarized insights instead of endless scrolling

## 🎨 Example Use Cases

### Use Case 1: Daily Trend Report
```
Schedule: Every morning at 9 AM
Action: Analyze top 20 posts
Output: "Today's trends: AI tools, fitness reels, recipe videos"
```

### Use Case 2: Competitor Analysis
```
Task: Track specific accounts
Action: Visit profiles, analyze their posts
Output: "Competitor X posts 3x/day, videos get 5x more engagement"
```

### Use Case 3: Hashtag Research
```
Task: Find best hashtags for "tech startup"
Action: Search explore page, analyze top hashtags
Output: "Top hashtags: #TechStartup (2.3M), #StartupLife (5.1M)"
```

### Use Case 4: Content Strategy
```
Task: What video length works best?
Action: Analyze top 100 reels
Output: "15-30 second videos get 3x more engagement than 60+ seconds"
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- OpenAI API Key
- Instagram account (you'll need to be logged in)

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd doomscroller_ai
```

2. **Install dependencies**
```bash
pip install browser-use langchain-google-genai python-dotenv
```

3. **Set up environment variables**
Create a `.env` file:
```bash
GOOGLE_API_KEY=your_gemini_api_key_here
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
```

4. **Run the application**
```bash
python main.py
```

**Note:** If 2FA (Two-Factor Authentication) is enabled on your Instagram account, the script will detect it and prompt you to enter the 2FA code in the terminal/command line.

### Usage Modes

#### Quick Analysis (Fast & Simple)
```python
await quick_analysis()
```
- Analyzes top 10 trending posts
- Quick summary of current trends
- Perfect for daily checks

#### Full Analysis (Comprehensive)
```python
scroller = InstagramDoomscroller()
await scroller.run_full_analysis()
```
- Complete trend analysis
- Video deep-dive insights
- Hashtag tracking
- Detailed JSON reports

## 💡 Key Advantages

### 1. Fully Automated
- No manual scrolling or clicking
- Works while you sleep
- Can run continuously

### 2. AI-Powered Intelligence
- Understands context, not just numbers
- Identifies patterns humans might miss
- Adapts to UI changes automatically

### 3. Vision-Based
- Sees Instagram like a human would
- Works even when HTML structure changes
- Can analyze images/videos visually

### 4. Scalable
- Analyze 100s of posts quickly
- Run multiple analyses in parallel
- Track trends over days/weeks/months

### 5. Actionable Insights
- Not just data - actual recommendations
- Understands "why" content works
- Provides strategic advice

## 📁 Project Structure

```
doomscroller_ai/
├── main.py                      # Main AI-driven scraper with logging
├── log_to_playwright.py         # Convert logs to Playwright script
├── playwright_scraper.py        # Generated deterministic scraper
├── .env                         # Environment variables
├── README.md                    # This file
├── LOGGING_GUIDE.md             # Detailed logging documentation
├── requirements.txt             # Python dependencies
├── logs/                        # Detailed execution logs
│   └── instagram_scraper_*.log
├── instagram_trends_*.json      # AI analysis results
├── instagram_results_*.json     # Playwright scraper results
└── post_urls.txt                # Collected post URLs
```

## 🔧 Configuration

### Environment Variables
- `GOOGLE_API_KEY`: Your Google Gemini API key
- `INSTAGRAM_USERNAME`: Your Instagram username
- `INSTAGRAM_PASSWORD`: Your Instagram password

### Customization Options
You can modify the analysis parameters in `main.py`:
- Number of posts to analyze
- Analysis depth
- Output format
- Specific hashtags to track

## 📈 Sample Output

### JSON Report Structure
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "analysis": {
    "posts": [
      {
        "rank": 1,
        "type": "video",
        "likes": "50.3K",
        "comments": "234",
        "topic": "AI technology",
        "caption": "This AI tool changed everything...",
        "hashtags": ["#ai", "#tech", "#innovation"]
      }
    ],
    "trends": {
      "most_popular_type": "video",
      "trending_topics": ["AI", "Fashion", "Food"],
      "avg_engagement": "high"
    }
  }
}
```

## 📝 Logging & Playwright Conversion

### NEW: Convert AI Scraping to Deterministic Scripts

The scraper now includes comprehensive logging that allows you to convert AI-driven scraping into fast, deterministic Playwright scripts!

#### Why This Matters

| AI Scraper | Playwright Script |
|-----------|------------------|
| ⏱️ Slower (AI decisions) | ⚡ Much faster |
| 💰 API costs | 🆓 No API costs |
| 🎲 Variable results | ✅ Deterministic |
| 🐛 Harder to debug | 🔍 Easy to debug |

#### Quick Start

1. **Run the AI scraper** (it automatically logs everything):
```bash
python3 main.py
```

2. **Convert logs to Playwright**:
```bash
python3 log_to_playwright.py
```

3. **Run the generated Playwright script**:
```bash
pip install playwright
playwright install chromium
python3 playwright_scraper.py
```

#### What Gets Logged

- ✅ Every action performed
- ✅ URLs collected and analyzed  
- ✅ Timing information
- ✅ Errors and warnings
- ✅ Full results and insights
- ✅ Success/failure rates

Logs are saved in `logs/instagram_scraper_TIMESTAMP.log`

#### The Generated Playwright Script

The `playwright_scraper.py` script includes:
- Deterministic login flow
- URL collection (15 scrolls max, 50 URLs max)
- Post analysis (captions, hashtags, likes, post type)
- Error handling
- JSON results export

#### Use Cases

**Development Phase:** Use the AI scraper to explore and understand Instagram's behavior

**Production Phase:** Use the generated Playwright script for fast, reliable, cost-free scraping

📚 **For detailed documentation, see [LOGGING_GUIDE.md](LOGGING_GUIDE.md)**

## 🚀 Future Enhancements

### Planned Features
- **Real-time monitoring**: Continuous feed analysis
- **Database integration**: Store trends in Firebase/PostgreSQL
- **Competitor tracking**: Monitor specific accounts
- **Sentiment analysis**: Analyze comments and reactions
- **Prediction models**: Forecast which content will go viral
- **Multi-platform**: Expand to TikTok, Twitter, YouTube
- **API service**: Provide trends-as-a-service
- **Dashboard**: Visual analytics and charts

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Important Notes

- **Instagram Terms**: This tool is for educational and research purposes. Please ensure compliance with Instagram's Terms of Service
- **Rate Limiting**: Be mindful of API rate limits and Instagram's usage policies
- **Privacy**: The tool only analyzes publicly available content
- **Authentication**: You need to be logged into Instagram in your browser

## 🆘 Troubleshooting

### Common Issues

1. **"No module named 'browser_use'"**
   ```bash
   pip install browser-use
   ```

2. **"Invalid API key"**
   - Check your `.env` file has the correct `GOOGLE_API_KEY`
   - Verify the API key is valid and has Gemini access

3. **"Instagram credentials not found"**
   - Make sure you have `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` in your `.env` file
   - Check that the credentials are correct

4. **"Instagram not loading"**
   - Check your internet connection
   - Verify your Instagram credentials are correct
   - Try running the script again

5. **"No posts found"**
   - Instagram might have changed its layout
   - Try updating the browser-use library
   - Check if you're on the correct Instagram page

## 📞 Support

If you encounter any issues or have questions:
1. Check the troubleshooting section above
2. Search existing issues in the repository
3. Create a new issue with detailed information

---

**Happy trend hunting! 🎯**

*Built with ❤️ using Browser Use, Google Gemini, and Python*
