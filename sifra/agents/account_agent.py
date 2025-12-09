#!/usr/bin/env python3
"""
Account Agent - Reads account details from Freshops admin panel
"""

from crewai import Agent
from sifra.tools.account_tool import account_reader
from sifra.utils.config import Config
from sifra.utils.llm_config import LLMConfig


class AccountAgent:
    """
    Account Agent - Extracts comprehensive account information from Freshops admin panel
    """
    
    def __init__(self, config: Config):
        """
        Initialize Account Agent
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.tools = [account_reader]
        
        # Setup LLM configuration
        self.llm_config = LLMConfig(config)
        # Create proper CrewAI agent
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the CrewAI agent"""
        self.agent = Agent(
            role="Account Details Specialist",
            goal="Extract specific account information from Freshops admin panel using the provided authentication",
            backstory="""You are an expert at extracting account details from Freshworks admin panels.
            You specialize in reading account summary information, billing details, and configuration data
            from Freshops admin pages using web scraping tools.
            """,
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm_config.get_llm()
        )
