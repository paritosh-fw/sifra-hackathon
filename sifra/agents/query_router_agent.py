#!/usr/bin/env python3
"""
Query Router Agent - Routes incoming Slack messages to appropriate workflow
Determines if message is a ticket URL or a code query
"""

from crewai import Agent
from sifra.utils.config import Config
from sifra.utils.llm_config import LLMConfig
import re


class QueryRouterAgent:
    """Agent responsible for routing queries to ticket analysis or code assistant workflow"""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm_config = LLMConfig(config)
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the query router agent"""
        
        self.agent = Agent(
            role="Query Router",
            goal="Analyze incoming Slack messages and route them to the appropriate workflow (ticket analysis or code assistant)",
            backstory="""You are the intelligent routing system for Sifra Advanced. Your job is to 
            quickly analyze incoming queries and determine whether they are:
            
            1. **Ticket Analysis Request**: Contains a Freshdesk ticket URL that needs investigation
            2. **Code Query**: A question about codebase, asking for code changes, or debugging help
            
            You are very good at pattern recognition and can distinguish between these types instantly.
            
            TICKET URL PATTERNS:
            - Contains: freshdesk.com/a/tickets/
            - Contains: freshservice.com/a/tickets/
            - Example: "https://support.freshdesk.com/a/tickets/19188757"
            
            CODE QUERY PATTERNS:
            - Questions about code flow: "explain code flow of X"
            - Questions about code location: "where are we calling X"
            - Feature implementation: "how to add X feature"
            - Error debugging: stack traces, error messages
            - Code change requests: "what changes needed for X"
            
            You respond with either:
            - "TICKET_ANALYSIS" if it's a ticket URL
            - "CODE_QUERY" if it's a code-related question
            - "UNKNOWN" if unclear (default to CODE_QUERY if @sifra mentioned)
            """,
            verbose=True,
            llm=self.llm_config.get_llm(),
            allow_delegation=False
        )
    
    def get_agent(self):
        """Return the configured agent"""
        return self.agent
    
    @staticmethod
    def quick_route(query_text: str) -> str:
        """
        Quick routing without LLM (faster for obvious cases)
        
        Returns:
            "TICKET_ANALYSIS" or "CODE_QUERY"
        """
        # Check for ticket URL patterns
        ticket_url_patterns = [
            r'freshdesk\.com/a/tickets/\d+',
            r'freshservice\.com/a/tickets/\d+',
        ]
        
        for pattern in ticket_url_patterns:
            if re.search(pattern, query_text, re.IGNORECASE):
                print("📋 Quick route: TICKET_ANALYSIS (URL detected)")
                return "TICKET_ANALYSIS"
        
        # If no ticket URL found, it's a code query
        print("💻 Quick route: CODE_QUERY")
        return "CODE_QUERY"

