#!/usr/bin/env python3
"""
Code Search Tool - Search codebase for specific code patterns, methods, and files
"""

import os
import re
import json
from typing import Type, List, Dict
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class CodeSearchInput(BaseModel):
    """Input schema for Code Search tool."""
    query: str = Field(description="Search query (method name, class name, keyword, or pattern)")
    file_pattern: str = Field(default="*.rb", description="File pattern to search (e.g., *.rb, *.py)")
    max_results: int = Field(default=10, description="Maximum number of results to return")


class CodeSearchTool(BaseTool):
    """CrewAI tool for searching codebase"""
    
    name: str = "code_searcher"
    description: str = """Search the codebase for methods, classes, patterns, or keywords.
    
    Use this tool to:
    - Find where a method is defined: "create_agent"
    - Find where a class is used: "AgentService"
    - Search for patterns: "freshid_client.update"
    - Find API endpoints: "api/v2/agents"
    
    Returns file paths, line numbers, and code snippets.
    """
    args_schema: Type[BaseModel] = CodeSearchInput
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        # Path to codebase (use object.__setattr__ for Pydantic compatibility)
        object.__setattr__(self, 'codebase_path', "/Users/paritoshagarwal/code/itildesk_2")
    
    def _run(self, query: str, file_pattern: str = "*.rb", max_results: int = 10) -> str:
        """Search codebase for the given query"""
        
        if not query:
            return json.dumps({"error": "No search query provided"})
        
        print(f"🔍 Searching codebase for: '{query}' in {file_pattern} files...")
        
        try:
            results = self._search_files(query, file_pattern, max_results)
            
            if not results:
                return json.dumps({
                    "query": query,
                    "found": 0,
                    "message": f"No matches found for '{query}' in {file_pattern} files"
                })
            
            # Format results for LLM
            formatted_results = {
                "query": query,
                "found": len(results),
                "matches": results
            }
            
            return json.dumps(formatted_results, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Search failed: {str(e)}"})
    
    def _search_files(self, query: str, file_pattern: str, max_results: int) -> List[Dict]:
        """Search files in codebase directory"""
        results = []
        file_count = 0
        
        # Convert file pattern to regex
        # Supports: "*.rb", "app/**/*.rb", "**/agents_*.rb"
        pattern_regex = (file_pattern
                        .replace(".", r"\.")      # Escape dots
                        .replace("**", "___DOUBLESTAR___")  # Temp marker for **
                        .replace("*", "[^/]*")    # * matches anything except /
                        .replace("___DOUBLESTAR___", ".*")  # ** matches anything including /
                        )
        
        # Add anchors for full match
        # If pattern doesn't start with **, add line start anchor
        if not file_pattern.startswith("**") and not pattern_regex.startswith(".*"):
            # For patterns like "*.rb" or "app/**/*.rb", match from start or with path
            if "/" not in file_pattern.split("**")[0]:  # Simple pattern like "*.rb"
                pattern_regex = "(^|.*/)" + pattern_regex  # Match from start or after /
            else:
                pattern_regex = "^" + pattern_regex
        
        # Always anchor at end for exact extension match
        if not pattern_regex.endswith(".*"):
            pattern_regex = pattern_regex + "$"
        
        # Walk through codebase
        for root, dirs, files in os.walk(self.codebase_path):
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'tmp', 'log', 'coverage', '__pycache__']]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Get relative path from codebase root
                rel_path = os.path.relpath(file_path, self.codebase_path)
                
                # Match against relative path (supports path patterns like "app/**/*.rb")
                if not re.match(pattern_regex, rel_path):
                    continue
                
                file_count += 1
                
                # Search within file
                matches = self._search_in_file(file_path, query)
                if matches:
                    results.extend(matches)
                
                # Stop if we have enough results
                if len(results) >= max_results:
                    break
            
            if len(results) >= max_results:
                break
        
        print(f"  Searched {file_count} files, found {len(results)} matches")
        return results[:max_results]
    
    def _search_in_file(self, file_path: str, query: str) -> List[Dict]:
        """Search for query in a single file"""
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
                for line_num, line in enumerate(lines, start=1):
                    # Check if query appears in line (case-insensitive)
                    if re.search(re.escape(query), line, re.IGNORECASE):
                        # Get context (2 lines before and after)
                        context_start = max(0, line_num - 3)
                        context_end = min(len(lines), line_num + 2)
                        context_lines = lines[context_start:context_end]
                        
                        # Get relative path from codebase root
                        rel_path = os.path.relpath(file_path, self.codebase_path)
                        
                        matches.append({
                            "file": rel_path,
                            "line": line_num,
                            "match": line.strip(),
                            "context": "".join(context_lines)
                        })
        
        except Exception as e:
            # Skip files that can't be read
            pass
        
        return matches


# Create instance for easy import
code_searcher = CodeSearchTool()

