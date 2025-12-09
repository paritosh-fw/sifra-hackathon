#!/usr/bin/env python3
"""
Haystack URL Detector Tool - Detects and extracts parameters from Haystack URLs in tickets
"""

import re
from typing import Type, Optional, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sifra.utils.haystack_url_parser import HaystackURLParser

class HaystackURLDetectorInput(BaseModel):
    """Input schema for Haystack URL detector tool."""
    ticket_content: str = Field(description="Complete ticket content including description, comments, and attachments")

class HaystackURLDetectorTool(BaseTool):
    """Tool for detecting and extracting Haystack URLs from ticket content"""
    
    name: str = "haystack_url_detector"
    description: str = "Detect Haystack URLs in ticket content and extract search parameters"
    args_schema: Type[BaseModel] = HaystackURLDetectorInput
    
    def __init__(self):
        super().__init__()
        # Initialize parser and patterns as instance variables
        object.__setattr__(self, 'parser', HaystackURLParser())
        object.__setattr__(self, 'haystack_url_patterns', [
            r'https://logs\.haystack\.es/goto/[a-f0-9]+',
            r'https://logs-in\.haystack\.es/goto/[a-f0-9]+',
            r'https://logs-euc\.haystack\.es/goto/[a-f0-9]+',
            r'https://logs-au\.haystack\.es/goto/[a-f0-9]+',
            r'https://logs\.haystack\.es/app/discover[^\s]*',
            r'https://logs-in\.haystack\.es/app/discover[^\s]*',
            r'https://logs-euc\.haystack\.es/app/discover[^\s]*',
            r'https://logs-au\.haystack\.es/app/discover[^\s]*'
        ])
    
    def _run(self, ticket_content: str) -> str:
        """Detect Haystack URLs in ticket content and extract parameters"""
        
        try:
            print("🔍 Scanning ticket content for Haystack URLs...")
            
            # Find all Haystack URLs in the ticket content
            haystack_urls = self._find_haystack_urls(ticket_content)
            
            if not haystack_urls:
                print("❌ No Haystack URLs found in ticket content")
                return self._create_no_urls_result()
            
            print(f"✅ Found {len(haystack_urls)} Haystack URL(s)")
            
            # Parse each URL and extract parameters
            parsed_urls = []
            for i, url in enumerate(haystack_urls, 1):
                print(f"\n🔍 Parsing URL {i}: {url[:100]}...")
                parsed_params = self.parser.parse_haystack_url(url, debug=False)
                
                
                if parsed_params and parsed_params.get('query_string') and parsed_params.get('timestamp_gte'):
                    parsed_urls.append({
                        "url": url,
                        "parameters": parsed_params,
                        "status": "success"
                    })
                    print(f"✅ Successfully parsed URL {i}")
                else:
                    parsed_urls.append({
                        "url": url,
                        "parameters": parsed_params,
                        "status": "failed"
                    })
                    print(f"❌ Failed to parse URL {i} - missing required parameters")
            
            # Create result
            result = {
                "status": "success",
                "total_urls": len(haystack_urls),
                "parsed_urls": parsed_urls,
                "recommendation": self._get_recommendation(parsed_urls)
            }
            
            return self._format_result(result)
            
        except Exception as e:
            error_result = {
                "status": "error",
                "message": f"Failed to detect Haystack URLs: {str(e)}",
                "total_urls": 0,
                "parsed_urls": []
            }
            print(f"❌ Error: {str(e)}")
            return self._format_result(error_result)
    
    def _find_haystack_urls(self, content: str) -> list:
        """Find all Haystack URLs in the content"""
        urls = []
        
        for pattern in self.haystack_url_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            urls.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _create_no_urls_result(self) -> str:
        """Create result when no URLs are found"""
        result = {
            "status": "no_urls",
            "message": "No Haystack URLs found in ticket content",
            "total_urls": 0,
            "parsed_urls": [],
            "recommendation": "Use manual search term extraction from ticket description"
        }
        return self._format_result(result)
    
    def _get_recommendation(self, parsed_urls: list) -> str:
        """Get recommendation based on parsed URLs"""
        successful_parses = [url for url in parsed_urls if url["status"] == "success"]
        
        if not successful_parses:
            return "No valid Haystack URLs found. Use manual search term extraction."
        elif len(successful_parses) == 1:
            return "Use the extracted parameters from the Haystack URL for direct log search."
        else:
            return f"Multiple Haystack URLs found. Use the most recent or relevant one for log search."
    
    def _format_result(self, result: dict) -> str:
        """Format the result as JSON string"""
        import json
        return json.dumps(result, indent=2)

# Create instance for easy import
haystack_url_detector = HaystackURLDetectorTool()
