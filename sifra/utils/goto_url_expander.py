#!/usr/bin/env python3
"""
Goto URL Expander - Standalone utility to expand Haystack goto URLs to discover URLs

This module provides a simple function to convert short Haystack goto URLs 
to complete discover URLs that can be used for search requests.
"""

import requests
from typing import Optional, Dict


def expand_goto_url(goto_url: str, cookies: Dict[str, str], timeout: int = 10) -> Optional[str]:
    """
    Expand a Haystack goto URL to its complete discover URL.
    
    This function uses HTTP HEAD request with authentication cookies to follow 
    redirects and obtain the complete discover URL with all search parameters.
    
    Args:
        goto_url: The short goto URL from support ticket
                  (e.g., https://logs.haystack.es/goto/fcfcf7992bf3d65a6708060150547f37)
        cookies: Dictionary with authentication cookies:
                 - HAYSAuthSessionID-0: Session authentication token
                 - userEmail: User email address
        timeout: Request timeout in seconds (default: 10)
    
    Returns:
        Complete discover URL with all search parameters, or None if expansion fails
        
    Example:
        >>> cookies = {
        ...     'HAYSAuthSessionID-0': 'your_session_token',
        ...     'userEmail': 'user@example.com'
        ... }
        >>> goto_url = "https://logs.haystack.es/goto/abc123..."
        >>> discover_url = expand_goto_url(goto_url, cookies)
        >>> if discover_url:
        ...     print(f"Expanded to: {discover_url}")
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # STRATEGY 1: Try WITHOUT cookies first (goto URLs might be public)
        # This matches the user's original simple code that worked
        response = requests.head(
            goto_url, 
            headers=headers,
            allow_redirects=True, 
            timeout=timeout
        )
        
        final_url = response.url
        
        # Check if we got redirected to login (authentication required)
        if "accounts.google.com" in final_url or "login" in final_url.lower():
            # STRATEGY 2: Try WITH cookies (maybe authentication is needed)
            print("⚠️  Public access failed, trying with authentication cookies...")
            response = requests.head(
                goto_url, 
                headers=headers, 
                cookies=cookies,
                allow_redirects=True, 
                timeout=timeout
            )
            final_url = response.url
            
            # Still failed?
            if "accounts.google.com" in final_url or "login" in final_url.lower():
                print("⚠️  Authentication failed - cookies may be expired")
                print("💡 Update cookies in config.yaml from browser Dev Tools")
                return None
        
        if "/app/discover" not in final_url:
            print(f"⚠️  URL doesn't contain '/app/discover': {final_url[:100]}...")
            return None
        
        return final_url
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout expanding URL after {timeout} seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error expanding URL: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def expand_goto_url_from_config(goto_url: str, config=None) -> Optional[str]:
    """
    Expand a goto URL using cookies from configuration.
    
    Args:
        goto_url: The goto URL to expand
        config: Configuration object (optional, will load if not provided)
    
    Returns:
        Complete discover URL or None if expansion fails
        
    Example:
        >>> goto_url = "https://logs.haystack.es/goto/abc123..."
        >>> discover_url = expand_goto_url_from_config(goto_url)
    """
    # Load configuration if not provided
    if config is None:
        from sifra.utils.config import Config
        config = Config()
    
    # Get cookies from config
    cookies = config.haystack.get('cookies', {})
    
    if not cookies:
        print("❌ No authentication cookies found in config")
        print("💡 Add cookies to config.yaml under haystack.cookies")
        return None
    
    return expand_goto_url(goto_url, cookies)


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Test with command line argument
        goto_url = sys.argv[1]
        print(f"🔍 Expanding goto URL: {goto_url}")
        
        expanded = expand_goto_url_from_config(goto_url)
        
        if expanded:
            print(f"\n✅ Success!")
            print(f"\n📋 Complete Discover URL:")
            print(f"{expanded}")
        else:
            print(f"\n❌ Failed to expand URL")
            sys.exit(1)
    else:
        # Test with example URL
        print("Usage: python goto_url_expander.py <goto_url>")
        print("\nExample:")
        print("  python goto_url_expander.py https://logs.haystack.es/goto/fcfcf7992bf3d65a6708060150547f37")

