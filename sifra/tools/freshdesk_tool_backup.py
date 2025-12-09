#!/usr/bin/env python3
"""
Simple Freshdesk Tool - Just fetches raw ticket data, lets agent handle analysis
"""

import requests
import base64
import json
import re
import os
import tempfile
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
        """Download HAR file attachments and return local paths using multiple strategies"""
        downloaded = {}
        
        # Use project root directory for storing HAR files
        # This makes them accessible to har_parser tool
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        for attachment in attachments:
            attachment_name = attachment.get('name', '')
            
            # Only download .har files
            if not attachment_name.lower().endswith('.har'):
                continue
            
            attachment_id = attachment.get('id')
            attachment_url = attachment.get('attachment_url')
            
            if not attachment_id and not attachment_url:
                print(f"⚠️  No attachment ID or URL for {attachment_name}")
                continue
            
            # Save to project root with simple filename
            local_path = os.path.join(project_root, attachment_name)
            
            # Try multiple download strategies
            success = False
            
            # STRATEGY 1: Use Freshdesk's dedicated attachment endpoint
            if attachment_id and not success:
                success = self._download_strategy_api_endpoint(
                    attachment_id, attachment_name, local_path
                )
            
            # STRATEGY 2: Direct URL with API auth (original method)
            if attachment_url and not success:
                success = self._download_strategy_direct(
                    attachment_url, attachment_name, local_path
                )
            
            # STRATEGY 3: Try with session cookies if available
            if attachment_url and not success:
                success = self._download_strategy_session_cookies(
                    attachment_url, attachment_name, local_path
                )
            
            if success:
                downloaded[attachment_name] = local_path
            else:
                print(f"❌ All download strategies failed for {attachment_name}")
                print(f"💡 Please manually download from Freshdesk ticket and place in: {local_path}")
        
        return downloaded
    
    def _download_strategy_api_endpoint(self, attachment_id: str, filename: str, local_path: str) -> bool:
        """Strategy 1: Use Freshdesk's dedicated attachment API endpoint"""
        try:
            # Freshdesk's proper attachment download endpoint
            url = f"{self.base_url}/attachments/{attachment_id}"
            headers = {
                'Authorization': f'Basic {base64.b64encode(f"{self.api_key}:X".encode()).decode()}',
                'Accept': 'application/json, application/octet-stream'
            }
            
            print(f"📥 [Strategy 1] Downloading via API endpoint: {filename}")
            
            response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
            
            # Check if we got HTML (login page) instead of file
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                print(f"⚠️  [Strategy 1] Received HTML instead of file (likely login page)")
                return False
            
            response.raise_for_status()
            
            # Write to file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify it's valid JSON (HAR files are JSON)
            if self._verify_har_file(local_path):
                print(f"✅ [Strategy 1] Successfully downloaded: {filename}")
                return True
            else:
                print(f"⚠️  [Strategy 1] Downloaded file is not valid HAR JSON")
                os.remove(local_path)
                return False
                
        except Exception as e:
            print(f"⚠️  [Strategy 1] Failed: {e}")
            return False
    
    def _download_strategy_direct(self, url: str, filename: str, local_path: str) -> bool:
        """Strategy 2: Direct download with API key authentication"""
        try:
            headers = {
                'Authorization': f'Basic {base64.b64encode(f"{self.api_key}:X".encode()).decode()}',
                'Accept': 'application/json, application/octet-stream'
            }
            
            print(f"📥 [Strategy 2] Downloading via direct URL: {filename}")
            
            response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
            
            # Check if we got HTML (login page) instead of file
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                print(f"⚠️  [Strategy 2] Received HTML instead of file (likely login page)")
                return False
            
            response.raise_for_status()
            
            # Write to file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify it's valid JSON
            if self._verify_har_file(local_path):
                print(f"✅ [Strategy 2] Successfully downloaded: {filename}")
                return True
            else:
                print(f"⚠️  [Strategy 2] Downloaded file is not valid HAR JSON")
                os.remove(local_path)
                return False
                
        except Exception as e:
            print(f"⚠️  [Strategy 2] Failed: {e}")
            return False
    
    def _download_strategy_session_cookies(self, url: str, filename: str, local_path: str) -> bool:
        """Strategy 3: Download using browser session cookies (if configured)"""
        try:
            # Try to load Freshdesk session cookie from config
            try:
                from ..utils.config import get_config
                config = get_config()
                freshdesk_session = config.get('freshdesk', {}).get('session_cookie')
            except:
                freshdesk_session = None
            
            if not freshdesk_session:
                print(f"⚠️  [Strategy 3] No session cookie configured, skipping")
                return False
            
            print(f"📥 [Strategy 3] Downloading with session cookies: {filename}")
            
            headers = {
                'Cookie': freshdesk_session,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
            
            # Check if we got HTML (login page) instead of file
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                print(f"⚠️  [Strategy 3] Received HTML instead of file (session may be expired)")
                return False
            
            response.raise_for_status()
            
            # Write to file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify it's valid JSON
            if self._verify_har_file(local_path):
                print(f"✅ [Strategy 3] Successfully downloaded: {filename}")
                return True
            else:
                print(f"⚠️  [Strategy 3] Downloaded file is not valid HAR JSON")
                os.remove(local_path)
                return False
                
        except Exception as e:
            print(f"⚠️  [Strategy 3] Failed: {e}")
            return False
    
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
