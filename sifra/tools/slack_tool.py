#!/usr/bin/env python3
"""
Slack Tool - CrewAI compatible tool for reading messages from Slack channels
"""

import requests
import json
import re
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

from sifra.utils.config import load_config


# Global variables to store message metadata for threading and routing
_last_message_ts = None
_last_message_full_text = None  # Store full message for context
_is_sifra_mention = False  # Flag to indicate @sifra mention

# Load config once
_config = load_config()
_slack_config = _config.get('slack', {})


class SlackReaderInput(BaseModel):
    """Input schema for Slack reader tool."""
    query: str = Field(default="", description="Optional query parameter (not used)")


class SlackReaderTool(BaseTool):
    """CrewAI compatible tool for reading messages from Slack channels"""
    
    name: str = "slack_reader"
    description: str = "Read the last message from Slack channel to pick queries and ticket IDs"
    args_schema: Type[BaseModel] = SlackReaderInput
    
    def _run(self, query: str = "") -> str:
        """Read the last message from Slack channel to pick queries and ticket IDs"""
        global _last_message_ts, _last_message_full_text, _is_sifra_mention
        
        # Read from config
        bot_token = _slack_config.get('bot_token', '')
        channel_id = _slack_config.get('channel_id', '')
        
        if not bot_token or not channel_id:
            return "Error: Slack configuration missing in config.yaml"
        
        try:
            url = "https://slack.com/api/conversations.history"
            headers = {'Authorization': f'Bearer {bot_token}'}
            params = {'channel': channel_id, 'limit': 1}
            
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            
            if data.get('ok') and data.get('messages'):
                message = data['messages'][0]
                message_text = message['text']
                
                # Store timestamp for threading
                _last_message_ts = message.get('ts')
                _last_message_full_text = message_text
                
                # Check for @sifra mention (handles both <@U...> format and @sifra text)
                # Slack formats mentions as <@USER_ID> or sometimes plain @sifra
                sifra_mention_patterns = [
                    r'<@U\w+>',  # <@U12345678> format
                    r'@sifra',    # Plain @sifra text
                ]
                
                _is_sifra_mention = any(re.search(pattern, message_text, re.IGNORECASE) for pattern in sifra_mention_patterns)
                
                # Remove @sifra mention from the query text for cleaner processing
                clean_text = message_text
                for pattern in sifra_mention_patterns:
                    clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
                clean_text = clean_text.strip()
                
                if _is_sifra_mention:
                    print(f"🤖 @sifra mention detected! Query: {clean_text}")
                
                return clean_text
            else:
                return "No message found"
                
        except Exception as e:
            return f"Error reading Slack: {str(e)}"


class SlackReplyInput(BaseModel):
    """Input schema for Slack reply tool."""
    message: str = Field(description="Message to send as a reply to the original Slack message")


class SlackReplyTool(BaseTool):
    """CrewAI compatible tool for sending replies to Slack messages"""
    
    name: str = "slack_replier"
    description: str = "Send a reply to the original Slack message as a thread reply with analysis results"
    args_schema: Type[BaseModel] = SlackReplyInput
    
    def _run(self, message: str) -> str:
        """Send a reply to the original Slack message"""
        global _last_message_ts
        
        # Read from config
        bot_token = _slack_config.get('bot_token', '')
        channel_id = _slack_config.get('channel_id', '')
        
        if not bot_token or not channel_id:
            return "❌ Error: Slack configuration missing in config.yaml"
        
        if not _last_message_ts:
            return "❌ Error: No message timestamp found. Cannot reply to thread."
        
        try:
            url = "https://slack.com/api/chat.postMessage"
            headers = {
                'Authorization': f'Bearer {bot_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'channel': channel_id,
                'text': message,
                'thread_ts': _last_message_ts  # Reply in thread
            }
            
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
            
            if data.get('ok'):
                print("✅ Successfully sent reply to Slack thread")
                return "✅ Reply sent successfully to Slack thread"
            else:
                error_msg = data.get('error', 'Unknown error')
                print(f"❌ Failed to send Slack reply: {error_msg}")
                return f"❌ Failed to send reply: {error_msg}"
                
        except Exception as e:
            return f"❌ Error sending Slack reply: {str(e)}"


# Create instances for easy import
slack_reader = SlackReaderTool()
slack_replier = SlackReplyTool()


# Helper function to check if last message was a @sifra mention
def is_sifra_mention() -> bool:
    """Check if the last Slack message was a @sifra mention"""
    global _is_sifra_mention
    return _is_sifra_mention


def get_full_message_text() -> str:
    """Get the full unprocessed message text"""
    global _last_message_full_text
    return _last_message_full_text or ""
