#!/usr/bin/env python3
"""
HAR Parser Tool - Reads and analyzes HAR (HTTP Archive) files (FALLBACK for when no Haystack URL available)
"""

from crewai.tools import BaseTool
from typing import Type, Optional, List
from pydantic import BaseModel, Field
import json
import re
import os


class HARParserInput(BaseModel):
    """Input schema for HAR Parser"""
    file_path: str = Field(description="Path to HAR file (can be from ticket attachments)")
    extract_uuids: bool = Field(default=True, description="Whether to extract UUIDs/correlation IDs")
    find_errors: bool = Field(default=True, description="Whether to focus on failed requests (4xx, 5xx)")


class HARParserTool(BaseTool):
    name: str = "har_parser"
    description: str = """
    Parse HAR (HTTP Archive) files to extract failed requests and UUIDs for log analysis.
    
    **USE WHENEVER HAR file is attached to ticket** - provides valuable UUIDs and context
    
    Use this when:
    - HAR file (.har) is attached to ticket
    - Can be used alongside Haystack URL for additional correlation IDs
    - Especially useful for authentication/login issues
    
    Input:
    - file_path: Path to .har file
    
    Output:
    - Failed request UUIDs for Haystack search
    - Can be combined with Haystack URL data for comprehensive analysis
    """
    args_schema: Type[BaseModel] = HARParserInput
    
    def _run(self, file_path: str, extract_uuids: bool = True, find_errors: bool = True) -> str:
        """Parse HAR file and extract UUIDs and timestamps from failed requests"""
        try:
            # If file_path is just a filename, look in project root
            if not os.path.exists(file_path) and not os.path.isabs(file_path):
                # Try project root
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                alternate_path = os.path.join(project_root, file_path)
                if os.path.exists(alternate_path):
                    file_path = alternate_path
                    print(f"📁 Found HAR file in project root: {file_path}")
                else:
                    return f"❌ HAR file not found: {file_path} (also checked {alternate_path})"
            
            if not os.path.exists(file_path):
                return f"❌ HAR file not found: {file_path}"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                har_data = json.load(f)
            
            if 'log' not in har_data:
                return "❌ Invalid HAR file format"
            
            entries = har_data['log'].get('entries', [])
            
            if not entries:
                return "⚠️ HAR file has no entries"
            
            # Filter failed requests
            if find_errors:
                failed_requests = [e for e in entries if e['response']['status'] >= 400]
            else:
                failed_requests = entries
            
            if not failed_requests:
                return f"✅ HAR analyzed: {len(entries)} requests, 0 failures"
            
            # Extract UUIDs and timestamps
            extracted_uuids = set()
            timestamps = []
            
            for entry in failed_requests[:10]:  # Limit to first 10
                request = entry['request']
                response = entry['response']
                
                # Extract timestamp
                started_dt = entry.get('startedDateTime', '')
                if started_dt:
                    timestamps.append(started_dt)
                
                if extract_uuids:
                    # From URL
                    extracted_uuids.update(self._extract_uuids(request['url']))
                    
                    # From headers
                    for header in request.get('headers', []) + response.get('headers', []):
                        if any(k in header['name'].lower() for k in ['correlation', 'request-id', 'trace']):
                            extracted_uuids.update(self._extract_uuids(header['value']))
                    
                    # From response body
                    response_content = response.get('content', {}).get('text', '')
                    if response_content:
                        extracted_uuids.update(self._extract_uuids(response_content[:1000]))
            
            if not extracted_uuids:
                return "⚠️ No UUIDs found in failed requests"
            
            # Calculate time range
            time_range_info = ""
            if timestamps:
                earliest = min(timestamps)
                latest = max(timestamps)
                time_range_info = f"\n⏰ TIME RANGE FROM HAR:\n"
                time_range_info += f"   Earliest failure: {earliest}\n"
                time_range_info += f"   Latest failure: {latest}\n"
                time_range_info += f"   💡 Use these for timestamp_gte and timestamp_lte (add ±30 min buffer)\n"
            
            # Format output
            output = f"✅ HAR FILE PARSED:\n\n"
            output += f"- Total Requests: {len(entries)}\n"
            output += f"- Failed Requests: {len(failed_requests)}\n"
            output += f"- UUIDs Found: {len(extracted_uuids)}\n"
            output += time_range_info
            output += f"\n🔍 EXTRACTED UUIDs FOR HAYSTACK SEARCH:\n"
            
            for uuid in list(extracted_uuids)[:5]:  # Show first 5
                output += f"   • {uuid}\n"
            
            output += f"\n💡 Use these UUIDs in query_string for haystack_search\n"
            
            return output
            
        except Exception as e:
            return f"❌ Error parsing HAR: {str(e)}"
    
    def _extract_uuids(self, text: str) -> set:
        """Extract UUID patterns from text"""
        uuids = set()
        
        # Standard UUID pattern (8-4-4-4-12)
        uuid_pattern = r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'
        uuids.update(re.findall(uuid_pattern, text, re.IGNORECASE))
        
        return uuids


# Create the tool instance
har_parser = HARParserTool()

