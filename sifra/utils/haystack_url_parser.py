#!/usr/bin/env python3
"""
Haystack URL Parser - Extracts search parameters from direct Haystack URLs
"""

import re
import urllib.parse
import json
from typing import Dict, Optional, Tuple
from datetime import datetime

class HaystackURLParser:
    """Parser for Haystack URLs to extract search parameters"""
    
    def __init__(self, config=None):
        # Load configuration
        if config is None:
            from sifra.utils.config import Config
            config = Config()
        
        self.config = config
        
        # Get pod mapping from config
        pod_urls = config.haystack.get('pod_urls', {})
        self.pod_mapping = {}
        for pod, url in pod_urls.items():
            domain = url.replace('https://', '').replace('http://', '')
            self.pod_mapping[domain] = pod
    
    def parse_haystack_url(self, url: str, debug: bool = False) -> Optional[Dict[str, str]]:
        """
        Parse Haystack URL and extract search parameters
        
        Args:
            url: Haystack URL (either goto or discover format)
            debug: Whether to print debug information
            
        Returns:
            Dictionary with extracted parameters or None if parsing fails
        """
        try:
            # Handle goto URLs - need to resolve to discover URL first
            if "/goto/" in url:
                return self._parse_goto_url(url)
            elif "/app/discover" in url:
                return self._parse_discover_url(url, debug)
            else:
                if debug:
                    print(f"❌ Unsupported URL format: {url}")
                return None
                
        except Exception as e:
            if debug:
                print(f"❌ Error parsing Haystack URL: {e}")
            return None
    
    def _parse_goto_url(self, goto_url: str) -> Optional[Dict[str, str]]:
        """
        Parse goto URL by resolving it to discover URL
        
        Args:
            goto_url: Goto URL to resolve
            
        Returns:
            Dictionary with extracted parameters or None if parsing fails
        """
        try:
            print(f"🔍 Resolving goto URL: {goto_url}")
            
            # Make HTTP request to resolve goto URL
            import requests
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            # Get authentication cookies from config (using correct structure)
            cookies = self.config.haystack.get('cookies', {})
            
            # Fallback: If cookies not in new structure, try old keys for backward compatibility
            if not cookies:
                cookies = {
                    'HAYSAuthSessionID-0': self.config.haystack.get('hays_auth_session_id', ''),
                    'userEmail': self.config.haystack.get('default_user_email', '')
                }
            
            print(f"🔐 Using authentication cookies: {list(cookies.keys())}")
            
            # Use HEAD request for faster response (follows redirects)
            response = requests.head(goto_url, headers=headers, cookies=cookies, 
                                    allow_redirects=True, timeout=10)
            
            final_url = response.url
            print(f"✅ Resolved to: {final_url[:100]}...")
            
            # Check if we got redirected to a login page
            if "accounts.google.com" in final_url or "login" in final_url.lower():
                print("⚠️  Redirected to login page - authentication cookies may be expired")
                print("💡 Suggestion: Update authentication cookies in config.yaml")
                print("   - Open browser Dev Tools → Application → Cookies → logs.haystack.es")
                print("   - Copy HAYSAuthSessionID-0 and userEmail values")
                return None
            
            # Check if we got a valid discover URL
            if "/app/discover" not in final_url:
                print(f"⚠️  URL doesn't contain '/app/discover': {final_url[:150]}")
                return None
            
            print("✅ Successfully resolved goto URL to discover URL")
            
            # Now parse the resolved discover URL
            return self._parse_discover_url(final_url, debug=False)
                
        except Exception as e:
            print(f"❌ Error resolving goto URL: {e}")
            return None
    
    def _parse_discover_url(self, discover_url: str, debug: bool = False) -> Optional[Dict[str, str]]:
        """
        Parse discover URL to extract search parameters
        
        Args:
            discover_url: Full discover URL with parameters
            debug: Whether to print debug information
            
        Returns:
            Dictionary with extracted parameters
        """
        try:
            # Extract the fragment part after #
            if '#' not in discover_url:
                if debug:
                    print("❌ Invalid discover URL - missing fragment")
                return None
                
            fragment = discover_url.split('#')[1]
            
            # URL-decode the fragment to convert %27 to ', etc.
            fragment = urllib.parse.unquote(fragment)
            
            # Parse URL parameters
            parsed_url = urllib.parse.urlparse(discover_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Extract parameters from fragment
            fragment_params = self._parse_fragment(fragment, debug)
            
            # Determine pod from domain
            domain = parsed_url.netloc
            pod = self.pod_mapping.get(domain, "us")  # Default to us
            
            # Extract time range
            time_range = fragment_params.get('time', {})
            timestamp_gte = time_range.get('from', '')
            timestamp_lte = time_range.get('to', '')
            
            # Extract query
            query_info = fragment_params.get('query', {})
            query_string = query_info.get('query', '')
            
            # Clean up query string
            if query_string:
                # Remove newline characters (\n, %0A already decoded by unquote above)
                query_string = query_string.replace('\n', ' ').replace('\r', ' ')
                # Remove extra whitespace
                query_string = ' '.join(query_string.split())
                query_string = query_string.strip()
            
            # Extract index pattern
            index_pattern = fragment_params.get('indexPatternTitle', 'freshservice*')
            
            # Extract email from query if present
            email = self._extract_email_from_query(query_string)
            
            # Use email from query or fallback to config default
            if not email:
                email = self.config.haystack.get('default_user_email', 'paritosh.agarwal@freshworks.com')
            
            result = {
                "pod": pod,
                "email": email,
                "product": index_pattern,
                "query_string": query_string,
                "timestamp_gte": timestamp_gte,
                "timestamp_lte": timestamp_lte,
                "original_url": discover_url
            }
            
            if debug:
                print(f"✅ Successfully parsed Haystack URL:")
                print(f"📍 Pod: {result['pod']}")
                print(f"📧 Email: {result['email']}")
                print(f"🏷️ Product: {result['product']}")
                print(f"🔍 Query: {result['query_string']}")
                print(f"⏰ Time Range: {result['timestamp_gte']} to {result['timestamp_lte']}")
            
            return result
            
        except Exception as e:
            if debug:
                print(f"❌ Error parsing discover URL: {e}")
            return None
    
    def _parse_fragment(self, fragment: str, debug: bool = False) -> Dict:
        """Parse URL fragment to extract parameters"""
        params = {}
        
        try:
            if debug:
                print(f"🔍 Parsing fragment: {fragment[:200]}...")
            
            # Extract time range directly from fragment
            time_match = re.search(r"time:\(from:'([^']+)',to:'([^']+)'\)", fragment)
            if time_match:
                params['time'] = {
                    'from': time_match.group(1),
                    'to': time_match.group(2)
                }
                if debug:
                    print(f"✅ Extracted time: {params['time']}")
            elif debug:
                print("❌ No time match found")
            
            # Extract index pattern directly from fragment
            index_pattern_match = re.search(r"indexPatternTitle:'([^']+)'", fragment)
            if index_pattern_match:
                params['indexPatternTitle'] = index_pattern_match.group(1)
                if debug:
                    print(f"✅ Extracted index pattern: {params['indexPatternTitle']}")
            elif debug:
                print("❌ No index pattern match found")
            
            # Extract query directly from fragment
            query_match = re.search(r"query:\(language:lucene,query:'([^']+)'\)", fragment)
            if query_match:
                params['query'] = {
                    'language': 'lucene',
                    'query': query_match.group(1)
                }
                if debug:
                    print(f"✅ Extracted query: {params['query']}")
            elif debug:
                print("❌ No query match found")
                    
        except Exception as e:
            if debug:
                print(f"⚠️  Warning: Error parsing fragment: {e}")
            
        return params
    
    def _extract_email_from_query(self, query_string: str) -> Optional[str]:
        """Extract email address from query string"""
        if not query_string:
            return None
            
        # Look for email pattern in query
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, query_string)
        return match.group(0) if match else None
    
    def convert_goto_to_discover(self, goto_url: str) -> str:
        """
        Convert goto URL to discover URL format
        This is a placeholder - in practice, you'd need to make an HTTP request
        """
        print("⚠️  Goto URL conversion requires HTTP request to resolve")
        print("Please manually convert the goto URL to discover URL format")
        return goto_url

# Example usage and testing
if __name__ == "__main__":
    parser = HaystackURLParser()
    
    # Test with the provided discover URL
    test_url = "https://logs.haystack.es/app/discover#/?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:'2025-10-22T18:30:00.000Z',to:'2025-10-25T18:29:59.999Z'))&_a=(columns:!(host,message),filters:!(),index:'806f55e0-fddd-11e8-86e3-1f84a673de07',indexPatternTitle:'freshservice*',interval:auto,query:(language:lucene,query:'96a9d210-70ac-9097-920e-23791daf3c67%0A'),sort:!(!('@timestamp',desc)))"
    
    result = parser.parse_haystack_url(test_url)
    if result:
        print("\n📋 Extracted Parameters:")
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        print("❌ Failed to parse URL")
