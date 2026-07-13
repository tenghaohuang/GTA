#!/usr/bin/env python3
"""
Cookie utility for the accessibility tree extractor.
Helps convert between different cookie formats and manage cookie files.

Usage:
    python cookie_utils.py convert "session=abc123; user=john" --output cookies.json
    python cookie_utils.py browser-export --help
"""

import json
import pickle
import argparse
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta


def parse_browser_cookies(cookie_string: str, domain: str) -> list:
    """Parse browser-exported cookie string into Playwright format."""
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
                'domain': domain,
                'path': '/',
                'expires': -1,  # Session cookie
                'httpOnly': False,
                'secure': True if domain.startswith('https') else False,
                'sameSite': 'Lax'
            })
    
    return cookies


def convert_cookies(input_format: str, output_format: str, cookies_data, domain: str = None):
    """Convert cookies between different formats."""
    
    # Parse input
    if input_format == 'string':
        if not domain:
            raise ValueError("Domain is required when converting from string format")
        cookies = parse_browser_cookies(cookies_data, domain)
    elif input_format == 'json':
        if isinstance(cookies_data, str):
            cookies = json.loads(cookies_data)
        else:
            cookies = cookies_data
    elif input_format == 'pkl':
        if isinstance(cookies_data, str):
            with open(cookies_data, 'rb') as f:
                cookies = pickle.load(f)
        else:
            cookies = cookies_data
    else:
        raise ValueError(f"Unsupported input format: {input_format}")
    
    # Convert to output format
    if output_format == 'json':
        return json.dumps(cookies, indent=2)
    elif output_format == 'pkl':
        return cookies  # Return as-is for pickle saving
    elif output_format == 'string':
        # Convert back to browser string format
        parts = []
        for cookie in cookies:
            parts.append(f"{cookie['name']}={cookie['value']}")
        return "; ".join(parts)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


def create_cookie_template(domain: str) -> dict:
    """Create a template cookie entry."""
    return {
        "name": "cookie_name",
        "value": "cookie_value",
        "domain": domain,
        "path": "/",
        "expires": -1,
        "httpOnly": False,
        "secure": True,
        "sameSite": "Lax"
    }


def validate_cookies(cookies: list) -> list:
    """Validate and fix common cookie issues."""
    validated = []
    
    for cookie in cookies:
        # Ensure required fields
        if 'name' not in cookie or 'value' not in cookie:
            print(f"Warning: Skipping invalid cookie: {cookie}")
            continue
        
        # Set defaults for missing fields
        validated_cookie = {
            'name': cookie['name'],
            'value': cookie['value'],
            'domain': cookie.get('domain', ''),
            'path': cookie.get('path', '/'),
            'expires': cookie.get('expires', -1),
            'httpOnly': cookie.get('httpOnly', False),
            'secure': cookie.get('secure', True),
            'sameSite': cookie.get('sameSite', 'Lax')
        }
        
        validated.append(validated_cookie)
    
    return validated


def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or parsed.netloc


def main():
    parser = argparse.ArgumentParser(description="Cookie utilities for accessibility tree extractor")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert cookies between formats')
    convert_parser.add_argument('input', help='Input cookies (string or file path)')
    convert_parser.add_argument('--input-format', choices=['string', 'json', 'pkl'], default='string',
                              help='Input format')
    convert_parser.add_argument('--output-format', choices=['string', 'json', 'pkl'], default='json',
                              help='Output format')
    convert_parser.add_argument('--domain', help='Domain for string format cookies')
    convert_parser.add_argument('--output', help='Output file path')
    
    # Template command
    template_parser = subparsers.add_parser('template', help='Create cookie template')
    template_parser.add_argument('domain', help='Domain for the template')
    template_parser.add_argument('--output', help='Output file path')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate cookie file')
    validate_parser.add_argument('cookie_file', help='Cookie file to validate')
    validate_parser.add_argument('--fix', action='store_true', help='Fix common issues')
    
    # Browser export help
    browser_parser = subparsers.add_parser('browser-export', help='Instructions for browser cookie export')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'convert':
        try:
            # Determine if input is file or string
            input_path = Path(args.input)
            if input_path.exists():
                if args.input_format == 'json':
                    with open(input_path, 'r') as f:
                        input_data = json.load(f)
                elif args.input_format == 'pkl':
                    input_data = str(input_path)
                else:
                    with open(input_path, 'r') as f:
                        input_data = f.read().strip()
            else:
                input_data = args.input
            
            # Convert
            result = convert_cookies(args.input_format, args.output_format, input_data, args.domain)
            
            # Output
            if args.output:
                output_path = Path(args.output)
                if args.output_format == 'pkl':
                    with open(output_path, 'wb') as f:
                        pickle.dump(result, f)
                else:
                    with open(output_path, 'w') as f:
                        f.write(result)
                print(f"Converted cookies saved to: {args.output}")
            else:
                if args.output_format != 'pkl':
                    print(result)
                else:
                    print("Pickle format requires --output file path")
                    
        except Exception as e:
            print(f"Error converting cookies: {e}")
    
    elif args.command == 'template':
        template = [create_cookie_template(args.domain)]
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(template, f, indent=2)
            print(f"Cookie template saved to: {args.output}")
        else:
            print(json.dumps(template, indent=2))
    
    elif args.command == 'validate':
        try:
            # Load cookies
            cookie_path = Path(args.cookie_file)
            if cookie_path.suffix == '.json':
                with open(cookie_path, 'r') as f:
                    cookies = json.load(f)
            elif cookie_path.suffix == '.pkl':
                with open(cookie_path, 'rb') as f:
                    cookies = pickle.load(f)
            else:
                print("Unsupported file format. Use .json or .pkl")
                return
            
            print(f"Loaded {len(cookies)} cookies from {args.cookie_file}")
            
            # Validate
            if args.fix:
                validated = validate_cookies(cookies)
                print(f"Validated {len(validated)} cookies")
                
                # Save fixed version
                fixed_path = cookie_path.with_stem(f"{cookie_path.stem}_fixed")
                if cookie_path.suffix == '.json':
                    with open(fixed_path, 'w') as f:
                        json.dump(validated, f, indent=2)
                else:
                    with open(fixed_path, 'wb') as f:
                        pickle.dump(validated, f)
                print(f"Fixed cookies saved to: {fixed_path}")
            else:
                # Just check
                for i, cookie in enumerate(cookies):
                    issues = []
                    if 'name' not in cookie:
                        issues.append("missing name")
                    if 'value' not in cookie:
                        issues.append("missing value")
                    if 'domain' not in cookie:
                        issues.append("missing domain")
                    
                    if issues:
                        print(f"Cookie {i}: {', '.join(issues)}")
                
                print("Validation complete")
                
        except Exception as e:
            print(f"Error validating cookies: {e}")
    
    elif args.command == 'browser-export':
        print("Browser Cookie Export Instructions:")
        print("=" * 40)
        print()
        print("Chrome/Edge:")
        print("1. Open Developer Tools (F12)")
        print("2. Go to Application/Storage tab")
        print("3. Click on Cookies in the left panel")
        print("4. Select your domain")
        print("5. Copy cookie values manually or use browser extensions")
        print()
        print("Firefox:")
        print("1. Open Developer Tools (F12)")
        print("2. Go to Storage tab")
        print("3. Expand Cookies")
        print("4. Select your domain")
        print("5. Copy cookie values")
        print()
        print("Cookie String Format:")
        print('session_id=abc123; csrf_token=xyz789; user_pref=dark')
        print()
        print("Then convert using:")
        print('python cookie_utils.py convert "your_cookie_string" --domain example.com --output cookies.json')


if __name__ == "__main__":
    main() 