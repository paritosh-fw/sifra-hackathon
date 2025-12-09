#!/usr/bin/env python3
"""
Query Picker Agent - Listens to Slack and picks queries/ticket IDs
"""

from crewai import Agent
from sifra.tools.slack_tool import slack_reader
from sifra.utils.llm_config import LLMConfig


class QueryPicker:
    """
    Query Picker Agent - Listens to Slack channel and picks tasks
    """
    
    def __init__(self, config):
        """
        Initialize Query Picker agent
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.tools = [slack_reader]
        
        # Setup LLM configuration
        self.llm_config = LLMConfig(config)
        # Create proper CrewAI agent
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the CrewAI agent"""
        self.agent = Agent(
            role="Query pick agent",
            goal="Pick query or ticket ids to investigate",
            backstory="It's keep listening the slack channel and pick the task provided",
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm_config.get_llm()
        )
