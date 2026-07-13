import os
import openai
import json
import matplotlib.pyplot as plt
import base64
import io
from PIL import Image
openai.api_key = os.environ["OPENAI_API_KEY"]
openai.organization = os.environ.get("OPENAI_ORGANIZATION")
# client = openai.OpenAI()

def plot_image_with_code(image_code):
    img_data = base64.b64decode(image_code)
    img = Image.open(io.BytesIO(img_data))
    plt.figure(figsize=(15,10))
    plt.imshow(img)
    plt.axis('off')

def plot_image_with_id(task_id):
    with open(f'/path/to/your/data/WEB_PROJECT/agent-workflow-memory/webarena_submission/{task_id}.json', 'rb') as f:
        data = json.load(f)
        image_code = data[2]['content']
        plot_image_with_code(image_code)
        return image_code

def get_LLM_response(prompt):
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    return response.choices[0].message.content

def get_LLM_response_with_image(prompt, image_code):
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",  # Specify the GPT-4o model
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_code}",  # For Base64
                            # Or: "url": image_url, # For URL # or "low" or "auto" for image quality/detail
                        }
                    }
                ]
            }
        ],
        temperature=0.9,
        max_tokens=300, # Adjust as needed
    )
    return response.choices[0].message.content

import subprocess
import tempfile
import os
from pathlib import Path

def take_website_screenshot(url, output_filename, 
                          width=1920, height=1080, 
                          javascript_delay=1000,
                          custom_css="img { min-height: 200px; }",
                          load_error_handling="ignore",
                          cookies=None,
                          cookie_jar_path=None,
                          window_status=None,
                          retry_attempts=3):
    """
    Take a screenshot of a website using wkhtmltoimage
    
    Args:
        url (str): The URL to screenshot
        output_filename (str): Output filename for the screenshot
        width (int): Viewport width (default: 1920)
        height (int): Viewport height (default: 1080)
        javascript_delay (int): Delay in milliseconds for JavaScript (default: 1000)
        custom_css (str): Custom CSS to apply (default: makes images min 200px height)
        load_error_handling (str): How to handle load errors (default: "ignore")
        cookies (dict): Dictionary of cookie name-value pairs (default: None)
        cookie_jar_path (str): Path to cookie jar file to load/save cookies (default: None)
        window_status (str): Wait for window.status to be set to this value (default: None)
        retry_attempts (int): Number of retry attempts if screenshot fails (default: 3)
    
    Returns:
        bool: True if successful, False otherwise
    
    Examples:
        # Basic usage
        take_website_screenshot("https://example.com", "screenshot.png")
        
        # With cookies and longer delay for slow-loading pages
        cookies = {"session_id": "abc123", "user_token": "xyz789"}
        take_website_screenshot("https://example.com", "screenshot.png", 
                               cookies=cookies, javascript_delay=5000)
        
        # With window status waiting (page sets window.status = "ready" when loaded)
        take_website_screenshot("https://example.com", "screenshot.png", 
                               window_status="ready", javascript_delay=10000)
    """
    
    for attempt in range(retry_attempts):
        try:
            # Create a temporary CSS file for the custom styles
            with tempfile.NamedTemporaryFile(mode='w', suffix='.css', delete=False) as css_file:
                css_file.write(custom_css)
                css_file_path = css_file.name
            
            # Build the wkhtmltoimage command - use full path for upgraded version
            cmd = [
                '/usr/local/bin/wkhtmltoimage',
                '--javascript-delay', str(javascript_delay),
                '--load-error-handling', load_error_handling,
                '--user-style-sheet', css_file_path,
                '--width', str(width),
                '--height', str(height),
                '--no-stop-slow-scripts',  # Don't timeout slow scripts
                '--enable-javascript',  # Ensure JavaScript is enabled
                '--format', 'png',  # Explicitly set format
            ]
            
            # Add window status waiting if specified
            if window_status:
                cmd.extend(['--window-status', window_status])
            
            # Add cookie support
            if cookies:
                for cookie_name, cookie_value in cookies.items():
                    cmd.extend(['--cookie', cookie_name, str(cookie_value)])
            
            if cookie_jar_path:
                cmd.extend(['--cookie-jar', cookie_jar_path])
            
            # Add URL and output filename
            cmd.extend([url, output_filename])
            
            print(f"Attempt {attempt + 1}/{retry_attempts} - Running command: {' '.join(cmd)}")
            
            # Execute the command with longer timeout for slow pages
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=120)  # 120 second timeout for slow pages
            
            # Clean up the temporary CSS file
            os.unlink(css_file_path)
            
            if result.returncode == 0:
                print(f"✅ Screenshot saved successfully: {output_filename}")
                if os.path.exists(output_filename):
                    file_size = os.path.getsize(output_filename)
                    print(f"   File size: {file_size:,} bytes")
                    
                    # Check if the file is too small (might indicate loading issues)
                    if file_size < 1000:  # Less than 1KB might indicate a problem
                        print(f"⚠️  Warning: Screenshot file is very small ({file_size} bytes)")
                        print(f"   This might indicate the page didn't load properly")
                        if attempt < retry_attempts - 1:
                            print(f"   Retrying with longer delay...")
                            javascript_delay = int(javascript_delay * 1.5)  # Increase delay for retry
                            continue
                return True
            else:
                print(f"❌ Error taking screenshot (attempt {attempt + 1}):")
                print(f"   Return code: {result.returncode}")
                if result.stderr:
                    print(f"   Error output: {result.stderr}")
                if result.stdout:
                    print(f"   Standard output: {result.stdout}")
                
                if attempt < retry_attempts - 1:
                    print(f"   Retrying in 2 seconds...")
                    import time
                    time.sleep(2)
                    javascript_delay = int(javascript_delay * 1.5)  # Increase delay for retry
                    continue
                else:
                    return False
                
        except subprocess.TimeoutExpired:
            print(f"❌ Command timed out after 120 seconds (attempt {attempt + 1})")
            if attempt < retry_attempts - 1:
                print(f"   Retrying with longer delay...")
                javascript_delay = int(javascript_delay * 1.5)
                continue
            else:
                return False
        except FileNotFoundError:
            print("❌ wkhtmltoimage not found. Please install wkhtmltopdf package:")
            print("   Ubuntu/Debian: sudo apt-get install wkhtmltopdf")
            print("   CentOS/RHEL: sudo yum install wkhtmltopdf")
            print("   macOS: brew install wkhtmltopdf")
            return False
        except Exception as e:
            print(f"❌ Unexpected error (attempt {attempt + 1}): {str(e)}")
            if attempt < retry_attempts - 1:
                print(f"   Retrying...")
                continue
            else:
                return False
        finally:
            # Ensure temporary file is cleaned up even if there's an error
            if 'css_file_path' in locals() and os.path.exists(css_file_path):
                try:
                    os.unlink(css_file_path)
                except:
                    pass
    
    return False

# Example usage:
# take_website_screenshot("http://your-internal-host:7780/women/bottoms-women.html", "screenshot_with_images_python.png")

def extract_cookies_from_browser_format(cookie_data):
    """
    Extract cookies from browser/automation tool format to simple name-value pairs
    
    Args:
        cookie_data (dict): Cookie data from browser dev tools or automation tools
                           Expected format: {"cookies": [{"name": "...", "value": "...", ...}, ...]}
    
    Returns:
        dict: Simple dictionary of cookie name-value pairs
    """
    cookies = {}
    if isinstance(cookie_data, dict) and 'cookies' in cookie_data:
        for cookie in cookie_data['cookies']:
            if 'name' in cookie and 'value' in cookie:
                cookies[cookie['name']] = cookie['value']
    return cookies

def take_screenshot_with_your_cookies():
    """
    Example function showing how to use the provided cookies with enhanced loading handling
    """
    # Example cookie data (replace with your own values)
    cookie_data = {
        "cookies": [
            {
                "name": "admin",
                "value": "<REDACTED_SESSION_TOKEN>",
                "domain": "your-internal-host",
                "path": "/admin",
                "expires": 1750918684.058699,
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax"
            },
            {
                "name": "known_sign_in",
                "value": "<REDACTED_SESSION_TOKEN>",
                "domain": "your-internal-host",
                "path": "/",
                "expires": 1751768284.65463,
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax"
            },
            {
                "name": "_gitlab_session",
                "value": "<REDACTED_SESSION_TOKEN>",
                "domain": "your-internal-host",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax"
            }
        ],
        "origins": []
    }
    
    # Extract simple cookie name-value pairs
    cookies = extract_cookies_from_browser_format(cookie_data)
    print("Extracted cookies:", cookies)
    
    # Try the enhanced screenshot function for slow-loading pages
    print("\n🚀 Using enhanced screenshot function for slow-loading pages...")
    success = take_screenshot_slow_loading_page(
        "http://your-internal-host:7780/women/bottoms-women.html",
        "screenshot_with_cookies_enhanced.png",
        cookies=cookies,
        max_wait_time=10000  # 10 seconds max wait time
    )
    
    if not success:
        print("\n🔄 Enhanced method failed, trying manual approach...")
        # Fallback to manual approach with very long delay
        success = take_website_screenshot(
            "http://your-internal-host:7780/women/bottoms-women.html",
            "screenshot_with_cookies_fallback.png",
            cookies=cookies,
            javascript_delay=15000,  # 15 second delay
            retry_attempts=3
        )
    
    return success

def take_screenshot_slow_loading_page(url, output_filename, cookies=None, max_wait_time=15000):
    """
    Specialized function for taking screenshots of slow-loading pages.
    Tries multiple strategies with increasing wait times.
    
    Args:
        url (str): The URL to screenshot
        output_filename (str): Output filename for the screenshot
        cookies (dict): Dictionary of cookie name-value pairs (default: None)
        max_wait_time (int): Maximum wait time in milliseconds (default: 15000 = 15 seconds)
    
    Returns:
        bool: True if successful, False otherwise
    """
    strategies = [
        # Strategy 1: Standard approach with longer delay
        {
            'javascript_delay': max_wait_time,
            'window_status': None,
            'description': 'Standard approach with extended delay'
        },
        # Strategy 2: Wait for window status (if page supports it)
        {
            'javascript_delay': max_wait_time,
            'window_status': 'complete',
            'description': 'Waiting for window.status = "complete"'
        },
        # Strategy 3: Even longer delay with no script timeout
        {
            'javascript_delay': max_wait_time * 2,
            'window_status': None,
            'description': 'Extended delay with no script timeouts'
        }
    ]
    
    print(f"🔄 Attempting to capture slow-loading page: {url}")
    print(f"   Max wait time: {max_wait_time/1000:.1f} seconds")
    
    for i, strategy in enumerate(strategies, 1):
        print(f"\n📸 Strategy {i}/{len(strategies)}: {strategy['description']}")
        
        success = take_website_screenshot(
            url=url,
            output_filename=output_filename,
            javascript_delay=strategy['javascript_delay'],
            window_status=strategy['window_status'],
            cookies=cookies,
            retry_attempts=2,  # Fewer retries per strategy since we have multiple strategies
            width=1920,
            height=1080
        )
        
        if success:
            print(f"✅ Successfully captured page using strategy {i}")
            return True
        else:
            print(f"❌ Strategy {i} failed, trying next approach...")
    
    print(f"❌ All strategies failed to capture the page")
    return False

def organize_urls_in_tree(df, output_txt_path, url_column='Page URL'):
    """
    Organize all page URLs from a dataframe in a hierarchical tree structure.
    
    Args:
        df: DataFrame containing URLs
        output_txt_path (str): Path to save the URL tree text file
        url_column (str): Name of the column containing URLs (default: 'Page URL')
    
    Returns:
        dict: The tree structure as a dictionary
    """
    from urllib.parse import urlparse, urljoin
    from collections import defaultdict
    
    # Get all unique page URLs from the dataframe
    all_urls = df[url_column].dropna().unique().tolist()
    
    print(f"Processing {len(all_urls)} unique URLs...")
    
    # Helper: Normalize URL (remove trailing slash and handle query params)
    def normalize_url(url):
        return url.rstrip('/')
    
    # Create a mapping of path-only URLs to full URLs with query params
    def get_base_path(url):
        """Extract just the scheme, netloc, and path (no query/fragment)"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
    
    # Build mappings
    base_path_to_urls = defaultdict(list)
    for url in all_urls:
        base_path = get_base_path(url)
        base_path_to_urls[base_path].append(url)
    
    # For each base path, pick one representative URL (prefer shorter query strings)
    representative_urls = {}
    for base_path, urls in base_path_to_urls.items():
        # Pick the URL with the shortest query string as representative
        representative = min(urls, key=lambda x: len(urlparse(x).query))
        representative_urls[base_path] = representative
    
    print(f"Reduced to {len(representative_urls)} representative URLs")
    
    # Build parent-child relationships using base paths
    url_set = set(representative_urls.keys())
    parent_map = {}
    
    for base_path in url_set:
        parsed = urlparse(base_path)
        path_parts = [p for p in parsed.path.split('/') if p]  # Remove empty parts
        
        # Try to find the closest parent by removing path segments
        parent = None
        for i in range(len(path_parts)-1, 0, -1):
            parent_path = '/'.join(path_parts[:i])
            if parent_path:
                parent_url = f"{parsed.scheme}://{parsed.netloc}/{parent_path}"
            else:
                parent_url = f"{parsed.scheme}://{parsed.netloc}"
            
            parent_url = normalize_url(parent_url)
            if parent_url in url_set and parent_url != base_path:
                parent = parent_url
                break
        
        parent_map[base_path] = parent
    
    # Build the tree using representative URLs
    tree = defaultdict(list)
    for child_path, parent_path in parent_map.items():
        child_url = representative_urls[child_path]
        if parent_path:
            parent_url = representative_urls[parent_path]
            tree[parent_url].append(child_url)
        else:
            tree[None].append(child_url)
    
    # Add all other URLs that share the same base path
    final_tree = defaultdict(list)
    for parent, children in tree.items():
        for child in children:
            child_base = get_base_path(child)
            # Add all URLs that share this base path
            all_child_urls = base_path_to_urls[child_base]
            final_tree[parent].extend(all_child_urls)
    
    # Also add root URLs
    for root_url in tree[None]:
        root_base = get_base_path(root_url)
        all_root_urls = base_path_to_urls[root_base]
        final_tree[None].extend(all_root_urls)
    
    # Remove duplicates
    for parent in final_tree:
        final_tree[parent] = list(set(final_tree[parent]))
    
    # Print the URL tree into a txt file
    def print_tree_to_file(tree, root, file, level=0, visited=None):
        if visited is None:
            visited = set()
        
        # Sort children for consistent output
        children = sorted(tree.get(root, []))
        
        for node in children:
            if node in visited:
                continue  # Avoid cycles
            visited.add(node)
            file.write("- " * level + f"- {node}\n")
            print_tree_to_file(tree, node, file, level+1, visited)
    
    with open(output_txt_path, "w", encoding="utf-8") as f:
        print_tree_to_file(final_tree, None, f)

    
    return dict(final_tree)
