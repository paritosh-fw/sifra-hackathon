#!/usr/bin/env python3
"""
LLM Configuration for Sifra Advanced
"""

import os
from crewai import LLM


class LLMConfig:
    """
    LLM Configuration class for Cloudverse
    """
    
    def __init__(self, config):
        """Initialize LLM config with Cloudverse settings"""
        self.config = config
        self.llm = self._setup_cloudverse_llm()
    
    def _setup_cloudverse_llm(self):
        """Setup Cloudverse LLM for CrewAI"""
        llm_config = self.config.llm
        
        # Set environment variables for CrewAI
        os.environ["OPENAI_API_KEY"] = llm_config.get('api_key', '')
        os.environ["OPENAI_API_BASE"] = llm_config.get('base_url', '')
        
        # Get token limits from config (with sensible defaults)
        max_tokens = llm_config.get('max_tokens', 8192)  # Response length
        temperature = llm_config.get('temperature', 0.7)  # Creativity
        
        # Create LLM instance with configured limits
        llm = LLM(
            model=f"openai/{llm_config.get('model', 'anthropic-claude-3-5-sonnet-v2')}",
            base_url=llm_config.get('base_url', ''),
            api_key=llm_config.get('api_key', ''),
            max_tokens=max_tokens,  # Read from config (8192 for Claude 3.5 Sonnet)
            temperature=temperature
        )
        
        print(f"✅ LLM configured: {llm_config.get('model')} (max_tokens={max_tokens})")
        
        return llm
    
    def get_llm(self):
        """Get the configured LLM instance"""
        return self.llm
