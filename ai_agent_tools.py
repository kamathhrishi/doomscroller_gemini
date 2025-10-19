"""
AI Agent with Tool Calling Capabilities
Provides tools for analyzing JSON data, keyword matching, and more
With robust error handling, retries, and fallbacks
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
from datetime import datetime
import time
import logging
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_json_loads(json_string: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Safely parse JSON with multiple attempts and fallbacks"""
    for attempt in range(max_retries):
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse attempt {attempt + 1} failed: {e}")
            
            # Try to fix common JSON issues
            if attempt < max_retries - 1:
                # Remove markdown code blocks
                json_string = re.sub(r'```json\s*', '', json_string)
                json_string = re.sub(r'```\s*', '', json_string)
                
                # Remove trailing commas
                json_string = re.sub(r',\s*}', '}', json_string)
                json_string = re.sub(r',\s*]', ']', json_string)
                
                # Try to extract JSON object if embedded in text
                json_match = re.search(r'\{.*\}', json_string, re.DOTALL)
                if json_match:
                    json_string = json_match.group(0)
            else:
                logger.error(f"Failed to parse JSON after {max_retries} attempts")
                return None
    
    return None


def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying functions on error"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts")
            
            # Return error dict instead of raising
            return {
                "error": f"Failed after {max_retries} attempts",
                "last_error": str(last_exception),
                "function": func.__name__
            }
        return wrapper
    return decorator


class AnalysisTools:
    """Collection of tools for data analysis with robust error handling"""
    
    @staticmethod
    def get_consolidated_data(platform: str = "all") -> Dict[str, Any]:
        """Get consolidated Instagram/YouTube data (faster than individual files)"""
        try:
            data_dir = Path("data/consolidated")
            
            if not data_dir.exists():
                return {
                    "error": "Consolidated data not found. Run consolidate_media_data.py first",
                    "suggestion": "python consolidate_media_data.py"
                }
            
            result = {}
            
            if platform in ["instagram", "all"]:
                instagram_file = data_dir / "instagram_consolidated.json"
                if instagram_file.exists():
                    with open(instagram_file, 'r', encoding='utf-8') as f:
                        result["instagram"] = json.load(f)
            
            if platform in ["youtube", "all"]:
                youtube_file = data_dir / "youtube_consolidated.json"
                if youtube_file.exists():
                    with open(youtube_file, 'r', encoding='utf-8') as f:
                        result["youtube"] = json.load(f)
            
            if not result:
                return {"error": f"No consolidated data found for platform: {platform}"}
            
            return {
                "success": True,
                "platform": platform,
                "data": result
            }
        
        except Exception as e:
            return {"error": f"Failed to load consolidated data: {str(e)}"}
    
    @staticmethod
    def get_media_summary(platform: str = "all") -> Dict[str, Any]:
        """Get lightweight summary of Instagram/YouTube data (very fast)"""
        try:
            data_dir = Path("data/consolidated")
            
            if not data_dir.exists():
                return {"error": "Consolidated data not found. Run consolidate_media_data.py first"}
            
            result = {}
            
            if platform in ["instagram", "all"]:
                instagram_summary = data_dir / "instagram_summary.json"
                if instagram_summary.exists():
                    with open(instagram_summary, 'r', encoding='utf-8') as f:
                        result["instagram"] = json.load(f)
            
            if platform in ["youtube", "all"]:
                youtube_summary = data_dir / "youtube_summary.json"
                if youtube_summary.exists():
                    with open(youtube_summary, 'r', encoding='utf-8') as f:
                        result["youtube"] = json.load(f)
            
            if not result:
                return {"error": f"No summary data found for platform: {platform}"}
            
            return {
                "success": True,
                "platform": platform,
                "summaries": result
            }
        
        except Exception as e:
            return {"error": f"Failed to load summary data: {str(e)}"}
    
    @staticmethod
    def search_media_content(query: str, platform: str = "all", limit: int = 20) -> Dict[str, Any]:
        """Search through consolidated media data (fast keyword search)"""
        try:
            # Get consolidated data
            consolidated = AnalysisTools.get_consolidated_data(platform)
            
            if "error" in consolidated:
                return consolidated
            
            query_lower = query.lower()
            results = []
            
            data = consolidated.get("data", {})
            
            # Search Instagram posts
            if "instagram" in data:
                for post in data["instagram"].get("posts", []):
                    caption = post.get("caption", "").lower()
                    hashtags = [h.lower() for h in post.get("hashtags", [])]
                    
                    if query_lower in caption or query_lower in " ".join(hashtags):
                        results.append({
                            "platform": "instagram",
                            "type": post.get("type", ""),
                            "url": post.get("url", ""),
                            "caption": post.get("caption", "")[:200],
                            "hashtags": post.get("hashtags", [])[:10],
                            "likes": post.get("likes", 0),
                            "comments": post.get("comments", 0),
                            "creator": post.get("creator", "")
                        })
            
            # Search YouTube videos
            if "youtube" in data:
                for video in data["youtube"].get("videos", []):
                    title = video.get("title", "").lower()
                    description = video.get("description", "").lower()
                    tags = [t.lower() for t in video.get("tags", [])]
                    
                    if query_lower in title or query_lower in description or query_lower in " ".join(tags):
                        results.append({
                            "platform": "youtube",
                            "url": video.get("url", ""),
                            "title": video.get("title", "")[:200],
                            "description": video.get("description", "")[:200],
                            "tags": video.get("tags", [])[:10],
                            "views": video.get("views", 0),
                            "likes": video.get("likes", 0),
                            "channel": video.get("channel", "")
                        })
            
            # Sort by engagement/views and limit
            results = sorted(
                results,
                key=lambda x: x.get("likes", 0) + x.get("views", 0) + x.get("comments", 0),
                reverse=True
            )[:limit]
            
            return {
                "success": True,
                "query": query,
                "total_results": len(results),
                "results": results
            }
        
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}
    
    @staticmethod
    @retry_on_error(max_retries=2)
    def list_json_files(directory: str = ".") -> Dict[str, Any]:
        """List all JSON files in a directory with metadata"""
        try:
            path = Path(directory)
            if not path.exists():
                return {"error": f"Directory {directory} not found"}
            
            json_files = []
            for file in path.glob("*.json"):
                try:
                    size = file.stat().st_size
                    modified = datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                    json_files.append({
                        "filename": file.name,
                        "path": str(file),
                        "size_bytes": size,
                        "size_kb": round(size / 1024, 2),
                        "modified": modified
                    })
                except Exception as e:
                    continue
            
            return {
                "success": True,
                "count": len(json_files),
                "files": sorted(json_files, key=lambda x: x["modified"], reverse=True)
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    @retry_on_error(max_retries=2)
    def read_json_file(filename: str) -> Dict[str, Any]:
        """Read and parse a JSON file with robust error handling"""
        try:
            path = Path(filename)
            if not path.exists():
                # Try to find the file in common directories
                for search_dir in [".", "data", "data/accounts"]:
                    search_path = Path(search_dir) / filename
                    if search_path.exists():
                        path = search_path
                        break
                else:
                    return {"error": f"File {filename} not found in any known location"}
            
            # Read file content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse JSON with fallbacks
            data = safe_json_loads(content)
            if data is None:
                return {
                    "error": "Failed to parse JSON file",
                    "filename": str(path),
                    "content_preview": content[:200] if len(content) > 200 else content
                }
            
            return {
                "success": True,
                "filename": str(path),
                "data": data,
                "summary": {
                    "type": type(data).__name__,
                    "keys": list(data.keys()) if isinstance(data, dict) else None,
                    "length": len(data) if isinstance(data, (list, dict)) else None,
                    "file_size": path.stat().st_size
                }
            }
        except UnicodeDecodeError as e:
            return {"error": f"File encoding error: {str(e)}", "filename": filename}
        except PermissionError as e:
            return {"error": f"Permission denied: {str(e)}", "filename": filename}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}", "filename": filename}
    
    @staticmethod
    def keyword_search(data: Any, keywords: List[str], case_sensitive: bool = False) -> Dict[str, Any]:
        """Search for keywords in JSON data recursively"""
        try:
            if isinstance(keywords, str):
                keywords = [keywords]
            
            results = []
            
            def search_recursive(obj, path="root"):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}"
                        # Check key
                        for keyword in keywords:
                            key_str = str(key)
                            keyword_str = keyword if case_sensitive else keyword.lower()
                            search_in = key_str if case_sensitive else key_str.lower()
                            
                            if keyword_str in search_in:
                                results.append({
                                    "path": current_path,
                                    "keyword": keyword,
                                    "found_in": "key",
                                    "key": key,
                                    "value": str(value)[:200] if len(str(value)) > 200 else str(value)
                                })
                        
                        # Check value
                        if isinstance(value, str):
                            for keyword in keywords:
                                keyword_str = keyword if case_sensitive else keyword.lower()
                                search_in = value if case_sensitive else value.lower()
                                
                                if keyword_str in search_in:
                                    results.append({
                                        "path": current_path,
                                        "keyword": keyword,
                                        "found_in": "value",
                                        "key": key,
                                        "value": value[:200] if len(value) > 200 else value,
                                        "match_count": search_in.count(keyword_str)
                                    })
                        else:
                            search_recursive(value, current_path)
                
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj):
                        search_recursive(item, f"{path}[{idx}]")
                
                elif isinstance(obj, str):
                    for keyword in keywords:
                        keyword_str = keyword if case_sensitive else keyword.lower()
                        search_in = obj if case_sensitive else obj.lower()
                        
                        if keyword_str in search_in:
                            results.append({
                                "path": path,
                                "keyword": keyword,
                                "found_in": "value",
                                "value": obj[:200] if len(obj) > 200 else obj,
                                "match_count": search_in.count(keyword_str)
                            })
            
            search_recursive(data)
            
            return {
                "success": True,
                "keywords": keywords,
                "total_matches": len(results),
                "matches": results
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def filter_json(data: Any, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Filter JSON data based on conditions"""
        try:
            results = []
            
            def check_filters(obj):
                """Check if object matches all filters"""
                if not isinstance(obj, dict):
                    return False
                
                for key, value in filters.items():
                    if key not in obj:
                        return False
                    
                    obj_value = obj[key]
                    
                    # Handle different filter types
                    if isinstance(value, dict):
                        # Complex filter with operators
                        if "$gt" in value and not (obj_value > value["$gt"]):
                            return False
                        if "$lt" in value and not (obj_value < value["$lt"]):
                            return False
                        if "$gte" in value and not (obj_value >= value["$gte"]):
                            return False
                        if "$lte" in value and not (obj_value <= value["$lte"]):
                            return False
                        if "$eq" in value and obj_value != value["$eq"]:
                            return False
                        if "$ne" in value and obj_value == value["$ne"]:
                            return False
                        if "$in" in value and obj_value not in value["$in"]:
                            return False
                        if "$contains" in value and value["$contains"] not in str(obj_value):
                            return False
                    else:
                        # Simple equality filter
                        if obj_value != value:
                            return False
                
                return True
            
            def filter_recursive(obj):
                if isinstance(obj, dict):
                    if check_filters(obj):
                        results.append(obj)
                    for value in obj.values():
                        filter_recursive(value)
                elif isinstance(obj, list):
                    for item in obj:
                        filter_recursive(item)
            
            filter_recursive(data)
            
            return {
                "success": True,
                "filters_applied": filters,
                "matches_found": len(results),
                "results": results
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def aggregate_data(data: Any, field: str, operation: str = "count") -> Dict[str, Any]:
        """Aggregate data from JSON (count, sum, avg, min, max)"""
        try:
            values = []
            
            def extract_values(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == field:
                            values.append(value)
                        else:
                            extract_values(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_values(item)
            
            extract_values(data)
            
            result = {
                "success": True,
                "field": field,
                "operation": operation,
                "total_values": len(values)
            }
            
            if operation == "count":
                result["result"] = len(values)
                # Count by value
                from collections import Counter
                result["value_counts"] = dict(Counter(values))
            
            elif operation in ["sum", "avg", "min", "max"]:
                numeric_values = [v for v in values if isinstance(v, (int, float))]
                if not numeric_values:
                    return {"error": f"No numeric values found for field '{field}'"}
                
                if operation == "sum":
                    result["result"] = sum(numeric_values)
                elif operation == "avg":
                    result["result"] = sum(numeric_values) / len(numeric_values)
                elif operation == "min":
                    result["result"] = min(numeric_values)
                elif operation == "max":
                    result["result"] = max(numeric_values)
                
                result["numeric_values_count"] = len(numeric_values)
            
            else:
                return {"error": f"Unknown operation: {operation}"}
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def extract_hashtags(data: Any) -> Dict[str, Any]:
        """Extract and count hashtags from text fields in JSON data"""
        try:
            hashtags = []
            
            def find_hashtags(obj):
                if isinstance(obj, str):
                    # Find hashtags in text
                    found = re.findall(r'#(\w+)', obj)
                    hashtags.extend(found)
                elif isinstance(obj, dict):
                    for value in obj.values():
                        find_hashtags(value)
                elif isinstance(obj, list):
                    for item in obj:
                        find_hashtags(item)
            
            find_hashtags(data)
            
            from collections import Counter
            hashtag_counts = Counter(hashtags)
            
            return {
                "success": True,
                "total_hashtags": len(hashtags),
                "unique_hashtags": len(hashtag_counts),
                "top_10": hashtag_counts.most_common(10),
                "all_hashtags": dict(hashtag_counts)
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def compare_files(file1: str, file2: str) -> Dict[str, Any]:
        """Compare two JSON files and find differences"""
        try:
            with open(file1, 'r', encoding='utf-8') as f:
                data1 = json.load(f)
            with open(file2, 'r', encoding='utf-8') as f:
                data2 = json.load(f)
            
            def compare_recursive(obj1, obj2, path="root"):
                differences = []
                
                if type(obj1) != type(obj2):
                    differences.append({
                        "path": path,
                        "type": "type_mismatch",
                        "file1_type": type(obj1).__name__,
                        "file2_type": type(obj2).__name__
                    })
                    return differences
                
                if isinstance(obj1, dict):
                    all_keys = set(obj1.keys()) | set(obj2.keys())
                    for key in all_keys:
                        current_path = f"{path}.{key}"
                        if key not in obj1:
                            differences.append({
                                "path": current_path,
                                "type": "missing_in_file1",
                                "value": obj2[key]
                            })
                        elif key not in obj2:
                            differences.append({
                                "path": current_path,
                                "type": "missing_in_file2",
                                "value": obj1[key]
                            })
                        else:
                            differences.extend(compare_recursive(obj1[key], obj2[key], current_path))
                
                elif isinstance(obj1, list):
                    if len(obj1) != len(obj2):
                        differences.append({
                            "path": path,
                            "type": "length_mismatch",
                            "file1_length": len(obj1),
                            "file2_length": len(obj2)
                        })
                    for idx in range(min(len(obj1), len(obj2))):
                        differences.extend(compare_recursive(obj1[idx], obj2[idx], f"{path}[{idx}]"))
                
                else:
                    if obj1 != obj2:
                        differences.append({
                            "path": path,
                            "type": "value_mismatch",
                            "file1_value": str(obj1)[:100],
                            "file2_value": str(obj2)[:100]
                        })
                
                return differences
            
            diffs = compare_recursive(data1, data2)
            
            return {
                "success": True,
                "file1": file1,
                "file2": file2,
                "differences_count": len(diffs),
                "differences": diffs[:50]  # Limit to first 50 differences
            }
        except Exception as e:
            return {"error": str(e)}


class AIAgent:
    """AI Agent with tool calling capabilities"""
    
    def __init__(self, api_key: Optional[str] = None):
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.tools = AnalysisTools()
        self.max_iterations = 3
        self.conversation_history = []
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with descriptions"""
        return [
            {
                "name": "get_consolidated_data",
                "description": "Get consolidated Instagram/YouTube data (FAST - use this first!)",
                "parameters": {"platform": "Platform: 'instagram', 'youtube', or 'all' (default)"}
            },
            {
                "name": "get_media_summary",
                "description": "Get lightweight summary of Instagram/YouTube data (VERY FAST - quick stats)",
                "parameters": {"platform": "Platform: 'instagram', 'youtube', or 'all' (default)"}
            },
            {
                "name": "search_media_content",
                "description": "Search through Instagram/YouTube content by keywords (FAST)",
                "parameters": {
                    "query": "Search query/keyword",
                    "platform": "Platform: 'instagram', 'youtube', or 'all'",
                    "limit": "Max results (default: 20)"
                }
            },
            {
                "name": "list_json_files",
                "description": "List all JSON files in a directory with metadata (size, modified date)",
                "parameters": {"directory": "Directory path (default: current directory)"}
            },
            {
                "name": "read_json_file",
                "description": "Read and parse a JSON file, returning its contents and summary",
                "parameters": {"filename": "Path to the JSON file"}
            },
            {
                "name": "keyword_search",
                "description": "Search for keywords in JSON data recursively",
                "parameters": {
                    "data": "JSON data to search in",
                    "keywords": "List of keywords to search for",
                    "case_sensitive": "Whether to do case-sensitive search (default: False)"
                }
            },
            {
                "name": "filter_json",
                "description": "Filter JSON data based on conditions (supports $gt, $lt, $eq, $ne, $in, $contains)",
                "parameters": {
                    "data": "JSON data to filter",
                    "filters": "Dictionary of filter conditions"
                }
            },
            {
                "name": "aggregate_data",
                "description": "Aggregate data from JSON (count, sum, avg, min, max)",
                "parameters": {
                    "data": "JSON data",
                    "field": "Field name to aggregate",
                    "operation": "Operation: count, sum, avg, min, max"
                }
            },
            {
                "name": "extract_hashtags",
                "description": "Extract and count hashtags from text fields in JSON data",
                "parameters": {"data": "JSON data containing text with hashtags"}
            },
            {
                "name": "compare_files",
                "description": "Compare two JSON files and find differences",
                "parameters": {
                    "file1": "Path to first JSON file",
                    "file2": "Path to second JSON file"
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
        """Execute a tool with given parameters and retry logic"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Executing tool: {tool_name} (attempt {attempt + 1}/{max_retries})")
                
                # Validate parameters
                if not isinstance(parameters, dict):
                    return {"error": "Parameters must be a dictionary"}
                
                # Execute based on tool name
                if tool_name == "get_consolidated_data":
                    platform = parameters.get("platform", "all")
                    result = self.tools.get_consolidated_data(platform)
                
                elif tool_name == "get_media_summary":
                    platform = parameters.get("platform", "all")
                    result = self.tools.get_media_summary(platform)
                
                elif tool_name == "search_media_content":
                    query = parameters.get("query")
                    platform = parameters.get("platform", "all")
                    limit = parameters.get("limit", 20)
                    if not query:
                        return {"error": "Missing required parameter: query"}
                    result = self.tools.search_media_content(query, platform, limit)
                
                elif tool_name == "list_json_files":
                    directory = parameters.get("directory", ".")
                    result = self.tools.list_json_files(directory)
                
                elif tool_name == "read_json_file":
                    filename = parameters.get("filename")
                    if not filename:
                        return {"error": "Missing required parameter: filename"}
                    result = self.tools.read_json_file(filename)
                
                elif tool_name == "keyword_search":
                    data = parameters.get("data")
                    keywords = parameters.get("keywords")
                    case_sensitive = parameters.get("case_sensitive", False)
                    if not data or not keywords:
                        return {"error": "Missing required parameters: data, keywords"}
                    result = self.tools.keyword_search(data, keywords, case_sensitive)
                
                elif tool_name == "filter_json":
                    data = parameters.get("data")
                    filters = parameters.get("filters")
                    if not data or not filters:
                        return {"error": "Missing required parameters: data, filters"}
                    result = self.tools.filter_json(data, filters)
                
                elif tool_name == "aggregate_data":
                    data = parameters.get("data")
                    field = parameters.get("field")
                    operation = parameters.get("operation", "count")
                    if not data or not field:
                        return {"error": "Missing required parameters: data, field"}
                    result = self.tools.aggregate_data(data, field, operation)
                
                elif tool_name == "extract_hashtags":
                    data = parameters.get("data")
                    if not data:
                        return {"error": "Missing required parameter: data"}
                    result = self.tools.extract_hashtags(data)
                
                elif tool_name == "compare_files":
                    file1 = parameters.get("file1")
                    file2 = parameters.get("file2")
                    if not file1 or not file2:
                        return {"error": "Missing required parameters: file1, file2"}
                    result = self.tools.compare_files(file1, file2)
                
                else:
                    return {"error": f"Unknown tool: {tool_name}"}
                
                # Check if result has error
                if isinstance(result, dict) and "error" in result and attempt < max_retries - 1:
                    last_error = result.get("error")
                    logger.warning(f"Tool {tool_name} returned error: {last_error}, retrying...")
                    time.sleep(1.0 * (attempt + 1))
                    continue
                
                logger.info(f"Tool {tool_name} executed successfully")
                return result
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"Tool execution error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    return {
                        "error": f"Tool execution failed after {max_retries} attempts",
                        "last_error": last_error,
                        "tool": tool_name
                    }
        
        return {
            "error": f"Tool execution failed after {max_retries} attempts",
            "last_error": last_error,
            "tool": tool_name
        }
    
    async def run(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the agent with tool calling for up to 3 iterations"""
        iterations = []
        current_context = context or {}
        
        # Build system prompt with available tools
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.get_available_tools()
        ])
        
        system_prompt = f"""You are an AI agent with access to data analysis tools. You can use these tools to help answer user queries.

Available Tools:
{tools_desc}

Instructions:
1. Analyze the user's query and determine which tools would be helpful
2. Call tools by responding with JSON in this format:
   {{"action": "use_tool", "tool": "tool_name", "parameters": {{"param": "value"}}}}
3. After getting tool results, you can call more tools or provide a final answer
4. Provide a final answer by responding with:
   {{"action": "answer", "response": "your detailed answer"}}
5. You have a maximum of 3 iterations (tool calls)

Current Context: {json.dumps(current_context, indent=2)}
"""
        
        for iteration in range(self.max_iterations):
            try:
                # Build prompt for this iteration
                if iteration == 0:
                    prompt = f"{system_prompt}\n\nUser Query: {user_query}\n\nWhat would you like to do?"
                else:
                    # Include previous iteration results
                    prev_results = "\n".join([
                        f"Iteration {i+1}: Tool={it['tool']}, Result={json.dumps(it['result'], indent=2)[:500]}"
                        for i, it in enumerate(iterations)
                    ])
                    prompt = f"{system_prompt}\n\nUser Query: {user_query}\n\nPrevious Actions:\n{prev_results}\n\nWhat would you like to do next?"
                
                # Generate response from AI
                response = self.model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Try to parse as JSON
                try:
                    # Extract JSON from response (handle markdown code blocks)
                    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1)
                    elif '```' in response_text:
                        # Try to extract any code block
                        json_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                        if json_match:
                            response_text = json_match.group(1)
                    
                    action_data = json.loads(response_text)
                    
                    if action_data.get("action") == "answer":
                        # Agent is providing final answer
                        return {
                            "success": True,
                            "iterations": iterations,
                            "final_answer": action_data.get("response"),
                            "total_iterations": iteration + 1
                        }
                    
                    elif action_data.get("action") == "use_tool":
                        # Execute tool
                        tool_name = action_data.get("tool")
                        parameters = action_data.get("parameters", {})
                        
                        tool_result = self.execute_tool(tool_name, parameters)
                        
                        iterations.append({
                            "iteration": iteration + 1,
                            "tool": tool_name,
                            "parameters": parameters,
                            "result": tool_result
                        })
                
                except json.JSONDecodeError:
                    # If not valid JSON, treat as final answer
                    return {
                        "success": True,
                        "iterations": iterations,
                        "final_answer": response_text,
                        "total_iterations": iteration + 1
                    }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "iterations": iterations,
                    "iteration_failed": iteration + 1
                }
        
        # Max iterations reached, provide summary
        return {
            "success": True,
            "iterations": iterations,
            "final_answer": "Maximum iterations reached. Here's what I found:\n" + 
                           json.dumps(iterations, indent=2),
            "total_iterations": self.max_iterations
        }

