class Haystack:
    """
    Haystack log search utility class
    """
    
    def __init__(self, pod: str, email: str, product: str, query_string: str, timestamp_gte: str, timestamp_lte: str, config=None):
        """
        Initialize Haystack search parameters
        
        Args:
            pod: Pod/region (us/in/eu/au)
            email: User email
            product: Product (e.g., freshservice*)
            query_string: Search query string
            timestamp_gte: Start timestamp in ISO format
            timestamp_lte: End timestamp in ISO format
            config: Configuration object (optional)
        """
        # Load configuration
        if config is None:
            from sifra.utils.config import Config
            config = Config()
        
        # Get pod URLs from config
        pod_urls_dict = config.haystack.get('pod_urls', {
            "us": "https://logs.haystack.es",
            "in": "https://logs-in.haystack.es",
            "eu": "https://logs-euc.haystack.es",
            "au": "https://logs-au.haystack.es"
        })
        
        # Use provided email or default from config
        if not email or email == "unknown@example.com":
            email = config.haystack.get('default_user_email', 'paritosh.agarwal@freshworks.com')
        
        self.haystack_url = pod_urls_dict.get(pod)
        self.email = email
        self.product = product
        self.query_string = query_string
        self.timestamp_gte = timestamp_gte
        self.timestamp_lte = timestamp_lte
        self.config = config

    def get_logs(self):
        """
        Search Haystack logs and return log messages
        
        Returns:
            list: List of log messages
        """
        
        import requests

        # Get cookies from config (using correct structure)
        cookies = self.config.haystack.get('cookies', {}).copy()
        
        # Fallback: If cookies not in new structure, try old keys for backward compatibility
        if not cookies:
            cookies = {
                'HAYSAuthSessionID-0': self.config.haystack.get('hays_auth_session_id', ''),
                'userEmail': self.email
            }
        else:
            # Update userEmail in cookies with the current email
            cookies['userEmail'] = self.email

        headers = {
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/json',
            'origin': self.haystack_url,
            'osd-version': '6.1.5-SNAPSHOT',
            'priority': 'u=1, i',
            'referer': f"{self.haystack_url}/app/discover",
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'x-env': 'production',
        }

        json_data = {

            'searches': [
                {
                    'header': {
                        'index': f"{self.product}", #'freshservice*',
                        'preference': 1761109933271,
                    },
                    'body': {
                        'version': True,
                        'size': 2000,
                        'sort': [
                            {
                                '@timestamp': {
                                    'order': 'asc',
                                    'unmapped_type': 'boolean',
                                },
                            },
                            {
                                'offset': {
                                    'order': 'asc',
                                    'unmapped_type': 'boolean',
                                },
                            },
                        ],
                        'stored_fields': [
                            '*',
                        ],
                        'script_fields': {},
                        'docvalue_fields': [
                            {
                                'field': '@timestamp',
                                'format': 'date_time',
                            },
                            {
                                'field': 'time',
                                'format': 'date_time',
                            },
                        ],
                        '_source': {
                            'excludes': [],
                        },
                        'query': {
                            'bool': {
                                'must': [
                                    {
                                        'query_string': {
                                            'query': f"{self.query_string}", #'3bd9fafc1a115df8ae7f7317 AND error',
                                            'analyze_wildcard': True,
                                            'default_operator': 'AND',
                                            'time_zone': 'Asia/Calcutta',
                                        },
                                    },
                                ],
                                'filter': [
                                    {
                                        'range': {
                                            '@timestamp': {
                                                'gte': f"{self.timestamp_gte}",  # '2025-10-16T18:30:00.000Z',
                                                'lte': f"{self.timestamp_lte}",   # '2025-10-17T18:29:59.999Z',
                                                'format': 'strict_date_optional_time',
                                            },
                                        },
                                    },
                                ],
                                'should': [],
                                'must_not': [],
                            },
                        },
                        'track_total_hits': False,
                    },
                },
            ],
        }

        print (f"{self.haystack_url}/internal/_msearch")
       
        print(json_data)

        response = requests.post(f"{self.haystack_url}/internal/_msearch", cookies=cookies, headers=headers, json=json_data)
        
        log_messages = []

        try:
            # Parse the response body as JSON
            import json

            data = response.json()
            print(f"✅ Successfully parsed JSON response")
            print(f"📊 Response keys: {list(data.keys())}")

            # Print the JSON data
            # print(json.dumps(data, indent=4)) # Pretty print for readability

            responses = data["body"]["responses"]
            print(f"📊 Found {len(responses)} responses")
            # print(json.dumps(responses, indent=4)) # Pretty print for readability

            hits = responses[0]["hits"]["hits"]
            print(f"📊 Found {len(hits)} log entries")
            # print(json.dumps(hits, indent=4)) # Pretty print for readability
            
            for hit in hits:
                print("Message : ")
                print(json.dumps(hit["_source"]["message"], indent=4))
                print("\n")
                log_messages.append(hit["_source"]["message"])
            
            # Return the collected log messages
            return log_messages

        except requests.exceptions.JSONDecodeError:
            print("❌ Response body is not valid JSON - likely authentication failed")
            print("🔍 Response content type:", response.headers.get('content-type', 'Unknown'))
            print("🔍 Response status code:", response.status_code)
            print("🔍 First 200 chars of response:", response.text[:200])
            
            # If we get HTML (login page), return empty list but log the issue
            if 'text/html' in response.headers.get('content-type', '').lower():
                print("⚠️  Received HTML response - likely a login page. Authentication may have failed.")
            
            return log_messages