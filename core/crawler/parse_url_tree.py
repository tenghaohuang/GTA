import re
from typing import Dict, List
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent key usage:
    - Convert scheme and domain to lowercase
    - Remove trailing slashes from path
    - Remove default ports (80 for HTTP, 443 for HTTPS)
    - Sort query parameters alphabetically
    - Remove fragment identifiers
    """
    if not url:
        return url
    
    try:
        parsed = urlparse(url.strip())
        
        # Normalize scheme and netloc to lowercase
        scheme = parsed.scheme.lower() if parsed.scheme else ''
        netloc = parsed.netloc.lower() if parsed.netloc else ''
        
        # Remove default ports
        if netloc:
            if ':80' in netloc and scheme == 'http':
                netloc = netloc.replace(':80', '')
            elif ':443' in netloc and scheme == 'https':
                netloc = netloc.replace(':443', '')
        
        # Normalize path - remove trailing slash unless it's the root path
        path = parsed.path
        if path and path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        elif not path:
            path = '/'
        
        # Sort query parameters for consistency
        query = ''
        if parsed.query:
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            sorted_params = sorted(query_params.items())
            query = urlencode(sorted_params, doseq=True)
        
        # Reconstruct URL without fragment
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ''))
        return normalized
    except Exception:
        # If URL parsing fails, return original URL
        return url

def parse_url_tree(file_path: str) -> Dict[str, List[str]]:
    """
    Parse the URL tree structure file and return a dictionary where:
    - Keys are URLs (parent URLs)
    - Values are lists of children URLs
    """
    url_tree = {}
    
    # Stack to track the current hierarchy of paths/URLs
    path_stack = []
    url_stack = []
    
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line_content = line.rstrip()
            
            # Skip empty lines and header sections
            if not line_content or line_content.startswith('=') or 'DOMAIN SUMMARY' in line_content or 'HIERARCHICAL' in line_content:
                continue
                
            # Skip domain summary lines
            if ':' in line_content and 'URLs' in line_content and not line_content.strip().startswith('🌐'):
                continue
                
            # Calculate indentation level
            stripped = line_content.lstrip()
            indent_level = len(line_content) - len(stripped)
            
            # Handle domain roots (🌐)
            if stripped.startswith('🌐'):
                domain_match = re.match(r'🌐 ([^\s]+)', stripped)
                if domain_match:
                    domain = domain_match.group(1)
                    path_stack = ['/']
                    base_url = f"https://{domain}"
                    url_stack = [base_url]
                    normalized_url = normalize_url(base_url)
                    if normalized_url not in url_tree:
                        url_tree[normalized_url] = []
                    continue
            
            # Handle folder nodes (📁)
            elif stripped.startswith('📁'):
                path_match = re.match(r'📁 ([^\s]+)', stripped)
                if path_match:
                    path = path_match.group(1)
                    # Adjust stack based on indentation
                    stack_level = (indent_level - 2) // 2  # Adjust for indentation pattern
                    
                    # Trim stacks to current level
                    if stack_level < len(path_stack):
                        path_stack = path_stack[:stack_level + 1]
                        url_stack = url_stack[:stack_level + 1]
                    
                    # Build full URL for this folder
                    if url_stack:
                        domain_base = url_stack[0].replace('https://', '').replace('http://', '')
                        if path.startswith('/'):
                            current_url = f"https://{domain_base}{path}"
                        else:
                            parent_path = path_stack[-1] if path_stack else '/'
                            if parent_path.endswith('/'):
                                current_url = f"https://{domain_base}{parent_path}{path}"
                            else:
                                current_url = f"https://{domain_base}{parent_path}/{path}"
                        
                        # Add to parent's children if we have a parent
                        if len(url_stack) > 0:
                            parent_url = url_stack[-1]
                            normalized_parent = normalize_url(parent_url)
                            normalized_current = normalize_url(current_url)
                            if normalized_parent not in url_tree:
                                url_tree[normalized_parent] = []
                            if normalized_current not in url_tree[normalized_parent]:
                                url_tree[normalized_parent].append(normalized_current)
                        
                        # Add current URL to tree
                        normalized_current = normalize_url(current_url)
                        if normalized_current not in url_tree:
                            url_tree[normalized_current] = []
                        
                        # Update stacks
                        path_stack.append(path)
                        url_stack.append(current_url)
                    continue
            
            # Handle page nodes (📄)
            elif stripped.startswith('📄'):
                path_match = re.match(r'📄 ([^\s]+)', stripped)
                if path_match:
                    path = path_match.group(1)
                    # Build full URL for this page
                    if url_stack:
                        domain_base = url_stack[0].replace('https://', '').replace('http://', '')
                        if path.startswith('/'):
                            current_url = f"https://{domain_base}{path}"
                        else:
                            parent_path = path_stack[-1] if path_stack else '/'
                            if parent_path.endswith('/'):
                                current_url = f"https://{domain_base}{parent_path}{path}"
                            else:
                                current_url = f"https://{domain_base}{parent_path}/{path}"
                        
                        # Add to parent's children if we have a parent
                        if len(url_stack) > 0:
                            parent_url = url_stack[-1]
                            normalized_parent = normalize_url(parent_url)
                            normalized_current = normalize_url(current_url)
                            if normalized_parent not in url_tree:
                                url_tree[normalized_parent] = []
                            if normalized_current not in url_tree[normalized_parent]:
                                url_tree[normalized_parent].append(normalized_current)
                        
                        # Add current URL to tree
                        normalized_current = normalize_url(current_url)
                        if normalized_current not in url_tree:
                            url_tree[normalized_current] = []
                    continue
            
            # Handle actual URLs (└──)
            elif '└──' in stripped:
                url_match = re.search(r'└── ([^\s]+)', stripped)
                if url_match:
                    actual_url = url_match.group(1)
                    normalized_actual = normalize_url(actual_url)
                    # Add to parent's children if we have a parent
                    if len(url_stack) > 0:
                        parent_url = url_stack[-1]
                        normalized_parent = normalize_url(parent_url)
                        if normalized_parent not in url_tree:
                            url_tree[normalized_parent] = []
                        if normalized_actual not in url_tree[normalized_parent]:
                            url_tree[normalized_parent].append(normalized_actual)
                    
                    # Add actual URL to tree (as leaf node)
                    if normalized_actual not in url_tree:
                        url_tree[normalized_actual] = []
                    continue
    
    return url_tree

def print_sample_results(url_tree: Dict[str, List[str]], num_samples: int = 10):
    """Print a sample of the parsed results"""
    print(f"Total URLs in tree: {len(url_tree)}")
    print(f"\nSample results ({num_samples} entries):")
    print("-" * 50)
    
    count = 0
    for url, children in url_tree.items():
        if count >= num_samples:
            break
        print(f"Parent: {url}")
        print(f"Children ({len(children)}): {children[:3]}{'...' if len(children) > 3 else ''}")
        print()
        count += 1

if __name__ == "__main__":
    # Parse the URL tree
    file_path = "url_tree_url_tree_structure.txt"
    url_tree = parse_url_tree(file_path)
    
    # Print sample results
    print_sample_results(url_tree)
    
    # Save results for further use
    import json
    with open("url_tree_parsed.json", "w") as f:
        json.dump(url_tree, f, indent=2)
    
    print(f"Results saved to url_tree_parsed.json")
    
    # Demonstrate URL normalization
    print("\n" + "="*50)
    print("URL Normalization Examples:")
    print("="*50)
    test_urls = [
        "HTTPS://Example.com/Path/",
        "https://example.com:443/path",
        "http://example.com:80/path?b=2&a=1#fragment",
        "https://example.com/path/../other/",
        "https://Example.COM/Path?a=1&b=2"
    ]
    
    for url in test_urls:
        normalized = normalize_url(url)
        print(f"Original:   {url}")
        print(f"Normalized: {normalized}")
        print()