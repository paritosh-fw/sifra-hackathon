#!/usr/bin/env python3
"""
Simplified Freshdesk Tool - Session Cookie Only (Hackathon Version)
Removes complexity of strategies that don't work on support.freshdesk.com
"""

import requests
import base64
import json
import re
import os
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FreshdeskInput(BaseModel):
    """Input schema for Freshdesk tool."""
    ticket_url: str = Field(description="Freshdesk ticket URL to analyze")


class SimpleFreshdeskTool(BaseTool):
    """Simple tool that fetches raw ticket data - agent handles all analysis"""
    
    name: str = "freshdesk_reader"
    description: str = "Fetch complete raw ticket data including description, conversations, and attachments"
    args_schema: Type[BaseModel] = FreshdeskInput
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        
        # Simple configuration using object.__setattr__ for Pydantic compatibility
        object.__setattr__(self, 'api_key', "_FjddtQ1jnPP7JVpIOjS")
        object.__setattr__(self, 'domain', "support")
        object.__setattr__(self, 'base_url', f"https://{self.domain}.freshdesk.com/api/v2")
        
        # Load session cookie from config
        try:
            from ..utils.config import get_config
            config = get_config()
            session_cookie = config.get('freshdesk', {}).get('session_cookie', '')
            object.__setattr__(self, 'session_cookie', session_cookie)
        except:
            object.__setattr__(self, 'session_cookie', '')
    
    def _run(self, ticket_url: str) -> str:
        """Fetch raw ticket data and return as JSON"""
        print(f"📋 Fetching ticket data: {ticket_url}")
        
        try:
            # Extract ticket ID
            ticket_id = self._extract_ticket_id(ticket_url)
            if not ticket_id:
                return json.dumps({"error": "Could not extract ticket ID from URL"})
            
            # Fetch all raw data
            ticket_data = self._fetch_ticket_details(ticket_id)
            conversations = self._fetch_conversations(ticket_id)
            
            # Download HAR file attachments if present
            downloaded_files = {}
            attachments = ticket_data.get('attachments', [])
            if attachments:
                downloaded_files = self._download_har_attachments(ticket_id, attachments)
            
            # Return complete raw data as JSON
            complete_data = {
                "ticket_id": ticket_id,
                "ticket_url": ticket_url,
                "ticket_details": ticket_data,
                "conversations": conversations,
                "downloaded_attachments": downloaded_files,
                "status": "success"
            }
            
            print(f"✅ Successfully fetched ticket {ticket_id}")
            if downloaded_files:
                print(f"📎 Downloaded {len(downloaded_files)} HAR file(s): {list(downloaded_files.keys())}")
            return json.dumps(complete_data, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch ticket data: {str(e)}"})
    
    def _extract_ticket_id(self, url: str) -> str:
        """Extract ticket ID from URL using simple regex"""
        # Pattern: /tickets/12345 or /a/tickets/12345
        pattern = r'/(?:a/)?tickets/(\d+)'
        match = re.search(pattern, url)
        return match.group(1) if match else None
    
    def _fetch_ticket_details(self, ticket_id: str) -> dict:
        """Fetch main ticket details from Freshdesk API"""
        # Include attachments and stats in the response
        url = f"{self.base_url}/tickets/{ticket_id}?include=requester,company,stats"
        headers = {'Authorization': f'Basic {base64.b64encode(f"{self.api_key}:X".encode()).decode()}'}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            ticket_data = response.json()
            
            # Fetch attachments separately as they're not in main ticket endpoint
            attachments = self._fetch_attachments(ticket_id)
            
            # Also check ticket description for attachment links
            description = ticket_data.get('description', '')
            if description:
                desc_attachments = self._extract_attachment_links_from_html(description)
                attachments.extend(desc_attachments)
            
            if attachments:
                ticket_data['attachments'] = attachments
            
            return ticket_data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching ticket details: {e}")
            return {"error": str(e)}
    
    def _fetch_attachments(self, ticket_id: str) -> list:
        """Fetch attachments for a ticket from conversations"""
        try:
            # Get conversations which contain attachment information
            url = f"{self.base_url}/tickets/{ticket_id}/conversations"
            headers = {'Authorization': f'Basic {base64.b64encode(f"{self.api_key}:X".encode()).decode()}'}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            conversations = response.json()
            
            # Extract all attachments from conversations
            all_attachments = []
            for conv in conversations:
                attachments = conv.get('attachments', [])
                all_attachments.extend(attachments)
                
                # Also parse body HTML for attachment links
                body = conv.get('body', '')
                if body:
                    attachment_links = self._extract_attachment_links_from_html(body)
                    all_attachments.extend(attachment_links)
            
            print(f"📎 Found {len(all_attachments)} total attachments")
            return all_attachments
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error fetching attachments: {e}")
            return []
    
    def _extract_attachment_links_from_html(self, html: str) -> list:
        """Extract attachment links from HTML description/conversations"""
        attachments = []
        
        # Pattern: <a href="https://support.freshdesk.com/helpdesk/attachments/ID">filename.har</a>
        pattern = r'<a[^>]*href="(https://[^"]*freshdesk\.com/helpdesk/attachments/(\d+))"[^>]*>([^<]+\.har)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        for match in matches:
            attachment_url, attachment_id, filename = match
            attachments.append({
                'id': attachment_id,
                'name': filename,
                'attachment_url': attachment_url,
                'size': 0,  # Unknown from HTML
                'content_type': 'application/json'
            })
            print(f"🔗 Found HAR link in HTML: {filename} -> {attachment_url}")
        
        return attachments
    
    def _fetch_conversations(self, ticket_id: str) -> list:
        """Fetch all conversations for a ticket"""
        url = f"{self.base_url}/tickets/{ticket_id}/conversations"
        headers = {'Authorization': f'Basic {base64.b64encode(f"{self.api_key}:X".encode()).decode()}'}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching conversations: {e}")
            return [{"error": str(e)}]
    
    def _download_har_attachments(self, ticket_id: str, attachments: list) -> dict:
        """
        Handle HAR file attachments - check for existing files or provide download instructions.
        
        Note: Automated download doesn't work with Google SSO authentication.
        Users must manually download HAR files from browser.
        """
        downloaded = {}
        har_attachments = []
        seen_attachments = set()  # Track seen attachment names to avoid duplicates
        
        # Use project root directory for storing HAR files
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        for attachment in attachments:
            attachment_name = attachment.get('name', '')
            
            # Only process .har files
            if not attachment_name.lower().endswith('.har'):
                continue
            
            # Skip duplicates
            if attachment_name in seen_attachments:
                continue
            seen_attachments.add(attachment_name)
            
            attachment_url = attachment.get('attachment_url')
            local_path = os.path.join(project_root, attachment_name)
            
            # First, check if HAR file already exists locally
            if os.path.exists(local_path) and self._verify_har_file(local_path):
                downloaded[attachment_name] = local_path
                print(f"✅ Found existing HAR file: {attachment_name}")
                continue
            
            # Collect HAR attachments that need manual download
            har_attachments.append({
                'name': attachment_name,
                'url': attachment_url,
                'local_path': local_path
            })
        
        # If there are HAR files that need downloading, provide instructions
        if har_attachments:
            print()
            print("=" * 60)
            print("📎 HAR FILE(S) FOUND - MANUAL DOWNLOAD REQUIRED")
            print("=" * 60)
            print()
            print("⚠️  Auto-download not possible (Google SSO authentication)")
            print()
            print("📋 Please download manually:")
            print()
            
            for i, har in enumerate(har_attachments, 1):
                print(f"   {i}. {har['name']}")
                print(f"      URL: {har['url']}")
                print(f"      Save to: {har['local_path']}")
                print()
            
            print("💡 Quick steps:")
            print("   1. Click the URL above (or open in browser)")
            print("   2. Download the file")
            print("   3. Move to the specified location")
            print("   4. Re-run Sifra")
            print()
            print("=" * 60)
            
            # Store info about pending downloads for the agent to use
            for har in har_attachments:
                downloaded[f"PENDING:{har['name']}"] = har['url']
        
        return downloaded
    
    def _verify_har_file(self, file_path: str) -> bool:
        """Verify that downloaded file is valid HAR JSON"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # HAR files must have a 'log' key
                return 'log' in data
        except:
            return False


# Create instance for easy import
freshdesk_reader = SimpleFreshdeskTool()

