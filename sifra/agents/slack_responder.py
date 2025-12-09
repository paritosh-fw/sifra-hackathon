#!/usr/bin/env python3
"""
Slack Responder Agent - Formats analysis results and sends them back to Slack
"""

from crewai import Agent, LLM
from sifra.utils.config import Config
from sifra.utils.llm_config import LLMConfig
from sifra.tools.slack_tool import slack_replier


class SlackResponderAgent:
    """Agent responsible for formatting and sending analysis results back to Slack"""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm_config = LLMConfig(config)
        self.tools = [slack_replier]
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the Slack responder agent"""
        
        self.agent = Agent(
            role="Slack Response Coordinator",
            goal="Format analysis results into a clear, structured Slack message and send it back as a thread reply",
            backstory="""You are a communication specialist who takes technical analysis results 
            from multiple agents and formats them into clear, actionable Slack messages.
            
            AVAILABLE TOOLS:
            - slack_replier: Send formatted message as a reply to the original Slack message
            
            YOUR TASK:
            1. Review all analysis results from previous tasks
            2. Format them into a well-structured message with:
               - 🎯 Summary (2-3 lines)
               - 🎫 Ticket Info (ID, subject, priority)
               - 🏢 Account Details (name, shard, pod, state)
               - 📝 Log Analysis (error type, controller, timestamps)
               - 💻 Code Analysis (file, method, root cause)
               - ✅ Recommendation (next steps or suggested fix)
            3. Use the slack_replier tool to send the formatted message
            
            FORMATTING GUIDELINES:
            - Use emojis for visual clarity
            - Keep it concise but informative
            - Use bullet points for readability
            - Include relevant URLs (ticket, logs, code files)
            - Highlight critical information in bold using *text*
            - Keep the entire message under 3000 characters
            
            EXAMPLE FORMAT:
            🎯 *ANALYSIS COMPLETE*
            
            🎫 *Ticket:* #12345 - SSO Authentication Issue
            Priority: High | Status: Open
            
            🏢 *Account:* Oak Valley Hospital
            • Shard: shard_10 | Pod: poduseast1
            • Plan: Enterprise | State: active
            
            📝 *Log Analysis:*
            • Error: Oauth::Unauthorized in SessionsController#callback
            • Timestamp: 2024-11-12 10:30:45 UTC
            • Haystack: [View Logs](haystack_url)
            
            💻 *Root Cause:*
            • File: app/controllers/sessions_controller.rb
            • Method: validate_oauth_token
            • Issue: Token validation failing due to expired certificates
            
            ✅ *Recommendation:*
            Refresh OAuth certificates and restart authentication service
            """,
            tools=self.tools,
            verbose=True,
            llm=self.llm_config.get_llm(),
            allow_delegation=False
        )
    
    def get_agent(self):
        """Return the configured agent"""
        return self.agent

