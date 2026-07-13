#!/usr/bin/env python3
"""
Generalized accessibility tree extractor and crawler for websites with cookie support.
Based on WebArena implementation but simplified for reliability.

Usage:
    python get_accessibility_tree_public.py "http://example.com"
    python get_accessibility_tree_public.py "http://example.com" --cookies "admin=abc123"
    python get_accessibility_tree_public.py "http://example.com" --cookie-file cookies.pkl
    python get_accessibility_tree_public.py --config config.json
    python get_accessibility_tree_public.py "http://example.com" --crawl --max-depth 4 --max-pages 2000
"""

import sys
import urllib.parse
import json
import argparse
import time
import re
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
import pickle
from collections import deque
from urllib.parse import urljoin, urlparse

def parse_cookie_string(cookie_string: str) -> list:
    """Parse cookie string into Playwright format."""
    cookies = []
    
    # Remove "Cookie:" prefix if present
    if cookie_string.startswith("Cookie:"):
        cookie_string = cookie_string[7:].strip()
    
    # Split by semicolon for multiple cookies
    for pair in cookie_string.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': '',  # Will be set later
                'path': '/',
                'expires': -1,
                'httpOnly': False,
                'secure': False,
                'sameSite': 'Lax'
            })
    
    return cookies

def parse_cookie_string_browser_format(cookie_string: str) -> list:
    """Parse browser-format cookie string (multiple name=value pairs separated by semicolons)."""
    cookies = []
    
    # Remove "Cookie:" prefix if present
    if cookie_string.startswith("Cookie:"):
        cookie_string = cookie_string[7:].strip()
    
    # Split by semicolon and process each cookie
    for pair in cookie_string.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': '',  # Will be set later
                'path': '/',
                'expires': -1,
                'httpOnly': False,
                'secure': False,
                'sameSite': 'Lax'
            })
    
    return cookies


def extract_url_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or parsed.netloc


def parse_accessibility_tree_simple(accessibility_tree: list, debug_buttons: bool = False, button_urls: dict = None) -> str:
    """Parse accessibility tree to text - simplified version."""
    
    if button_urls is None:
        button_urls = {}
    
    # Ignored properties that add noise
    ignored_props = {
        "readonly", "level", 
        "settable", "multiline"
    }
    
    # Build node index
    node_index = {node["nodeId"]: i for i, node in enumerate(accessibility_tree)}
    
    def format_node(node_idx: int, obs_id: str, depth: int) -> str:
        if node_idx >= len(accessibility_tree):
            return ""
            
        node = accessibility_tree[node_idx]
        indent = "  " * depth  # Use spaces instead of tabs
        
        try:
            role = node.get("role", {}).get("value", "unknown")
            name = node.get("name", {}).get("value", "")
            
            # Format basic node info
            node_str = f"{indent}[{obs_id}] {role}"
            if name:
                node_str += f" {repr(name)}"
            
            # Add relevant properties
            properties = []
            for prop in node.get("properties", []):
                try:
                    prop_name = prop.get("name", "")
                    if prop_name not in ignored_props:
                        prop_value = prop.get("value", {}).get("value", "")
                        if prop_value:
                            properties.append(f"{prop_name}: {prop_value}")
                except:
                    pass
            
            # Add clickable property for interactive elements
            has_clickable = any("clickable" in prop for prop in properties)
            if not has_clickable and role in ["link", "button", "menuitem", "tab", "option", "treeitem"]:
                properties.append("clickable: true")
            
            # Special handling for links and buttons - add URL if available
            if role in ["link", "button"]:
                # Check for URL in different possible locations
                url = None
                
                # Method 1: Check in properties for 'url'
                for prop in node.get("properties", []):
                    prop_name = prop.get("name", "")
                    if prop_name == "url":
                        url = prop.get("value", {}).get("value", "")
                        break
                
                # Method 2: Check direct 'url' field
                if not url and "url" in node:
                    url = node["url"]
                
                # Method 3: Check in attributes for various URL-related attributes
                if not url:
                    for attr in node.get("attributes", []):
                        attr_name = attr.get("name", "")
                        attr_value = attr.get("value", "")
                        
                        # Traditional URL attributes
                        if attr_name in ["href", "url", "data-href", "data-url", "data-navigation-url"]:
                            if attr_value and ("http" in attr_value or attr_value.startswith("/") or attr_value.startswith("javascript:")):
                                url = attr_value
                                break
                        
                        # Look for data attributes that might contain URLs or routes
                        if attr_name.startswith("data-") and attr_value:
                            if any(keyword in attr_value.lower() for keyword in ["lightning", "/lightning", "force.com", "page", "record", "view"]):
                                url = attr_value
                                break
                
                # Method 4: For buttons, check for Salesforce-specific attributes
                if not url and role == "button":
                    for attr in node.get("attributes", []):
                        attr_name = attr.get("name", "").lower()
                        attr_value = attr.get("value", "")
                        if any(keyword in attr_name for keyword in ["nav", "route", "path", "target", "action"]):
                            if attr_value and (attr_value.startswith("/") or "lightning" in attr_value):
                                url = attr_value
                                break
                
                # Method 5: Check in node's children for any URL information
                if not url:
                    for child_id in node.get("childIds", []):
                        if child_id in node_index:
                            child_node = accessibility_tree[node_index[child_id]]
                            if "url" in child_node:
                                url = child_node["url"]
                                break
                
                # Method 6: For buttons, check DOM-extracted URL information
                if not url and role == "button" and button_urls:
                    button_text = name.strip()
                    if button_text in button_urls:
                        dom_attrs = button_urls[button_text]
                        # Check for child href first (most reliable)
                        if 'child_href' in dom_attrs:
                            url = dom_attrs['child_href']
                        else:
                            # Look for data attributes that might contain URLs
                            for attr_name, attr_value in dom_attrs.items():
                                if attr_value and any(keyword in str(attr_value).lower() 
                                                    for keyword in ["lightning", "/lightning", "force.com", "http"]):
                                    url = f"DOM_ATTR:{attr_name}={attr_value}"
                                    break
                
                if url:
                    # Check if URL is already in properties to avoid duplication
                    url_already_added = any(f"url: {url}" in prop for prop in properties)
                    if not url_already_added:
                        properties.append(f"url: {url}")
                
                # Debug mode: show all attributes for buttons
                if debug_buttons and role == "button":
                    debug_attrs = []
                    for attr in node.get("attributes", []):
                        attr_name = attr.get("name", "")
                        attr_value = attr.get("value", "")
                        if attr_value:
                            debug_attrs.append(f"{attr_name}={attr_value[:50]}")  # Limit length
                    
                    # Also check properties
                    debug_props = []
                    for prop in node.get("properties", []):
                        prop_name = prop.get("name", "")
                        prop_value = prop.get("value", {})
                        if isinstance(prop_value, dict) and "value" in prop_value:
                            val = str(prop_value["value"])[:30]
                            if val:
                                debug_props.append(f"{prop_name}={val}")
                    
                    all_debug = debug_attrs + debug_props
                    if all_debug:
                        properties.append(f"DEBUG: {'; '.join(all_debug[:5])}")  # Limit to 5 items
            
            if properties:
                node_str += " " + " ".join(properties)
            
            # Skip empty generic containers
            if role in ["generic", "Section"] and not name and not properties:
                result = ""
            else:
                result = node_str + "\n"
            
            # Process children
            for child_id in node.get("childIds", []):
                if child_id in node_index:
                    child_text = format_node(
                        node_index[child_id], 
                        child_id, 
                        depth + 1 if result else depth
                    )
                    result += child_text
            
            return result
            
        except Exception as e:
            return f"{indent}[{obs_id}] ERROR: {str(e)}\n"
    
    if not accessibility_tree:
        return "No accessibility tree found"
    
    return format_node(0, accessibility_tree[0]["nodeId"], 0)


def load_cookies_from_file(file_path: str) -> list:
    """Load cookies from a file (supports .pkl, .json)."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Cookie file not found: {file_path}")
    
    if file_path.suffix == '.pkl':
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    elif file_path.suffix == '.json':
        with open(file_path, 'r') as f:
            return json.load(f)
    else:
        raise ValueError(f"Unsupported cookie file format: {file_path.suffix}")

def load_config_from_file(config_path: str) -> dict:
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)

def save_cookies_to_file(cookies: list, file_path: str):
    """Save cookies to a file."""
    file_path = Path(file_path)
    
    if file_path.suffix == '.pkl':
        with open(file_path, 'wb') as f:
            pickle.dump(cookies, f)
    elif file_path.suffix == '.json':
        with open(file_path, 'w') as f:
            json.dump(cookies, f, indent=2)
    else:
        raise ValueError(f"Unsupported cookie file format: {file_path.suffix}")


def extract_accessibility_tree_with_config(config: dict) -> str:
    """Extract accessibility tree using configuration dictionary.
    
    Args:
        config: Dictionary with keys like 'url', 'cookies', 'show_browser', 'debug_buttons'
    """
    url = config.get('url')
    if not url:
        raise ValueError("URL is required in configuration")
    
    cookies_list = config.get('cookies')
    show_browser = config.get('show_browser', False)
    debug_buttons = config.get('debug_buttons', False)
    wait_time = config.get('wait_time', 3000)  # Default 3 seconds
    timeout = config.get('timeout', 60000)  # Default 60 seconds
    
    return extract_accessibility_tree(
        url=url,
        cookies_list=cookies_list,
        show_browser=show_browser,
        debug_buttons=debug_buttons,
        wait_time=wait_time,
        timeout=timeout
    )

def extract_accessibility_tree(url: str, cookie: str = None, cookies_list: list = None, 
                             show_browser: bool = False, debug_buttons: bool = False,
                             wait_time: int = 3000, timeout: int = 60000) -> str:
    """Extract accessibility tree from website.
    
    Args:
        url: The URL to extract from
        cookie: Cookie string in format "name=value; name2=value2" (deprecated, use cookies_list)
        cookies_list: List of cookie dictionaries in Playwright format
        show_browser: Whether to show the browser window
        debug_buttons: Whether to show debug info for buttons
        wait_time: Time to wait for dynamic content (ms)
        timeout: Page load timeout (ms)
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not show_browser)
        
        try:
            # Create context
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            
            # Add cookies if provided
            if cookies_list:
                # Use cookies in Playwright format directly
                context.add_cookies(cookies_list)
            elif cookie:
                # Parse cookie string (legacy format)
                cookies = parse_cookie_string(cookie)
                domain = extract_url_domain(url)
                for c in cookies:
                    c['domain'] = domain
                context.add_cookies(cookies)
            
            # Create page and enable accessibility
            page = context.new_page()
            # Set page timeout for all operations
            page.set_default_timeout(timeout)
            client = page.context.new_cdp_session(page)
            client.send("Accessibility.enable")
            
            # Navigate to page
            print(f"Loading page: {url}", file=sys.stderr)
            page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            
            # Wait for dynamic content
            page.wait_for_timeout(wait_time)
            
            # Extract accessibility tree with timeout protection
            print("Extracting accessibility tree...", file=sys.stderr)
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Accessibility tree extraction timed out after {timeout/1000}s")
            
            # Set up timeout for accessibility tree extraction
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout/1000))  # Convert ms to seconds
            
            try:
                result = client.send("Accessibility.getFullAXTree", {})
                accessibility_tree = result["nodes"]
            finally:
                signal.alarm(0)  # Cancel the alarm
            
            # Also try to extract button URLs from DOM
            button_urls = {}
            try:
                print("Extracting button URLs from DOM...", file=sys.stderr)
                # Set up timeout for DOM button extraction
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout/1000))  # Convert ms to seconds
                
                try:
                    # Get all buttons and their click handlers or data attributes
                    js_result = page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button, [role="button"]');
                            const result = {};
                            buttons.forEach((btn, index) => {
                                const text = btn.textContent?.trim() || btn.getAttribute('aria-label') || '';
                                if (text) {
                                    const attrs = {};
                                    // Check data attributes
                                    for (let attr of btn.attributes) {
                                        if (attr.name.startsWith('data-') || attr.name === 'onclick') {
                                            attrs[attr.name] = attr.value;
                                        }
                                    }
                                    // Check for links within button
                                    const link = btn.querySelector('a');
                                    if (link && link.href) {
                                        attrs['child_href'] = link.href;
                                    }
                                    if (Object.keys(attrs).length > 0) {
                                        result[text] = attrs;
                                    }
                                }
                            });
                            return result;
                        }
                    """)
                    button_urls = js_result
                finally:
                    signal.alarm(0)  # Cancel the alarm
                print(f"Found {len(button_urls)} buttons with potential URL info", file=sys.stderr)
                # Debug: show what was found if in debug mode
                if debug_buttons:
                    for btn_text, attrs in list(button_urls.items())[:5]:  # Show first 5
                        print(f"  Button '{btn_text}': {attrs}", file=sys.stderr)
            except Exception as e:
                print(f"Could not extract DOM button info: {e}", file=sys.stderr)
            
            # Remove duplicates
            seen_ids = set()
            unique_tree = []
            for node in accessibility_tree:
                if node["nodeId"] not in seen_ids:
                    unique_tree.append(node)
                    seen_ids.add(node["nodeId"])
            
            # Parse to text
            tree_text = parse_accessibility_tree_simple(unique_tree, debug_buttons, button_urls)
            return tree_text
            
        except Exception as e:
            return f"Error: {str(e)}"
        
        finally:
            browser.close()


def extract_website_accessibility_tree(url: str, cookie_file: str = None, cookies_list: list = None, 
                                     show_browser: bool = False, debug_buttons: bool = False) -> str:
    """Extract accessibility tree from any website with flexible cookie support."""
    
    cookies = cookies_list
    if cookie_file and not cookies:
        try:
            cookies = load_cookies_from_file(cookie_file)
            print(f"Loaded {len(cookies)} cookies from {cookie_file}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not load cookies from {cookie_file}: {e}", file=sys.stderr)
    
    print(f"Extracting accessibility tree from: {url}")
    if cookies:
        print(f"Using {len(cookies)} cookies...")
    if debug_buttons:
        print("DEBUG MODE: Will show button attributes for debugging")
    print("-" * 80)
    
    tree = extract_accessibility_tree(url, cookies_list=cookies, show_browser=show_browser, debug_buttons=debug_buttons)
    return tree


class WebCrawler:
    """Web crawler with accessibility tree extraction."""
    
    def __init__(self, max_depth=4, max_pages=2000, delay=1.0, same_domain_only=True, max_links_per_depth=10):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay  # Delay between requests in seconds
        self.same_domain_only = same_domain_only
        self.max_links_per_depth = max_links_per_depth  # Max links to sample at depth > 0
        
        # Crawling state
        self.visited_urls = set()
        self.queued_urls = set()  # Track URLs that have been added to queue
        self.url_queue = deque()  # (url, depth)
        self.crawled_pages = []
        self.failed_urls = []
        
        # Dictionary storage: URL -> accessibility data
        self.accessibility_data = {}  # Main storage: {url: {tree_text, accessibility_tree, metadata}}
        
    def add_url_to_queue(self, url, depth):
        """Add URL to queue only if it's unique and not already visited/queued."""
        if url not in self.visited_urls and url not in self.queued_urls:
            self.url_queue.append((url, depth))
            self.queued_urls.add(url)
            return True
        return False

    def get_accessibility_data(self, url=None):
        """Get accessibility data dictionary. If url specified, return data for that URL."""
        if url:
            return self.accessibility_data.get(url)
        return self.accessibility_data
    
    def get_all_urls(self):
        """Get list of all crawled URLs."""
        return list(self.accessibility_data.keys())
    
    def get_urls_by_depth(self, depth):
        """Get URLs crawled at specific depth."""
        return [url for url, data in self.accessibility_data.items() 
                if data.get('depth') == depth]
    
    def export_accessibility_dict(self, include_raw_tree=False):
        """Export accessibility data as a clean dictionary.
        
        Args:
            include_raw_tree: Whether to include the raw accessibility tree nodes
        """
        exported = {}
        for url, data in self.accessibility_data.items():
            exported[url] = {
                'title': data.get('title', ''),
                'depth': data.get('depth', 0),
                'crawl_time': data.get('crawl_time', 0),
                'tree_text': data.get('tree_text', ''),
                'button_urls': data.get('button_urls', {}),
                'links_found': data.get('links_found', [])
            }
            
            if include_raw_tree:
                exported[url]['accessibility_tree'] = data.get('accessibility_tree', [])
        
        return exported
    
    def save_accessibility_dict(self, file_path="accessibility_data.json", include_raw_tree=False):
        """Save accessibility data dictionary to JSON file."""
        import json
        
        exported_data = {
            'crawl_metadata': {
                'total_pages': len(self.accessibility_data),
                'max_depth_used': self.max_depth,
                'max_pages_limit': self.max_pages,
                'crawl_timestamp': time.time(),
                'failed_urls_count': len(self.failed_urls)
            },
            'accessibility_data': self.export_accessibility_dict(include_raw_tree),
            'failed_urls': self.failed_urls
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(exported_data, f, indent=2, ensure_ascii=False)
        
        print(f"Accessibility data dictionary saved to: {file_path}")
        return file_path

    def _extract_main_domain(self, domain):
        """Extract the main domain, removing www prefix and handling subdomains more flexibly."""
        if not domain:
            return domain
            
        # Remove www prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # For domain checking, we'll use the main domain
        # Split by dots and take the last 2 parts for most cases
        parts = domain.split('.')
        if len(parts) >= 2:
            # Handle special cases like .co.uk, .com.au, etc.
            common_tlds = ['co.uk', 'com.au', 'co.jp', 'co.za', 'org.uk', 'net.au']
            domain_suffix = '.'.join(parts[-2:])
            
            if domain_suffix in common_tlds and len(parts) >= 3:
                # For domains like example.co.uk, keep 3 parts
                return '.'.join(parts[-3:])
            else:
                # For regular domains like example.com, keep 2 parts
                return '.'.join(parts[-2:])
        
        return domain
        
    def _is_same_domain(self, url_domain, base_domain):
        """Check if two domains are considered the same for crawling purposes."""
        if not url_domain or not base_domain:
            return False
            
        # Exact match (fastest check first)
        if url_domain == base_domain:
            return True
            
        # Extract main domains for comparison
        url_main = self._extract_main_domain(url_domain)
        base_main = self._extract_main_domain(base_domain)
        
        # Check if main domains match
        if url_main == base_main:
            return True
            
        # Check if url_domain is a subdomain of base_domain
        if url_domain.endswith('.' + base_main):
            return True
            
        # Check if base_domain is a subdomain of url_domain  
        if base_domain.endswith('.' + url_main):
            return True
            
        return False

    def is_valid_url(self, url, base_domain=None):
        """Check if URL is valid for crawling."""
        try:
            parsed = urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Skip non-http(s) URLs
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Skip files we can't process
            excluded_extensions = {
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.zip', '.rar', '.tar', '.gz', '.jpg', '.jpeg', '.png', 
                '.gif', '.svg', '.mp4', '.avi', '.mov', '.mp3', '.wav',
                '.css', '.js', '.xml', '.rss'
            }
            
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in excluded_extensions):
                return False
            
            # Check domain restriction with improved logic
            if self.same_domain_only and base_domain:
                if not self._is_same_domain(parsed.netloc, base_domain):
                    print(f"DOMAIN REJECT: {parsed.netloc} not same as {base_domain}")
                    return False
                else:
                    print(f"DOMAIN ACCEPT: {parsed.netloc} matches {base_domain}")
            
            return True
            
        except Exception:
            return False
    
    def extract_links_from_tree(self, accessibility_tree, base_url):
        """Extract links from accessibility tree."""
        links = set()
        
        try:
            for node in accessibility_tree:
                # Look for links and buttons with URLs
                role = node.get("role", {}).get("value", "")
                
                if role in ["link", "button"]:
                    url = None
                    
                    # Check properties for URL
                    for prop in node.get("properties", []):
                        if prop.get("name") == "url":
                            url = prop.get("value", {}).get("value", "")
                            break
                    
                    # Check attributes for href
                    if not url:
                        for attr in node.get("attributes", []):
                            attr_name = attr.get("name", "")
                            if attr_name in ["href", "url", "data-href"]:
                                url = attr.get("value", "")
                                break
                    
                    # Process found URL
                    if url:
                        # Convert relative URLs to absolute
                        absolute_url = urljoin(base_url, url)
                        
                        # Validate and add
                        base_domain = urlparse(base_url).netloc
                        if self.is_valid_url(absolute_url, base_domain):
                            links.add(absolute_url)
                            
        except Exception as e:
            print(f"Error extracting links: {e}", file=sys.stderr)
        
        return links
    
    def crawl_website(self, start_url, cookies_list=None, show_browser=False, 
                     debug_buttons=False, wait_time=3000, timeout=30000):
        """Crawl website starting from start_url with constraints."""
        
        print(f"Starting crawl from: {start_url}")
        print(f"Constraints: max_depth={self.max_depth}, max_pages={self.max_pages}")
        print(f"Same domain only: {self.same_domain_only}")
        print("-" * 80)
        
        # Initialize crawling
        base_domain = urlparse(start_url).netloc
        self.add_url_to_queue(start_url, 0)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not show_browser)
            
            try:
                # Create context
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                
                # Add cookies if provided
                if cookies_list:
                    context.add_cookies(cookies_list)
                
                while self.url_queue and len(self.crawled_pages) < self.max_pages:
                    current_url, depth = self.url_queue.popleft()
                    
                    # Remove from queued set since we're processing it now
                    self.queued_urls.discard(current_url)
                    
                    # Skip if already visited (double-check)
                    if current_url in self.visited_urls:
                        continue
                    
                    # Skip if depth exceeded
                    if depth > self.max_depth:
                        continue
                    
                    # Mark as visited
                    self.visited_urls.add(current_url)
                    
                    print(f"Crawling [{len(self.crawled_pages)+1}/{self.max_pages}] "
                          f"depth={depth}: {current_url}", file=sys.stderr)
                    
                    try:
                        # Extract accessibility tree for current page
                        page_data = self._extract_single_page(
                            context, current_url, debug_buttons, wait_time, timeout
                        )
                        
                        if page_data:
                            # Add metadata
                            page_data['url'] = current_url
                            page_data['depth'] = depth
                            page_data['crawl_time'] = time.time()
                            
                            # Store in both formats
                            self.crawled_pages.append(page_data)  # For backward compatibility
                            self.accessibility_data[current_url] = page_data  # New dictionary format
                            
                            # Extract links if we haven't reached max depth
                            if depth < self.max_depth:
                                links = self.extract_links_from_tree(
                                    page_data.get('accessibility_tree', []), current_url
                                )
                                
                                # Store found links in the data
                                page_data['links_found'] = list(links)
                                self.accessibility_data[current_url]['links_found'] = list(links)
                                
                                # For depths > 1, randomly sample at most 10 links to prevent exponential growth
                                links_to_queue = list(links)
                                if depth >= 1 and len(links_to_queue) > self.max_links_per_depth:
                                    links_to_queue = random.sample(links_to_queue, self.max_links_per_depth)
                                    print(f"  Randomly sampled {self.max_links_per_depth} links from {len(links)} total links", file=sys.stderr)
                                
                                # Add new unique links to queue
                                added_count = 0
                                for link in links_to_queue:
                                    if self.add_url_to_queue(link, depth + 1):
                                        added_count += 1
                                
                                if depth >= 1 and len(links) > self.max_links_per_depth:
                                    print(f"  Found {len(links)} links, sampled {len(links_to_queue)}, added {added_count} unique to queue (queue size: {len(self.url_queue)})", 
                                          file=sys.stderr)
                                else:
                                    print(f"  Found {len(links)} links, added {added_count} unique to queue (queue size: {len(self.url_queue)})", 
                                          file=sys.stderr)
                        
                        # Rate limiting
                        if self.delay > 0:
                            time.sleep(self.delay)
                            
                    except TimeoutError as e:
                        error_msg = f"Timeout: {str(e)}"
                        print(f"  ⏰ {error_msg}", file=sys.stderr)
                        self.failed_urls.append((current_url, error_msg))
                        continue
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        print(f"  ❌ {error_msg}", file=sys.stderr)
                        self.failed_urls.append((current_url, error_msg))
                        continue
                
                print(f"\nCrawl completed!")
                print(f"Pages successfully crawled: {len(self.crawled_pages)}")
                print(f"Failed URLs: {len(self.failed_urls)}")
                print(f"Remaining URLs in queue: {len(self.url_queue)}")
                print(f"Total unique URLs processed: {len(self.visited_urls)}")
                print(f"Accessibility data stored for {len(self.accessibility_data)} URLs")
                
                return self.crawled_pages
                
            finally:
                browser.close()
    
    def _extract_single_page(self, context, url, debug_buttons, wait_time, timeout):
        """Extract accessibility tree from a single page."""
        page = context.new_page()
        
        try:
            # Set page timeout for all operations
            page.set_default_timeout(timeout)
            
            # Enable accessibility
            client = page.context.new_cdp_session(page)
            client.send("Accessibility.enable")
            
            # Navigate to page
            page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            
            # Wait for dynamic content
            page.wait_for_timeout(wait_time)
            
            # Extract accessibility tree with simple error handling
            try:
                # CDP call for accessibility tree
                result = client.send("Accessibility.getFullAXTree", {})
                accessibility_tree = result["nodes"]
            except Exception as e:
                print(f"CDP call failed: {e}", file=sys.stderr)
                accessibility_tree = []
            
            # Extract button URLs with simple error handling
            button_urls = {}
            try:
                button_urls = page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button, [role="button"]');
                        const result = {};
                        buttons.forEach((btn, index) => {
                            const text = btn.textContent?.trim() || btn.getAttribute('aria-label') || '';
                            if (text) {
                                const attrs = {};
                                for (let attr of btn.attributes) {
                                    if (attr.name.startsWith('data-') || attr.name === 'onclick') {
                                        attrs[attr.name] = attr.value;
                                    }
                                }
                                const link = btn.querySelector('a');
                                if (link && link.href) {
                                    attrs['child_href'] = link.href;
                                }
                                if (Object.keys(attrs).length > 0) {
                                    result[text] = attrs;
                                }
                            }
                        });
                        return result;
                    }
                """)
            except Exception as e:
                print(f"JS evaluation failed: {e}", file=sys.stderr)
                button_urls = {}
            
            # Remove duplicates
            seen_ids = set()
            unique_tree = []
            for node in accessibility_tree:
                if node["nodeId"] not in seen_ids:
                    unique_tree.append(node)
                    seen_ids.add(node["nodeId"])
            
            # Parse to text
            tree_text = parse_accessibility_tree_simple(unique_tree, debug_buttons, button_urls)
            
            # Get page title
            title = page.title()
            
            return {
                'accessibility_tree': unique_tree,
                'tree_text': tree_text,
                'button_urls': button_urls,
                'title': title,
                'url': url
            }
            
        finally:
            page.close()

def save_crawl_results(crawled_pages, output_dir="crawl_results", crawler=None):
    """Save crawl results to files and accessibility dictionary."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Save summary
    summary = {
        'total_pages': len(crawled_pages),
        'crawl_timestamp': time.time(),
        'pages': []
    }
    
    for i, page_data in enumerate(crawled_pages):
        # Save individual page
        page_filename = f"page_{i:04d}_{hash(page_data['url']) % 10000:04d}.txt"
        page_path = output_path / page_filename
        
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(f"URL: {page_data['url']}\n")
            f.write(f"Title: {page_data.get('title', 'N/A')}\n")
            f.write(f"Depth: {page_data.get('depth', 0)}\n")
            f.write(f"Crawl Time: {time.ctime(page_data.get('crawl_time', 0))}\n")
            f.write("-" * 80 + "\n")
            f.write(page_data['tree_text'])
        
        # Add to summary
        summary['pages'].append({
            'url': page_data['url'],
            'title': page_data.get('title', 'N/A'),
            'depth': page_data.get('depth', 0),
            'file': page_filename,
            'crawl_time': page_data.get('crawl_time', 0)
        })
    
    # Save summary
    with open(output_path / "crawl_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Save accessibility data dictionary if crawler is provided
    if crawler and hasattr(crawler, 'accessibility_data'):
        # Save compact version (without raw tree)
        dict_path = output_path / "accessibility_data.json"
        crawler.save_accessibility_dict(dict_path, include_raw_tree=False)
        
        # Save full version with raw accessibility tree
        full_dict_path = output_path / "accessibility_data_full.json"
        crawler.save_accessibility_dict(full_dict_path, include_raw_tree=True)
        
        print(f"Accessibility dictionaries saved:")
        print(f"  Compact: {dict_path}")
        print(f"  Full: {full_dict_path}")
    
    print(f"Crawl results saved to: {output_path}")
    print(f"Total files: {len(crawled_pages) + 1}")
    
    return output_path


def create_sample_config():
    """Create a sample configuration file."""
    sample_config = {
        "url": "https://example.com",
        "cookies": [],
        "show_browser": False,
        "debug_buttons": False,
        "wait_time": 3000,
        "timeout": 60000,
        "output_file": "accessibility_tree.txt",
        "crawl": False,
        "max_depth": 4,
        "max_pages": 2000,
        "crawl_delay": 1.0,
        "max_links_per_depth": 10,
        "same_domain_only": True,
        "output_dir": "crawl_results"
    }
    
    with open("sample_config.json", "w") as f:
        json.dump(sample_config, f, indent=2)
    
    print("Created sample_config.json")
    print("Edit this file with your specific website details and run:")
    print("python get_accessibility_tree_public.py --config sample_config.json")


def main():
    parser = argparse.ArgumentParser(description="Extract accessibility tree from websites")
    parser.add_argument("url", nargs="?", help="URL to extract from")
    parser.add_argument("--cookies", help="Cookie string (format: 'name=value; name2=value2')")
    parser.add_argument("--cookie-file", help="Path to cookie file (.pkl or .json)")
    parser.add_argument("--config", help="Path to configuration JSON file")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--show-browser", action="store_true", help="Show browser window")
    parser.add_argument("--debug-buttons", action="store_true", help="Show debug info for buttons")
    parser.add_argument("--wait-time", type=int, default=3000, help="Wait time for dynamic content (ms)")
    parser.add_argument("--timeout", type=int, default=60000, help="Page load timeout (ms)")
    parser.add_argument("--create-sample-config", action="store_true", help="Create sample configuration file")
    
    # Crawling options
    parser.add_argument("--crawl", action="store_true", help="Enable crawling mode")
    parser.add_argument("--max-depth", type=int, default=4, help="Maximum crawling depth (default: 4)")
    parser.add_argument("--max-pages", type=int, default=2000, help="Maximum number of pages to crawl (default: 2000)")
    parser.add_argument("--crawl-delay", type=float, default=1.0, help="Delay between requests in seconds (default: 1.0)")
    parser.add_argument("--max-links-per-depth", type=int, default=10, help="Maximum links to sample at depth > 0 (default: 10)")
    parser.add_argument("--allow-external", action="store_true", help="Allow crawling external domains")
    parser.add_argument("--output-dir", default="crawl_results", help="Output directory for crawl results")
    
    # Legacy support
    parser.add_argument("--salesforce", action="store_true", help="Extract from Salesforce (requires cookie file)")
    parser.add_argument("--salesforce-debug", action="store_true", help="Extract from Salesforce with debug")
    
    args = parser.parse_args()
    
    if args.create_sample_config:
        create_sample_config()
        return
    
    # Handle legacy Salesforce modes
    if args.salesforce or args.salesforce_debug:
        salesforce_url = "https://your-instance.lightning.force.com/lightning/o/Account/list?filterName=__Recent"
        default_cookie_file = "/path/to/your/data/WEB_PROJECT/webarena/salesforce_cookies.pkl"
        
        cookie_file = args.cookie_file or default_cookie_file
        tree = extract_website_accessibility_tree(
            url=salesforce_url,
            cookie_file=cookie_file,
            debug_buttons=args.salesforce_debug
        )
        print(tree)
        return
    
    # Handle config file
    if args.config:
        try:
            config = load_config_from_file(args.config)
            
            # Check if crawling is enabled in config
            if config.get('crawl', False):
                crawler = WebCrawler(
                    max_depth=config.get('max_depth', 4),
                    max_pages=config.get('max_pages', 2000),
                    delay=config.get('crawl_delay', 1.0),
                    same_domain_only=config.get('same_domain_only', True),
                    max_links_per_depth=config.get('max_links_per_depth', 10)
                )
                
                crawled_pages = crawler.crawl_website(
                    start_url=config['url'],
                    cookies_list=config.get('cookies'),
                    show_browser=config.get('show_browser', False),
                    debug_buttons=config.get('debug_buttons', False),
                    wait_time=config.get('wait_time', 3000),
                    timeout=config.get('timeout', 60000)
                )
                
                # Save results
                output_dir = config.get('output_dir', 'crawl_results')
                save_crawl_results(crawled_pages, output_dir, crawler)
                
                # Print data access info
                print(f"\nAccessibility data available programmatically:")
                print(f"crawler.accessibility_data[url] -> access data for specific URL")
                print(f"crawler.get_all_urls() -> list of all crawled URLs")
                print(f"crawler.export_accessibility_dict() -> clean dictionary export")
                
            else:
                # Single page extraction
                tree = extract_accessibility_tree_with_config(config)
                
                output_file = config.get('output_file')
                if output_file:
                    with open(output_file, 'w') as f:
                        f.write(tree)
                    print(f"Accessibility tree saved to: {output_file}")
                else:
                    print(tree)
            return
            
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Require URL if not using config
    if not args.url:
        parser.print_help()
        sys.exit(1)
    
    # Load cookies
    cookies_list = None
    if args.cookie_file:
        try:
            cookies_list = load_cookies_from_file(args.cookie_file)
        except Exception as e:
            print(f"Error loading cookies: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Handle crawling mode
    if args.crawl:
        crawler = WebCrawler(
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            delay=args.crawl_delay,
            same_domain_only=not args.allow_external,
            max_links_per_depth=args.max_links_per_depth
        )
        
        crawled_pages = crawler.crawl_website(
            start_url=args.url,
            cookies_list=cookies_list,
            show_browser=args.show_browser,
            debug_buttons=args.debug_buttons,
            wait_time=args.wait_time,
            timeout=args.timeout
        )
        
        # Save results (now includes accessibility dictionary)
        save_crawl_results(crawled_pages, args.output_dir, crawler)
        
        # Print usage examples for accessing the data
        print("\n" + "="*60)
        print("DATA ACCESS EXAMPLES:")
        print("="*60)
        print("# Load accessibility data dictionary:")
        print(f'import json')
        print(f'with open("{args.output_dir}/accessibility_data.json") as f:')
        print(f'    data = json.load(f)')
        print(f'accessibility_dict = data["accessibility_data"]')
        print("")
        print("# Access specific URL:")
        print('url_data = accessibility_dict["https://example.com"]')
        print('tree_text = url_data["tree_text"]')
        print("")
        print("# Get all URLs:")
        print('all_urls = list(accessibility_dict.keys())')
        print("")
        print("# Filter by depth:")
        print('depth_0_urls = [url for url, data in accessibility_dict.items() if data["depth"] == 0]')
        print("="*60)
        
        return
    
    # Single page mode
    print(f"URL: {args.url}")
    if args.cookies:
        print(f"Cookie: {args.cookies}")
    if args.cookie_file:
        print(f"Cookie file: {args.cookie_file}")
    print("-" * 50)
    
    tree = extract_accessibility_tree(
        url=args.url,
        cookie=args.cookies,
        cookies_list=cookies_list,
        show_browser=args.show_browser,
        debug_buttons=args.debug_buttons,
        wait_time=args.wait_time,
        timeout=args.timeout
    )
    
    # Save to output file if specified
    if args.output:
        with open(args.output, 'w') as f:
            f.write(tree)
        print(f"Accessibility tree saved to: {args.output}")
    else:
        print(tree)


if __name__ == "__main__":
    main() 