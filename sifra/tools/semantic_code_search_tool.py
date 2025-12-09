#!/usr/bin/env python3
"""
Semantic Code Search Tool - Search codebase using embeddings (like Cursor)
Much better than regex-based search for conceptual queries
"""

import json
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sifra.utils.code_rag import CodeRAG


class SemanticCodeSearchInput(BaseModel):
    """Input schema for Semantic Code Search tool."""
    query: str = Field(
        description="Natural language query (e.g., 'how to add a feature flag', 'user authentication flow', 'FreshID integration')"
    )
    top_k: int = Field(
        default=5,
        description="Number of relevant code chunks to return (default: 5 for efficiency)"
    )


class SemanticCodeSearchTool(BaseTool):
    """
    CrewAI tool for semantic code search using embeddings
    
    This tool understands MEANING, not just keywords!
    
    Examples:
    - "how to add a feature flag" → finds temp_features.yml, account_features.rb, erm.yml
    - "user authentication" → finds auth controllers, FreshID integration, session management
    - "email sending logic" → finds mailers, email services, SMTP config
    
    Much better than regex for conceptual queries!
    """
    
    name: str = "semantic_code_search"
    description: str = """Search codebase using semantic understanding (like Cursor AI).
    
    Use this for:
    - Conceptual queries: "how to implement X", "where is Y handled"
    - Finding patterns: "authentication flow", "database transactions"
    - Discovering related code: "feature flag system", "API endpoints"
    
    This tool understands MEANING, not just keywords!
    Much better than regex search for "how-to" questions.
    
    Returns relevant code chunks with file paths and line numbers.
    """
    args_schema: Type[BaseModel] = SemanticCodeSearchInput
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        # Initialize Code RAG system
        from sifra.utils.config import Config
        config = Config()
        object.__setattr__(self, 'code_rag', CodeRAG(config))
    
    def _run(self, query: str, top_k: int = 5) -> str:
        """Semantic search using embeddings"""
        
        if not query:
            return json.dumps({"error": "No search query provided"})
        
        print(f"🧠 Semantic search: '{query}' (top {top_k} results)")
        
        try:
            # Check if indexed
            if self.code_rag.collection.count() == 0:
                return json.dumps({
                    "error": "Codebase not indexed yet",
                    "message": "Run: python -m sifra.utils.code_rag to index codebase first",
                    "query": query
                })
            
            # Query using semantic search
            results = self.code_rag.query(query, top_k=top_k)
            
            if not results:
                return json.dumps({
                    "query": query,
                    "found": 0,
                    "message": "No semantically similar code found"
                })
            
            # Format for LLM
            formatted_results = {
                "query": query,
                "found": len(results),
                "search_type": "semantic_embedding",
                "matches": []
            }
            
            for result in results:
                meta = result['metadata']
                # Return FULL code snippets for better context (don't truncate)
                code_text = result['text']
                formatted_results['matches'].append({
                    "file": meta['file'],
                    "start_line": meta['start_line'],
                    "end_line": meta['end_line'],
                    "name": meta.get('name', ''),
                    "type": meta.get('type', ''),
                    "relevance_score": 1.0 - result.get('distance', 0),  # Convert distance to score
                    "code_snippet": code_text,  # Full snippet for comprehensive answers
                    "snippet_length": len(code_text)
                })
            
            return json.dumps(formatted_results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Semantic search failed: {str(e)}",
                "query": query
            })


# Create instance for easy import
semantic_code_searcher = SemanticCodeSearchTool()

