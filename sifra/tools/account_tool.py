#!/usr/bin/env python3
"""
Account Tool - Simple CrewAI tool for reading Freshops admin panel account details
"""

import requests
import json
from typing import Type
from crewai.tools import BaseTool
# Note: Removed ScrapeWebsiteTool import - using direct authenticated requests instead
from pydantic import BaseModel, Field


class AccountReaderInput(BaseModel):
    """Input schema for Account reader tool."""
    account_url: str = Field(description="Freshops admin panel account URL to analyze")


class AccountReaderTool(BaseTool):
    """Simple CrewAI tool for extracting account details from Freshops admin panel"""
    
    name: str = "account_reader"
    description: str = "Extract account details from Freshops admin panel using authentication credentials"
    args_schema: Type[BaseModel] = AccountReaderInput
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        
        # Load configuration from config.yaml
        from sifra.utils.config import Config
        config = Config()
        freshops_config = config.freshops
        
        object.__setattr__(self, 'freshops_domain', freshops_config.get('domain', 'freshops-admin.freshservice.com'))
        object.__setattr__(self, 'freshops_session_cookie', freshops_config.get('session_cookie', ''))
        
        # Note: Using direct authenticated requests instead of CrewAI ScrapeWebsiteTool for proper auth
    
    def _run(self, account_url: str) -> str:
        """Extract account details from Freshops admin panel"""
        if not account_url:
            return json.dumps({"error": "No account URL provided"})
        
        print(f"🏢 Reading Account Details: {account_url}")
        
        try:
            # Extract account ID from URL using simple AI
            account_id = self._extract_account_id(account_url)
            if not account_id:
                return json.dumps({"error": "Could not extract account ID from URL"})
            
            print(f"📊 Account ID: {account_id}")
            
            # Scrape the account page with authentication
            page_content = self._scrape_with_auth(account_url)
            
            # Extract specific account information using AI
            account_data = self._extract_account_info(account_id, page_content)
            
            print("✅ Account details extracted successfully")
            return account_data
            
        except Exception as e:
            return json.dumps({"error": f"Failed to extract account details: {str(e)}"})
    
    def _extract_account_id(self, url: str) -> str:
        """Extract account ID from URL using AI"""
        prompt = f"""
        Extract the account ID number from this URL: {url}
        
        Look for patterns like /accounts/754504 or /accounts/123456
        Return ONLY the numeric ID, nothing else.
        If no ID found, return "NONE".
        """
        
        try:
            response = self._call_llm(prompt)
            account_id = response.strip()
            return account_id if account_id != "NONE" else None
        except:
            return None
    
    def _scrape_with_auth(self, account_url: str) -> str:
        """Scrape account page with authentication"""
        # Use our authenticated request directly since CrewAI ScrapeWebsiteTool doesn't have auth headers
        print("🔐 Using authenticated request for account data...")
        return self._authenticated_request(account_url)
    
    def _authenticated_request(self, account_url: str) -> str:
        """Make authenticated request to Freshops admin panel using working Spring Boot approach"""
        try:
            # Use the working authentication method (Spring Boot approach)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Content-Type': 'application/json',
                'Upgrade-Insecure-Requests': '1',
                'Cookie': f'_freshops_admin_session={self.freshops_session_cookie}'
            }
            
            print("🔐 Authenticating with Freshops admin session...")
            response = requests.get(account_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Check if we got a login page instead of account data
                # Look for actual login form indicators, not just "devops" in title
                is_login_page = (
                    "sign_in" in response.text.lower() or 
                    "sign in" in response.text.lower() or
                    "login form" in response.text.lower() or
                    '<form' in response.text.lower() and 'password' in response.text.lower() and 'email' in response.text.lower()
                )
                
                if is_login_page:
                    print("⚠️  Warning: Received login page - session may be expired")
                    return json.dumps({
                        "error": "Authentication failed - received login page",
                        "message": "Freshops session cookie appears to be expired or invalid",
                        "status": "Authentication Failed",
                        "recommendation": "Please update the Freshops session cookie in config.yaml (freshops.session_cookie)"
                    })
                else:
                    print("✅ Successfully authenticated and got account data!")
                    return response.text
            else:
                return json.dumps({
                    "error": f"HTTP error {response.status_code}",
                    "message": "Failed to access Freshops admin panel"
                })
            
        except Exception as e:
            return json.dumps({"error": f"Request failed: {str(e)}"})
    
    def update_session_cookie(self, session_cookie: str):
        """Update the Freshops admin session cookie (Note: This updates runtime only, not config.yaml)"""
        object.__setattr__(self, 'freshops_session_cookie', session_cookie)
        print(f"✅ Updated Freshops session cookie (runtime only)")
    
    def _extract_account_info(self, account_id: str, page_content: str) -> str:
        """Extract specific account information using AI"""
        
        prompt = f"""
        Extract account information from this Freshops admin panel page content.
        
        PAGE CONTENT:
        {page_content[:8000]}
        
        Extract information using these EXACT HTML field labels and return as JSON:
        
        FIELD MAPPING (look for these exact labels in the HTML):
        - "Account ID" → account_id
        - "Name" (extract complete text including URL in parentheses) → account_name
        - "Subscription ID" → subscription_id
        - "Shard" → shard
        - "Pod" → pod
        - "Contact information" (email and phone combined) → contact_information
        - "Created" → created_date
        - "Billing site" → billing_site
        - "State" → state
        - "Account Mode" → account_mode
        - "Plan" → plan
        - "Billing cycle (in months)" → billing_cycle
        - "Monthly Revenue (adjusted to current exchange rate)" → monthly_revenue
        - "API Limit" → api_limit
        - "Organization URL" (the myfreshworks.com one) → organization_url
        - "Organization Admins" → organization_admins
        
        Return JSON in this format:
        {{
            "account_id": "{account_id}",
            "account_name": "complete value from Name field including URL in parentheses",
            "subscription_id": "value from Subscription ID",
            "shard": "value from Shard",
            "pod": "value from Pod",
            "contact_information": "email and phone from Contact information field",
            "created_date": "value from Created",
            "billing_site": "value from Billing site",
            "state": "value from State",
            "account_mode": "value from Account Mode",
            "plan": "value from Plan",
            "billing_cycle": "value from Billing cycle (in months)",
            "monthly_revenue": "value from Monthly Revenue",
            "api_limit": "value from API Limit",
            "organization_url": "value from Organization URL",
            "organization_admins": "value from Organization Admins"
        }}
        
        IMPORTANT:
        - For "Name" field: Extract COMPLETE text including the URL in parentheses (e.g., "Oak Valley Hospital ( oakvalleyhospital.freshservice.com )")
        - For "Organization URL": Use the myfreshworks.com URL, not the freshservice.com one
        - For "Contact information": Combine email and phone on same line (e.g., "trinehart@ovhd.com, 2098485464")
        - Use null for fields not found in the HTML
        
        Return ONLY the JSON object.
        """
        
        try:
            return self._call_llm(prompt)
        except Exception as e:
            return json.dumps({"error": f"AI extraction failed: {str(e)}"})
    
    def _call_llm(self, prompt: str) -> str:
        """Call Cloudverse LLM"""
        # Use the same Cloudverse token from config
        from sifra.utils.config import Config
        config = Config()
        api_key = config.llm.get('api_key', '')
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'anthropic-claude-3-5-sonnet-v2',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1500
        }
        
        response = requests.post(
            'https://cloudverse.freshworkscorp.com/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=90  # Increased from 30s to handle large HTML pages
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"LLM Error: {response.status_code}"


# Create instance for easy import
account_reader = AccountReaderTool()