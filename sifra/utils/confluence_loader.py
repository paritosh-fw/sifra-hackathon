#!/usr/bin/env python3
"""
Confluence Document Loader
Fetches pages and child pages from Confluence for RAG indexing
"""

import requests
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ConfluencePage:
    """Represents a Confluence page with its content"""
    page_id: str
    title: str
    content: str
    url: str
    space: str
    parent_id: Optional[str] = None
    labels: List[str] = None


class ConfluenceLoader:
    """
    Loads Confluence pages using Confluence REST API
    Supports fetching parent page and all child pages recursively
    """
    
    def __init__(self, base_url: str, username: str, api_token: str):
        """
        Initialize Confluence loader
        
        Args:
            base_url: Confluence base URL (e.g., https://confluence.freshworks.com)
            username: Your Freshworks email
            api_token: API token (Cloud uses Basic Auth) or PAT (Server/DC uses Bearer token)
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/rest/api"
        self.session = requests.Session()
        
        # Confluence Server/DC with PAT requires Bearer token authentication
        # Confluence Cloud uses Basic Auth (username + API token)
        is_cloud = 'atlassian.net' in base_url
        
        if is_cloud:
            # Cloud: Basic Auth
            self.session.auth = (username, api_token)
        else:
            # Server/DC: Bearer token for PAT
            self.session.headers.update({
                'Authorization': f'Bearer {api_token}'
            })
        
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def get_page(self, page_id: str, expand: str = "body.storage,space,metadata.labels") -> Optional[Dict]:
        """
        Get a single page by ID
        
        Args:
            page_id: Confluence page ID
            expand: Fields to expand (default: body, space, labels)
            
        Returns:
            Page data dictionary or None if not found
        """
        url = f"{self.api_base}/content/{page_id}"
        params = {'expand': expand}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching page {page_id}: {e}")
            return None
    
    def get_child_pages(self, page_id: str, limit: int = 100) -> List[Dict]:
        """
        Get direct child pages of a parent page
        
        Args:
            page_id: Parent page ID
            limit: Maximum number of children to fetch per request
            
        Returns:
            List of child page dictionaries
        """
        url = f"{self.api_base}/content/{page_id}/child/page"
        params = {
            'limit': limit,
            'expand': 'body.storage,space,metadata.labels'
        }
        
        all_children = []
        
        try:
            while True:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                children = data.get('results', [])
                all_children.extend(children)
                
                # Check if there are more pages
                if 'next' in data.get('_links', {}):
                    url = f"{self.base_url}{data['_links']['next']}"
                    params = {}  # Next link already has params
                else:
                    break
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching child pages of {page_id}: {e}")
        
        return all_children
    
    def get_all_descendant_pages(self, root_page_id: str) -> List[ConfluencePage]:
        """
        Recursively fetch all descendant pages (children, grandchildren, etc.)
        
        Args:
            root_page_id: ID of the root page to start from
            
        Returns:
            List of ConfluencePage objects including root and all descendants
        """
        all_pages = []
        visited = set()
        
        def fetch_recursive(page_id: str, depth: int = 0):
            """Recursive helper to fetch pages"""
            if page_id in visited:
                return
            
            visited.add(page_id)
            indent = "  " * depth
            
            # Fetch the page itself
            print(f"{indent}📄 Fetching page {page_id}...")
            page_data = self.get_page(page_id)
            
            if not page_data:
                return
            
            # Convert to ConfluencePage
            page = self._convert_to_page(page_data)
            if page:
                all_pages.append(page)
                print(f"{indent}✅ Loaded: {page.title} (ID: {page.page_id})")
            
            # Fetch children recursively
            children = self.get_child_pages(page_id)
            print(f"{indent}👶 Found {len(children)} child page(s)")
            
            for child in children:
                child_id = child.get('id')
                if child_id:
                    fetch_recursive(child_id, depth + 1)
        
        # Start recursive fetch from root
        print(f"\n🌳 Fetching page tree starting from root page {root_page_id}...")
        fetch_recursive(root_page_id)
        
        print(f"\n✅ Total pages loaded: {len(all_pages)}")
        return all_pages
    
    def _convert_to_page(self, page_data: Dict) -> Optional[ConfluencePage]:
        """Convert Confluence API response to ConfluencePage object"""
        try:
            page_id = page_data.get('id')
            title = page_data.get('title', 'Untitled')
            
            # Extract content (HTML storage format)
            body = page_data.get('body', {}).get('storage', {})
            content = body.get('value', '')
            
            # Clean HTML tags (basic cleaning - can be improved)
            import re
            content_text = re.sub('<[^<]+?>', '', content)
            content_text = re.sub(r'\s+', ' ', content_text).strip()
            
            # Build page URL
            url = f"{self.base_url}/pages/viewpage.action?pageId={page_id}"
            
            # Extract space key
            space = page_data.get('space', {}).get('key', 'Unknown')
            
            # Extract labels
            labels = []
            metadata_labels = page_data.get('metadata', {}).get('labels', {}).get('results', [])
            labels = [label.get('name') for label in metadata_labels if label.get('name')]
            
            return ConfluencePage(
                page_id=page_id,
                title=title,
                content=content_text,
                url=url,
                space=space,
                labels=labels
            )
        except Exception as e:
            print(f"❌ Error converting page data: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test if authentication works
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.api_base}/space"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            print("✅ Confluence authentication successful!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Confluence authentication failed: {e}")
            print("💡 Please check your username and API token in config.yaml")
            return False

