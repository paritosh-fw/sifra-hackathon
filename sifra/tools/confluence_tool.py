#!/usr/bin/env python3
"""
Confluence RAG Tool for CrewAI
Allows agents to query Confluence documentation using RAG
"""

from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class ConfluenceQueryInput(BaseModel):
    """Input schema for Confluence query tool"""
    question: str = Field(description="Question to search in Confluence documentation")


class ConfluenceQueryTool(BaseTool):
    """
    Tool for querying Confluence documentation using RAG
    
    This tool searches pre-indexed Confluence pages and returns relevant context
    """
    
    name: str = "confluence_search"
    description: str = """Search Confluence documentation using semantic search.
    Retrieves relevant documentation chunks based on your question.
    Use this when you need information from internal documentation, guides, or knowledge base.
    
    Example: "How do we handle authentication in Freshservice?"
    """
    args_schema: Type[BaseModel] = ConfluenceQueryInput
    
    def _run(self, question: str) -> str:
        """Query Confluence documentation"""
        try:
            from sifra.utils.config import Config
            
            print(f"\n🔍 Searching Confluence for: {question}")
            
            # Lazy import to avoid initialization issues
            try:
                from sifra.utils.confluence_rag import ConfluenceRAG
            except ImportError as ie:
                return f"""❌ Confluence RAG dependencies not installed: {str(ie)}
                
Please install: pip install chromadb sentence-transformers
"""
            
            # Initialize RAG system
            config = Config()
            rag = ConfluenceRAG(config)
            
            # Check if documents are indexed
            if rag.collection.count() == 0:
                return """⚠️  Confluence knowledge base not indexed yet.
                
Please run the indexing script first:
    python -m sifra.utils.confluence_rag

Or use the index command:
    sifra-adv index-confluence
"""
            
            # Get context
            context = rag.get_context_for_llm(question, top_k=5)
            
            return f"""
📚 Confluence Documentation Results:

{context}

Note: Use this context to answer the question. Always cite the source URLs when providing information.
"""
            
        except ImportError as e:
            return f"""❌ Missing dependencies. Please install:
    pip install chromadb sentence-transformers

Error: {str(e)}
"""
        except Exception as e:
            return f"❌ Error searching Confluence: {str(e)}"


# Create instance for easy import
confluence_query_tool = ConfluenceQueryTool()

