#!/usr/bin/env python3
"""
Haystack Search Tool - Uses extracted parameters to search logs using Haystack class
"""

import json
import re
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sifra.utils.haystack import Haystack


class HaystackSearchInput(BaseModel):
    """Input schema for Haystack search tool."""
    pod: str = Field(description="Pod/region (us/in/eu/au)")
    product: str = Field(description="Product (e.g., freshservice*)")
    query_string: str = Field(description="Search query string")
    timestamp_gte: str = Field(description="Start timestamp in ISO format")
    timestamp_lte: str = Field(description="End timestamp in ISO format")


class HaystackSearchTool(BaseTool):
    """Tool for searching Haystack logs using extracted parameters"""
    
    name: str = "haystack_search"
    description: str = "Search Haystack logs using extracted parameters from ticket analysis"
    args_schema: Type[BaseModel] = HaystackSearchInput
    
    def _run(self, pod: str, product: str, query_string: str, 
             timestamp_gte: str, timestamp_lte: str) -> str:
        """Search Haystack logs using the provided parameters"""
        
        try:
            # Load configuration
            from sifra.utils.config import Config
            config = Config()
            
            # Get email from config
            email = config.haystack.get('default_user_email', 'paritosh.agarwal@freshworks.com')
            
            print(f"🔍 Searching Haystack logs...")
            print(f"📍 Pod: {pod}")
            print(f"📧 Email: {email} (from config)")
            print(f"🏷️ Product: {product}")
            print(f"🔍 Query: {query_string}")
            print(f"⏰ Time Range: {timestamp_gte} to {timestamp_lte}")
            
            # Create Haystack instance with extracted parameters
            haystack_obj = Haystack(
                pod=pod,
                email=email,
                product=product,
                query_string=query_string,
                timestamp_gte=timestamp_gte,
                timestamp_lte=timestamp_lte,
                config=config
            )
            
            # Get logs from Haystack
            logs = haystack_obj.get_logs()
            
            # Check if we got logs or if there was an authentication issue
            if len(logs) == 0:
                # Check if this was due to authentication failure
                print("⚠️  No logs returned - this could be due to:")
                print("   1. No matching logs found for the search criteria")
                print("   2. Authentication failure (expired cookies)")
                print("   3. Network connectivity issues")
            
            # Format results
            result = {
                "status": "success" if len(logs) > 0 else "no_results",
                "search_parameters": {
                    "pod": pod,
                    "email": email,
                    "product": product,
                    "query_string": query_string,
                    "timestamp_gte": timestamp_gte,
                    "timestamp_lte": timestamp_lte
                },
                "total_logs": len(logs),
                "logs": logs[:10] if logs else [],  # Return first 10 logs
                "message": f"Found {len(logs)} log entries" if len(logs) > 0 else "No logs found - check authentication or search criteria"
            }
            
            print(f"✅ Found {len(logs)} log entries")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            # Load config for error reporting
            from sifra.utils.config import Config
            config = Config()
            email = config.haystack.get('default_user_email', 'paritosh.agarwal@freshworks.com')
            
            error_result = {
                "status": "error",
                "message": f"Failed to search Haystack logs: {str(e)}",
                "search_parameters": {
                    "pod": pod,
                    "email": email,
                    "product": product,
                    "query_string": query_string,
                    "timestamp_gte": timestamp_gte,
                    "timestamp_lte": timestamp_lte
                }
            }
            print(f"❌ Error: {str(e)}")
            return json.dumps(error_result, indent=2)


# Create instance for easy import
haystack_search = HaystackSearchTool()
