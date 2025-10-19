"""
Google Deep Research API Integration
Advanced research capabilities using Google's Gemini API with web search and deep analysis
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from urllib.parse import quote

# Load environment variables
load_dotenv()

class GoogleDeepResearcher:
    """
    Advanced research tool using Google's Gemini API with web search capabilities
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Google Deep Researcher
        
        Args:
            api_key: Google API key (if not provided, will use GOOGLE_API_KEY from .env)
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY in .env file")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Initialize models
        self.research_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.analysis_model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Research cache to avoid duplicate API calls
        self.research_cache = {}
        
    def _get_web_search_results(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Perform web search using Google Custom Search API
        Note: You need to set up Google Custom Search Engine and get API key
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results with titles, snippets, and URLs
        """
        # This is a placeholder - you'll need to implement actual web search
        # You can use Google Custom Search API, SerpAPI, or other search services
        
        # For now, return mock data structure
        return [
            {
                "title": f"Search result for: {query}",
                "snippet": f"Detailed information about {query}...",
                "url": f"https://example.com/{query.replace(' ', '-')}",
                "published_date": datetime.now().isoformat()
            }
        ]
    
    def _create_research_prompt(self, topic: str, research_goals: List[str], 
                              search_results: List[Dict] = None) -> str:
        """
        Create a comprehensive research prompt for deep analysis
        
        Args:
            topic: Main research topic
            research_goals: List of specific research objectives
            search_results: Optional web search results
            
        Returns:
            Formatted prompt for Gemini
        """
        prompt = f"""
# INSTAGRAM ACCOUNTS RESEARCH ANALYSIS

## RESEARCH TOPIC
{topic}

## RESEARCH OBJECTIVES
{chr(10).join(f"- {goal}" for goal in research_goals)}

## WEB SEARCH CONTEXT
{self._format_search_results(search_results) if search_results else "No web search results provided"}

## CRITICAL REQUIREMENTS FOR INSTAGRAM ACCOUNTS

You MUST provide ONLY REAL, VERIFIABLE Instagram accounts. Follow these strict guidelines:

### 1. ACCOUNT VERIFICATION RULES
- Only include accounts that actually exist on Instagram
- Use the exact format: @username (e.g., @natgeo, @vogue)
- NO generic descriptions like "Established media outlets"
- NO made-up account names
- NO URLs or website references
- NO placeholder text

### 2. ACCOUNT FORMAT REQUIREMENTS
Each account must be in this exact format:
{{
    "name": "@actual_username",
    "followers": "X.XM" or "X.XK" (realistic numbers),
    "engagement": "X.X%" (realistic engagement rates),
    "description": "Brief description of what this account posts"
}}

### 3. RESEARCH FOCUS
Focus on finding REAL Instagram accounts in the {topic.split()[-1] if 'niche' in topic else 'specified'} niche that:
- Are actively posting content
- Have significant followings (10K+ followers)
- Post relevant content to the niche
- Are well-known in their field

### 4. ACCOUNT CATEGORIES TO FIND
- **Top Creators**: Individual content creators with large followings
- **Brands/Companies**: Official brand accounts in the niche
- **Influencers**: People with significant influence in the niche
- **Educational Accounts**: Accounts that teach about the niche
- **Community Accounts**: Accounts that bring people together around the niche

## OUTPUT FORMAT
Return the analysis as structured JSON with this EXACT format:
{{
    "executive_summary": "Brief summary of findings about Instagram accounts in this niche",
    "competitive_landscape": {{
        "key_players": [
            {{
                "name": "@real_account_1",
                "followers": "2.1M",
                "engagement": "4.2%",
                "description": "Top fitness influencer with workout content"
            }},
            {{
                "name": "@real_account_2", 
                "followers": "850K",
                "engagement": "3.8%",
                "description": "Nutrition expert sharing healthy recipes"
            }}
        ],
        "market_dynamics": "Analysis of the Instagram landscape in this niche",
        "opportunities": ["Specific opportunities for new accounts"],
        "threats": ["Challenges in this niche"]
    }},
    "trend_analysis": {{
        "current_trends": ["Current content trends in this niche"],
        "historical_context": "How this niche has evolved on Instagram",
        "future_projections": "Where this niche is heading"
    }},
    "actionable_recommendations": {{
        "next_steps": ["Specific actions to take based on findings"],
        "implementation_strategies": "How to implement recommendations",
        "success_metrics": "How to measure success"
    }},
    "confidence_score": 0.85,
    "research_quality": "high"
}}

## VERIFICATION CHECKLIST
Before including any account, verify:
✓ Account name follows @username format
✓ Account is real and exists on Instagram
✓ Follower count is realistic for the niche
✓ Engagement rate is realistic (1-10%)
✓ Description accurately reflects the account's content
✓ No generic or placeholder text

## EXAMPLES OF GOOD ACCOUNTS
✅ @natgeo (National Geographic)
✅ @vogue (Vogue Magazine)
✅ @gymshark (Fitness brand)
✅ @therock (Dwayne Johnson)

## EXAMPLES OF BAD ENTRIES
❌ "Established media outlets (e.g., National Geographic, Vogue)"
❌ "https://www.instagram.com/account"
❌ "Top fitness influencers"
❌ "Major brands in this niche"

Remember: ONLY include accounts you can verify exist on Instagram with the exact @username format.
"""
        return prompt
    
    def _format_search_results(self, search_results: List[Dict]) -> str:
        """Format search results for inclusion in prompt"""
        if not search_results:
            return "No search results available"
        
        formatted = "### WEB SEARCH RESULTS\n\n"
        for i, result in enumerate(search_results[:5], 1):  # Limit to top 5
            formatted += f"**Result {i}:**\n"
            formatted += f"- Title: {result.get('title', 'N/A')}\n"
            formatted += f"- Snippet: {result.get('snippet', 'N/A')}\n"
            formatted += f"- URL: {result.get('url', 'N/A')}\n\n"
        
        return formatted
    
    async def deep_research_streaming(self, topic: str, research_goals: List[str], 
                                     include_web_search: bool = True,
                                     cache_results: bool = True):
        """
        Perform deep research on a given topic with streaming progress updates
        
        Args:
            topic: Main research topic
            research_goals: List of specific research objectives
            include_web_search: Whether to include web search results
            cache_results: Whether to cache results for future use
            
        Yields:
            Progress updates and final results
        """
        # Check cache first
        cache_key = f"{topic}_{hash(tuple(research_goals))}"
        if cache_results and cache_key in self.research_cache:
            yield {"status": "cached", "message": "📋 Using cached research results", "data": self.research_cache[cache_key]}
            return
        
        yield {"status": "progress", "message": f"🔍 Starting deep research on: {topic}"}
        yield {"status": "progress", "message": f"🎯 Research goals: {', '.join(research_goals)}"}
        
        # Perform web search if requested
        search_results = None
        if include_web_search:
            yield {"status": "progress", "message": "🌐 Performing web search..."}
            yield {"status": "progress", "message": "🔍 Searching for current data and trends..."}
            search_results = self._get_web_search_results(topic)
            yield {"status": "progress", "message": f"✅ Found {len(search_results)} search results"}
            yield {"status": "progress", "message": "📋 Processing search results..."}
        
        # Create research prompt
        yield {"status": "progress", "message": "📝 Creating research prompt..."}
        prompt = self._create_research_prompt(topic, research_goals, search_results)
        
        # Generate research analysis
        yield {"status": "progress", "message": "🤖 Generating deep analysis with Gemini..."}
        yield {"status": "progress", "message": "🧠 AI is analyzing data and generating insights..."}
        try:
            response = self.research_model.generate_content(prompt)
            analysis_text = response.text
            
            yield {"status": "progress", "message": "📊 Processing AI response..."}
            yield {"status": "progress", "message": "🔍 Extracting structured data from analysis..."}
            
            # Try to parse as JSON
            try:
                # Extract JSON from response if wrapped in markdown
                if '```json' in analysis_text:
                    json_start = analysis_text.find('```json') + 7
                    json_end = analysis_text.find('```', json_start)
                    analysis_text = analysis_text[json_start:json_end].strip()
                elif '```' in analysis_text:
                    json_start = analysis_text.find('```') + 3
                    json_end = analysis_text.find('```', json_start)
                    analysis_text = analysis_text[json_start:json_end].strip()
                
                analysis = json.loads(analysis_text)
                
            except json.JSONDecodeError:
                # If JSON parsing fails, create structured response
                yield {"status": "progress", "message": "⚠️ JSON parsing failed, creating structured response..."}
                analysis = {
                    "executive_summary": analysis_text[:500] + "...",
                    "detailed_analysis": {"raw_analysis": analysis_text},
                    "trend_analysis": {"current_trends": [], "historical_context": "", "future_projections": ""},
                    "competitive_landscape": {"key_players": [], "market_dynamics": "", "opportunities": [], "threats": []},
                    "data_insights": {"quantitative_analysis": "", "statistical_patterns": "", "performance_metrics": ""},
                    "expert_perspectives": {"industry_opinions": "", "academic_findings": "", "professional_recommendations": ""},
                    "risk_assessment": {"potential_risks": [], "mitigation_strategies": "", "contingency_planning": ""},
                    "actionable_recommendations": {"next_steps": [], "implementation_strategies": "", "success_metrics": ""},
                    "future_research": {"further_investigation": [], "emerging_questions": "", "long_term_priorities": ""},
                    "confidence_score": 0.7,
                    "research_quality": "medium",
                    "sources_used": [result.get('url', '') for result in (search_results or [])],
                    "last_updated": datetime.now().isoformat(),
                    "raw_response": analysis_text
                }
            
            # Add metadata
            analysis["research_metadata"] = {
                "topic": topic,
                "research_goals": research_goals,
                "search_results_included": include_web_search,
                "search_results_count": len(search_results) if search_results else 0,
                "generated_at": datetime.now().isoformat(),
                "model_used": "gemini-2.0-flash-exp"
            }
            
            # Cache results
            if cache_results:
                self.research_cache[cache_key] = analysis
            
            yield {"status": "completed", "message": "✅ Deep research analysis complete", "data": analysis}
            
        except Exception as e:
            yield {"status": "error", "message": f"❌ Research failed: {e}", "error": str(e)}
    
    async def deep_research(self, topic: str, research_goals: List[str], 
                           include_web_search: bool = True,
                           cache_results: bool = True) -> Dict[str, Any]:
        """
        Perform deep research on a given topic
        
        Args:
            topic: Main research topic
            research_goals: List of specific research objectives
            include_web_search: Whether to include web search results
            cache_results: Whether to cache results for future use
            
        Returns:
            Comprehensive research analysis
        """
        # Check cache first
        cache_key = f"{topic}_{hash(tuple(research_goals))}"
        if cache_results and cache_key in self.research_cache:
            print("📋 Using cached research results")
            return self.research_cache[cache_key]
        
        print(f"🔍 Starting deep research on: {topic}")
        print(f"🎯 Research goals: {', '.join(research_goals)}")
        
        # Perform web search if requested
        search_results = None
        if include_web_search:
            print("🌐 Performing web search...")
            search_results = self._get_web_search_results(topic)
            print(f"✅ Found {len(search_results)} search results")
        
        # Create research prompt
        prompt = self._create_research_prompt(topic, research_goals, search_results)
        
        # Generate research analysis
        print("🤖 Generating deep analysis with Gemini...")
        try:
            response = self.research_model.generate_content(prompt)
            analysis_text = response.text
            
            # Try to parse as JSON
            try:
                # Extract JSON from response if wrapped in markdown
                if '```json' in analysis_text:
                    json_start = analysis_text.find('```json') + 7
                    json_end = analysis_text.find('```', json_start)
                    analysis_text = analysis_text[json_start:json_end].strip()
                elif '```' in analysis_text:
                    json_start = analysis_text.find('```') + 3
                    json_end = analysis_text.find('```', json_start)
                    analysis_text = analysis_text[json_start:json_end].strip()
                
                analysis = json.loads(analysis_text)
                
            except json.JSONDecodeError:
                # If JSON parsing fails, create structured response
                analysis = {
                    "executive_summary": analysis_text[:500] + "...",
                    "detailed_analysis": {"raw_analysis": analysis_text},
                    "trend_analysis": {"current_trends": [], "historical_context": "", "future_projections": ""},
                    "competitive_landscape": {"key_players": [], "market_dynamics": "", "opportunities": [], "threats": []},
                    "data_insights": {"quantitative_analysis": "", "statistical_patterns": "", "performance_metrics": ""},
                    "expert_perspectives": {"industry_opinions": "", "academic_findings": "", "professional_recommendations": ""},
                    "risk_assessment": {"potential_risks": [], "mitigation_strategies": "", "contingency_planning": ""},
                    "actionable_recommendations": {"next_steps": [], "implementation_strategies": "", "success_metrics": ""},
                    "future_research": {"further_investigation": [], "emerging_questions": "", "long_term_priorities": ""},
                    "confidence_score": 0.7,
                    "research_quality": "medium",
                    "sources_used": [result.get('url', '') for result in (search_results or [])],
                    "last_updated": datetime.now().isoformat(),
                    "raw_response": analysis_text
                }
            
            # Add metadata
            analysis["research_metadata"] = {
                "topic": topic,
                "research_goals": research_goals,
                "search_results_included": include_web_search,
                "search_results_count": len(search_results) if search_results else 0,
                "generated_at": datetime.now().isoformat(),
                "model_used": "gemini-2.0-flash-exp"
            }
            
            # Cache results
            if cache_results:
                self.research_cache[cache_key] = analysis
            
            print("✅ Deep research analysis complete")
            return analysis
            
        except Exception as e:
            print(f"❌ Research failed: {e}")
            return {
                "error": str(e),
                "topic": topic,
                "research_goals": research_goals,
                "generated_at": datetime.now().isoformat()
            }
    
    def compare_research(self, research_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare multiple research results to identify patterns and insights
        
        Args:
            research_results: List of research analysis results
            
        Returns:
            Comparative analysis
        """
        print(f"📊 Comparing {len(research_results)} research results...")
        
        # Extract key insights from each research result
        insights = []
        for i, result in enumerate(research_results):
            insight = {
                "index": i,
                "topic": result.get("research_metadata", {}).get("topic", f"Research {i+1}"),
                "executive_summary": result.get("executive_summary", ""),
                "key_trends": result.get("trend_analysis", {}).get("current_trends", []),
                "recommendations": result.get("actionable_recommendations", {}).get("next_steps", []),
                "confidence_score": result.get("confidence_score", 0.5)
            }
            insights.append(insight)
        
        # Create comparison prompt
        comparison_prompt = f"""
# RESEARCH COMPARISON ANALYSIS

Compare and analyze the following research results to identify:
1. Common patterns and themes
2. Conflicting information or perspectives
3. Emerging consensus or trends
4. Unique insights from each study
5. Synthesis of findings
6. Meta-recommendations

## RESEARCH RESULTS
{json.dumps(insights, indent=2)}

## OUTPUT FORMAT
Return as JSON:
{{
    "comparative_analysis": {{
        "common_patterns": ["pattern1", "pattern2"],
        "conflicting_views": ["conflict1", "conflict2"],
        "emerging_consensus": "string",
        "unique_insights": ["insight1", "insight2"]
    }},
    "synthesis": {{
        "overall_trends": ["trend1", "trend2"],
        "key_findings": ["finding1", "finding2"],
        "meta_recommendations": ["rec1", "rec2"]
    }},
    "research_quality": {{
        "highest_confidence": 0.95,
        "average_confidence": 0.85,
        "quality_assessment": "high|medium|low"
    }},
    "next_steps": ["step1", "step2"]
}}
"""
        
        try:
            response = self.analysis_model.generate_content(comparison_prompt)
            comparison_text = response.text
            
            # Parse JSON response
            if '```json' in comparison_text:
                json_start = comparison_text.find('```json') + 7
                json_end = comparison_text.find('```', json_start)
                comparison_text = comparison_text[json_start:json_end].strip()
            
            comparison = json.loads(comparison_text)
            comparison["research_count"] = len(research_results)
            comparison["generated_at"] = datetime.now().isoformat()
            
            print("✅ Research comparison complete")
            return comparison
            
        except Exception as e:
            print(f"❌ Comparison failed: {e}")
            return {"error": str(e), "research_count": len(research_results)}
    
    def save_research(self, research_data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Save research results to JSON file
        
        Args:
            research_data: Research analysis data
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            topic = research_data.get("research_metadata", {}).get("topic", "research")
            safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"deep_research_{safe_topic}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(research_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Research saved to: {filename}")
        return filename
    
    def get_research_summary(self, research_data: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of research results
        
        Args:
            research_data: Research analysis data
            
        Returns:
            Formatted summary string
        """
        if "error" in research_data:
            return f"❌ Research Error: {research_data['error']}"
        
        summary = f"""
# RESEARCH SUMMARY

## Topic: {research_data.get('research_metadata', {}).get('topic', 'Unknown')}

## Executive Summary
{research_data.get('executive_summary', 'No summary available')}

## Key Trends
{', '.join(research_data.get('trend_analysis', {}).get('current_trends', []))}

## Top Recommendations
{', '.join(research_data.get('actionable_recommendations', {}).get('next_steps', []))}

## Confidence Score: {research_data.get('confidence_score', 'N/A')}
## Research Quality: {research_data.get('research_quality', 'N/A')}

## Generated: {research_data.get('research_metadata', {}).get('generated_at', 'Unknown')}
"""
        return summary


# Example usage and testing
async def main():
    """
    Example usage of Google Deep Researcher
    """
    print("🚀 Google Deep Research API Demo")
    print("=" * 50)
    
    # Initialize researcher
    try:
        researcher = GoogleDeepResearcher()
        print("✅ Google Deep Researcher initialized")
    except ValueError as e:
        print(f"❌ Initialization failed: {e}")
        print("Please set GOOGLE_API_KEY in your .env file")
        return
    
    # Example 1: Deep research on AI trends
    print("\n🔍 Example 1: AI Trends Research")
    print("-" * 30)
    
    ai_research = await researcher.deep_research(
        topic="Artificial Intelligence Trends 2024",
        research_goals=[
            "Identify the top 5 AI trends for 2024",
            "Analyze market growth and investment patterns",
            "Examine emerging AI applications in business",
            "Assess risks and challenges in AI adoption",
            "Provide actionable recommendations for AI implementation"
        ],
        include_web_search=True
    )
    
    # Print summary
    print(researcher.get_research_summary(ai_research))
    
    # Save results
    researcher.save_research(ai_research)
    
    # Example 2: Compare multiple research topics
    print("\n📊 Example 2: Multi-topic Research Comparison")
    print("-" * 40)
    
    # Research multiple topics
    topics = [
        ("Quantum Computing", ["Current capabilities", "Future applications", "Market outlook"]),
        ("Blockchain Technology", ["Recent developments", "Use cases", "Regulatory landscape"]),
        ("Sustainable Energy", ["Renewable energy trends", "Storage solutions", "Policy impacts"])
    ]
    
    all_research = []
    for topic, goals in topics:
        print(f"\n🔍 Researching: {topic}")
        research = await researcher.deep_research(topic, goals, include_web_search=False)
        all_research.append(research)
    
    # Compare all research
    comparison = researcher.compare_research(all_research)
    print("\n📈 Comparative Analysis:")
    print(json.dumps(comparison, indent=2))
    
    # Save comparison
    researcher.save_research(comparison, "research_comparison.json")


if __name__ == "__main__":
    asyncio.run(main())
