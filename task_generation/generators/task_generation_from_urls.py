#!/usr/bin/env python3

import json
import argparse
import re
import requests
import time
import json
import csv
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import openai
from datetime import datetime
import os
import sys
from tqdm import tqdm
# Import our utility functions
from AA_utils import get_LLM_response
from aysnc_llm_call import process_llm_batch_calls
from create_retrieval_index import create_task_retrieval_index, save_retrieval_index, load_retrieval_index, retrieve_similar_tasks
def parse_arguments():
    """
    Parse command line arguments for the page classifier script.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Page Content Classifier - Fetch and classify web pages using OpenAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i urls.txt -o results.json --task-source content
  %(prog)s -i salesforce_urls.txt -o salesforce_results.json --timeout 5 --max-content 100000
  %(prog)s --input-file url_tree.txt --output-file classified_pages.json --task-source rationale
  %(prog)s --input-file url_tree.txt --output-file classified_pages.json --task-source rationale_only
        """
    )
    
    # Required arguments
    parser.add_argument(
        '-i', '--input-file',
        type=str,
        default='student_com_url_tree_structure.txt',
        help='Path to the input file containing URLs (default: student_com_url_tree_structure.txt)'
    )
    
    parser.add_argument(
        '-o', '--output-file',
        type=str,
        default='student_com_task_generation_results.json',
        help='Path to the output JSON file (default: student_com_task_generation_results.json)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--task-source',
        type=str,
        choices=['content', 'rationale', 'rationale_only'],
        default='rationale_only',
        help='Source for task generation: content (page content only), rationale (path rationale + page content), or rationale_only (path rationale only, no content fetching) (default: rationale)'
    )
    
    parser.add_argument(
        '--tree-file',
        type=str,
        default=None,
        help='Path to the tree JSON file for rationale extraction (optional, for Salesforce-style JSON trees)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--timeout',
        type=int,
        default=2,
        help='Request timeout in seconds (default: 2)'
    )
    
    parser.add_argument(
        '--max-content',
        type=int,
        default=50000,
        help='Maximum content length to extract from each page (default: 50000)'
    )
    
    parser.add_argument(
        '--max-prompt-content',
        type=int,
        default=15000,
        help='Maximum content length to include in LLM prompt (default: 15000)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()

def extract_urls_from_tree(file_path):
    """
    Extract URLs from the hierarchical url_tree.txt file.
    
    Args:
        file_path (str): Path to the url_tree.txt file
    
    Returns:
        list: List of unique URLs
    """
    urls = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ('http://' in line or 'https://' in line):
                    # Extract URL from line (remove leading dashes and spaces)
                    url_match = re.search(r'https?://[^\s]+', line)
                    if url_match:
                        url = url_match.group(0)
                        # Clean up URL (remove any trailing characters that aren't part of URL)
                        url = re.sub(r'[^\w\-\.\/\?\=\&\:\#]+$', '', url)
                        urls.append(url)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        return []
    
    # Remove duplicates while preserving order
    unique_urls = []
    seen = set()
    for url in urls:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    
    print(f"Extracted {len(unique_urls)} unique URLs from {file_path}")
    return unique_urls

def extract_urls_from_hierarchical_tree(file_path):
    """
    Extract URLs from the student.com hierarchical tree structure file.
    This function also builds a tree structure for rationale extraction and captures page file mappings.
    
    Args:
        file_path (str): Path to the hierarchical tree file
    
    Returns:
        tuple: (list of unique URLs, dict of tree structure, dict of URL to page file mapping)
    """
    urls = []
    tree_structure = {}
    url_to_page_file = {}  # Maps URLs to their page file names
    path_stack = []  # Stack to keep track of current path
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                original_line = line
                line = line.rstrip()
                
                # Skip header and separator lines
                if not line or line.startswith('=') or 'HIERARCHICAL URL TREE' in line or 'DOMAIN SUMMARY' in line:
                    continue
                if 'URLs)' in line and ('📁' in line or '🌐' in line):
                    continue
                    
                # Extract URL if present
                if '└── https://' in line:
                    url_match = re.search(r'https://[^\s]+', line)
                    page_file_match = re.search(r'page_\d+_\d+\.txt', line)
                    
                    if url_match:
                        url = url_match.group(0)
                        # Clean up URL (remove page reference if it got included)
                        url = re.sub(r'\s*->\s*page_\d+_\d+\.txt$', '', url)
                        urls.append(url)
                        
                        # Store page file mapping
                        if page_file_match:
                            page_file = page_file_match.group(0)
                            url_to_page_file[url] = page_file
                        
                        # Build tree structure for rationale
                        current_path = '/'.join(path_stack) if path_stack else '/'
                        tree_structure[url] = {
                            'path': current_path,
                            'depth': len(path_stack),
                            'parent_folders': path_stack.copy()
                        }
                
                # Track folder structure for rationale
                if '📁' in line and '(' in line:
                    # Extract folder path
                    folder_match = re.search(r'📁\s+([^(]+)', line)
                    if folder_match:
                        folder_path = folder_match.group(1).strip()
                        # Calculate depth based on indentation
                        indent = len(original_line) - len(original_line.lstrip())
                        depth = indent // 2  # Assuming 2 spaces per level
                        
                        # Adjust path stack based on depth
                        while len(path_stack) >= depth:
                            path_stack.pop()
                        path_stack.append(folder_path)
                
                # Track page paths
                elif '📄' in line:
                    # Extract page path
                    page_match = re.search(r'📄\s+([^\s]+)', line)
                    if page_match:
                        page_path = page_match.group(1).strip()
                        # Calculate depth based on indentation
                        indent = len(original_line) - len(original_line.lstrip())
                        depth = indent // 2
                        
                        # Adjust path stack for page level
                        while len(path_stack) > depth:
                            path_stack.pop()
    
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        return [], {}, {}
    
    # Remove duplicates while preserving order
    unique_urls = []
    seen = set()
    for url in urls:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    
    print(f"Extracted {len(unique_urls)} unique URLs from {file_path}")
    print(f"Found {len(url_to_page_file)} URL-to-page-file mappings")
    return unique_urls, tree_structure, url_to_page_file

def read_accessibility_tree_content(page_file, accessibility_tree_dir="Agentrek_expriment/student_com", max_content_length=50000):
    """
    Read accessibility tree content from a local file.
    
    Args:
        page_file (str): Name of the page file (e.g., "page_1880_9131.txt")
        accessibility_tree_dir (str): Directory containing the accessibility tree files
        max_content_length (int): Maximum content length to extract
    
    Returns:
        dict: Dictionary with 'success', 'content', 'error' keys
    """
    try:
        file_path = os.path.join(accessibility_tree_dir, page_file)
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'content': None,
                'error': f"Accessibility tree file not found: {file_path}",
                'content_length': 0
            }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Limit content length
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [TRUNCATED]"
        
        return {
            'success': True,
            'content': content,
            'error': None,
            'content_length': len(content)
        }
        
    except Exception as e:
        return {
            'success': False,
            'content': None,
            'error': f"Error reading accessibility tree file: {str(e)}",
            'content_length': 0
        }

def fetch_page_content(url, timeout=2, max_content_length=50000):
    """
    Fetch the text content of a webpage.
    
    Args:
        url (str): URL to fetch
        timeout (int): Request timeout in seconds
        max_content_length (int): Maximum content length to extract
    
    Returns:
        dict: Dictionary with 'success', 'content', 'error' keys
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit content length
        if len(text) > max_content_length:
            text = text[:max_content_length] + "... [TRUNCATED]"
        
        return {
            'success': True,
            'content': text,
            'error': None,
            'status_code': response.status_code,
            'content_length': len(text)
        }
        
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'content': None,
            'error': str(e),
            'status_code': None,
            'content_length': 0
        }
    except Exception as e:
        return {
            'success': False,
            'content': None,
            'error': f"Unexpected error: {str(e)}",
            'status_code': None,
            'content_length': 0
        }

def generate_user_task_prompt(url, page_content, max_prompt_content=15000):
    """
    Create a prompt for an LLM to generate a meaningful, actionable user task based on the HTML web page content.

    Args:
        url (str): The URL of the web page.
        page_content (str): The raw or extracted text content of the web page.
        max_prompt_content (int): Maximum content length to include in prompt.

    Returns:
        str: The formatted prompt for the LLM.
    """
    prompt = f"""
        You are a helpful assistant that creates meaningful, actionable user tasks based on the content of a web page.

        Given the following web page URL and its content, analyze the page and generate a concise, clear, and relevant user task that a typical user might want to accomplish on this page. The task should be specific to the purpose and content of the page, and should be written in natural language as an instruction or goal (e.g., "Sign up for a free trial", "Read the latest blog post", "Download the compliance document", "Contact customer support", "Compare product features", etc.).

        Consider the structure, main elements, and intent of the page. If the page is primarily navigational, suggest a navigation-related task. If it is a content page, suggest a content consumption or interaction task. If the page is a form, suggest a form submission or data entry task. If the page is information-rich, suggest a task to summarize the information or a QA task.

        The URL is: {url}
        The page content is: {page_content[:max_prompt_content]}

        Based on the above, generate one or more meaningful user tasks for this page.

        A meaningful user task should have the following characteristics:
        - It should be specific to the purpose and content of the page.
        - It should be actionable and measurable.
        - It should be written in a way that is easy to understand and follow.
        

        The output should be a list of user tasks and evaluation criteriato the tasks.

        e.g. 
        [
            {{
                "task": "What is the secret to Pepsi's sucess with Google provided services?",
                "evaluation_criteria": Google cloud services are used to provide services to Pepsi.
            }},
            {{
                "task": "Compare prices in casper.com headboards and buy the cheapest one",
                "evaluation_criteria": The cheapest headboard is Super Comfort 332, at price $1000.
            }},
            {{
                "task": "Summarize customer reviews for the Dream Hybrid Mattress (3 most recent reviews).",
                "evaluation_criteria": The most recent reviews are from 2024-01-01 to 2024-01-03. 
            }},
            {{
                "task": "Contact customer support",
                "evaluation_criteria": The user should call the number 1-800-123-4567.
            }}
        ]
        """
    return prompt

def generate_user_task_prompt_from_rationale(url, path_rationale, page_content=None, max_prompt_content=15000):
    """
    Create a prompt for an LLM to generate a meaningful, actionable user task based on the path rationale
    that led to this URL being crawled and the actual page content.

    Args:
        url (str): The URL of the web page.
        path_rationale (str): The rationale explaining why this URL was crawled and chosen.
        page_content (str, optional): The actual text content of the web page.
        max_prompt_content (int): Maximum content length to include in prompt.

    Returns:
        str: The formatted prompt for the LLM.
    """
    # Calculate content lengths to fit within max_prompt_content
    if page_content:
        rationale_limit = max_prompt_content // 2
        content_limit = max_prompt_content // 2
        rationale_text = path_rationale[:rationale_limit]
        content_text = page_content[:content_limit]
        
        page_content_section = f"""
        
        The actual page content is: {content_text}"""
    else:
        rationale_text = path_rationale[:max_prompt_content]
        page_content_section = """
        
        Note: No actual page content is available. Base your task generation purely on the navigation path and rationale provided above."""
    
    if page_content:
        intro_text = """You are a helpful assistant that simulates a real human user following a specific navigation path and rationale to generate meaningful, actionable user tasks based on the crawling rationale and actual page content.

        Imagine you are a real human user who has navigated to this web page following the exact same path and reasoning that the crawler used. Put yourself in the shoes of someone who would naturally arrive at this page through the described navigation journey.

        Given the following web page URL, the detailed rationale explaining why this page was selected and crawled (including the navigation path and reasoning), and the actual page content, think like a human user who followed this exact path and generate tasks that such a user would realistically want to accomplish."""
    else:
        intro_text = """You are a helpful assistant that simulates a real human user following a specific navigation path and rationale to generate meaningful, actionable user tasks based purely on the crawling rationale (no page content available).

        Imagine you are a real human user who has navigated to this web page following the exact same path and reasoning that the crawler used. Put yourself in the shoes of someone who would naturally arrive at this page through the described navigation journey.

        Given the following web page URL and the detailed rationale explaining why this page was selected and crawled (including the navigation path and reasoning), think like a human user who followed this exact path and generate tasks that such a user would realistically want to accomplish based on their expectations from the navigation journey."""
    
    prompt = f"""
        {intro_text}

        The crawling rationale provides insight into:
        - Why this page was considered important or salient
        - What navigation steps led to this page
        - What specific content or functionality was expected to be found
        - How this page fits into the overall website structure

        The actual page content provides the specific details of what is actually available on the page, allowing for more grounded and actionable tasks.

        As you simulate being a human user who followed this navigation path, consider:
        - What would motivate a real person to follow this exact navigation journey?
        - What goals or needs would drive someone to click through this specific sequence of pages?
        - What would a human user naturally want to do once they arrive at this destination page?
        - How would the navigation context influence what tasks they'd want to accomplish?

        The URL is: {url}
        
        The crawling path and rationale is: {rationale_text}

        Here is the actual page content: {page_content_section}

        Now, simulate being a real human user who followed this exact navigation path and rationale. Generate user tasks that such a person would naturally want to accomplish on this page, considering both their journey to get here and what they find once they arrive.

        A meaningful user task should have the following characteristics:
        - It should reflect what a real human user would naturally want to do after following this navigation path
        - It should be motivated by realistic human goals and needs that align with the crawling rationale
        - It should be specific to what a user would expect to find based on their navigation journey
        - It should be actionable and measurable from a human user's perspective
        - It should leverage both the navigation context and the actual available content
        - It should be written as if a real person with genuine intent would perform these tasks
        The output should be a list of user tasks and evaluation criteria for the tasks.

        Example format:
        [
            {{
                "task": "How can I use Salesforce Agentforce to build and deploy a custom AI agent for automating support tasks using Agent Builder?",
                "evaluation_criteria": "To build and deploy a custom AI agent using Salesforce Agentforce, follow this Salesforce-specific process:

                1. Use Agentforce to Define Your Agent
                   Start in the Agent Builder to define your agent's purpose (e.g. Sales Dev Rep, Service Agent). 
                   Salesforce provides templates tailored to common business roles.

                2. Leverage Salesforce Data
                   Train your agent using chat logs, support tickets, or CRM data already within Salesforce. 
                   Use Salesforce tools to clean and label this data.

                3. Select and Fine-Tune Models
                   Salesforce supports pre-trained models (like GPT, BERT) that you can fine-tune with your 
                   org's data directly in the platform.

                4. Train Within the Salesforce Ecosystem
                   Configure training parameters and run training jobs using Salesforce's built-in ML 
                   infrastructure and Agentforce tools.

                5. Test with Salesforce Workflows
                   Validate your agent in sandbox environments using A/B tests, unit tests, and real user 
                   flows via Salesforce UI.

                6. Deploy Natively in Salesforce
                   Deploy your AI agent across Salesforce Clouds (e.g. Sales, Service) or embed it into 
                   digital channels like chat or email. Monitor and refine via built-in analytics and 
                   feedback tools."
            }},
            {{
                "task": "Additional task example...",
                "evaluation_criteria": "Additional evaluation criteria..."
            }}
        ]
        """
    return prompt

def backtrack_to_root(child_node, tree_structure, parent_key='parent'):
    """
    Backtrack from a child node to the root node.
    
    Args:
        child_node: The starting node (could be a key or node object)
        tree_structure: The tree data structure (dict)
        parent_key: The key used to identify parent in node data (default: 'parent')
    
    Returns:
        list: Path from child to root (child first, root last)
    """
    path = []
    current = child_node
    
    while current is not None:
        path.append(current)
        
        # Get parent from tree structure
        if current in tree_structure:
            current = tree_structure[current].get(parent_key)
        else:
            # Current node not found in tree, stop backtracking
            break
    
    return path

def backtrack_to_root_reverse(child_node, tree_structure, parent_key='parent'):
    """
    Backtrack from a child node to the root node, returning path from root to child.
    
    Args:
        child_node: The starting node (could be a key or node object)
        tree_structure: The tree data structure (dict)
        parent_key: The key used to identify parent in node data (default: 'parent')
    
    Returns:
        list: Path from root to child (root first, child last)
    """
    path = backtrack_to_root(child_node, tree_structure, parent_key)
    return path[::-1]  # Reverse the path

def backtrack_with_children_structure(child_node, tree_structure):
    """
    Backtrack when tree structure uses 'children' relationships.
    This function finds the parent by searching through all nodes.
    
    Args:
        child_node: The starting node
        tree_structure: The tree data structure where each node has 'children' list
    
    Returns:
        list: Path from child to root (child first, root last)
    """
    # First, build a parent mapping from the children relationships
    parent_map = {}
    
    for node, node_data in tree_structure.items():
        if 'children' in node_data:
            for child in node_data['children']:
                parent_map[child] = node
    
    # Now backtrack using the parent mapping
    path = []
    current = child_node
    
    while current is not None:
        path.append(current)
        current = parent_map.get(current)
    
    return path

def backtrack_url_tree(child_url, tree_data):
    """
    Specific function for backtracking URL tree structures like in your notebook.
    
    Args:
        child_url: The URL to start backtracking from
        tree_data: The tree data structure from your JSON
    
    Returns:
        list: Path from child URL to root URL
    """
    if 'tree' not in tree_data:
        return [child_url]
    
    tree_structure = tree_data['tree']
    path = []
    current = child_url
    
    while current is not None:
        path.append(current)
        
        if current in tree_structure:
            # Look for parent in the tree structure
            current_data = tree_structure[current]
            
            # Find parent by looking at depth and checking other nodes
            current_depth = current_data.get('depth', 0)
            if current_depth > 0:
                # Find parent with depth one less
                for url, data in tree_structure.items():
                    if (data.get('depth', 0) == current_depth - 1 and 
                        'children' in data and 
                        current in data['children']):
                        current = url
                        break
                else:
                    # No parent found
                    current = None
            else:
                # We're at root (depth 0)
                current = None
        else:
            # Current URL not found in tree
            current = None
    
    return path

import json

def get_rationales_from_hierarchical_path(url, tree_structure):
    """
    Generate rationale from the hierarchical path structure for student.com URLs.
    
    Args:
        url (str): The URL to generate rationale for
        tree_structure (dict): Tree structure mapping URLs to their path information
    
    Returns:
        str: Generated rationale based on URL path structure
    """
    if url not in tree_structure:
        return f"❌ URL not found in tree structure: {url}"
    
    url_info = tree_structure[url]
    parent_folders = url_info.get('parent_folders', [])
    depth = url_info.get('depth', 0)
    
    # Parse the URL to understand its purpose
    parsed_url = urlparse(url)
    path_parts = [part for part in parsed_url.path.split('/') if part]
    
    # Generate rationale based on URL structure and hierarchy
    rationale_parts = []
    
    # Add navigation context
    if depth > 0:
        rationale_parts.append(f"NAVIGATION PATH (Depth {depth}):")
        for i, folder in enumerate(parent_folders):
            rationale_parts.append(f"  Level {i+1}: {folder}")
    
    # Analyze URL components for purpose
    purpose_analysis = []
    
    # Country/region detection
    if len(path_parts) > 0 and len(path_parts[0]) == 2:
        purpose_analysis.append(f"GEOGRAPHIC FOCUS: Targeting {path_parts[0].upper()} region")
    
    # City detection
    if len(path_parts) > 1:
        city = path_parts[1].replace('-', ' ').title()
        purpose_analysis.append(f"CITY FOCUS: {city}")
    
    # Category detection
    category_mapping = {
        'p': 'Student accommodation/property listings',
        'u': 'University/educational institution information',
        'articles': 'Educational content and guides',
        'about': 'Company information',
        'agent': 'Partner/agent services',
        'help': 'Support and assistance'
    }
    
    for part in path_parts:
        if part in category_mapping:
            purpose_analysis.append(f"CONTENT TYPE: {category_mapping[part]}")
            break
    
    # Query parameter analysis
    if parsed_url.query:
        query_params = parsed_url.query.split('&')
        for param in query_params:
            if 'previousPage' in param:
                purpose_analysis.append(f"USER JOURNEY: Referred from {param.split('=')[1].replace('%20', ' ')}")
    
    # Fragment analysis
    if parsed_url.fragment:
        purpose_analysis.append(f"SPECIFIC SECTION: Targeting #{parsed_url.fragment}")
    
    # Combine all rationale parts
    if purpose_analysis:
        rationale_parts.append("PURPOSE ANALYSIS:")
        rationale_parts.extend(f"  {analysis}" for analysis in purpose_analysis)
    
    # Add URL structure explanation
    rationale_parts.append(f"URL STRUCTURE: {url}")
    rationale_parts.append(f"  Base domain: {parsed_url.netloc}")
    rationale_parts.append(f"  Path depth: {len(path_parts)} levels")
    
    # Generate user intent rationale
    intent_rationale = generate_user_intent_rationale(url, path_parts, parsed_url)
    if intent_rationale:
        rationale_parts.append("LIKELY USER INTENT:")
        rationale_parts.append(f"  {intent_rationale}")
    
    return "\n".join(rationale_parts)

def generate_user_intent_rationale(url, path_parts, parsed_url):
    """
    Generate a rationale about likely user intent based on URL structure.
    
    Args:
        url (str): The full URL
        path_parts (list): URL path components
        parsed_url: Parsed URL object
    
    Returns:
        str: User intent rationale
    """
    intent_patterns = []
    
    # Geographic + category patterns
    if len(path_parts) >= 3:
        if path_parts[2] == 'p':
            intent_patterns.append("User is searching for student accommodation/properties")
        elif path_parts[2] == 'u':
            intent_patterns.append("User is researching universities or educational institutions")
    
    # Article patterns
    if 'articles' in path_parts:
        if any(keyword in url.lower() for keyword in ['save', 'money', 'budget']):
            intent_patterns.append("User seeking financial advice for student life")
        elif any(keyword in url.lower() for keyword in ['eat', 'food']):
            intent_patterns.append("User looking for dining/food guidance")
        else:
            intent_patterns.append("User seeking educational content or guidance")
    
    # Query parameter patterns
    if 'previousPage=SRP' in url:
        intent_patterns.append("User browsing from search results page")
    elif 'previousPage=Property' in url:
        intent_patterns.append("User navigating between property listings")
    elif 'share=' in url:
        intent_patterns.append("User engaging in social sharing")
    
    # Fragment patterns
    if parsed_url.fragment:
        if 'comment' in parsed_url.fragment:
            intent_patterns.append(f"User viewing specific comment or discussion")
        else:
            intent_patterns.append(f"User targeting specific section: {parsed_url.fragment}")
    
    return " | ".join(intent_patterns) if intent_patterns else "General browsing and information gathering"

def get_rationales_along_path(test_url, json_file_path=None):
    """
    Return a concatenated string of all the rationales along the path from child to root.
    Shows why each URL in the path was chosen/crawled.
    
    Args:
        test_url (str): The URL to start backtracking from
        json_file_path (str): Path to the JSON file containing the tree data
    Returns:
        str: Concatenated rationales along the path
    """
    if json_file_path is None:
        json_file_path = '/path/to/your/data/Agent_Vista/salient_crawl_results_www.salesforce.com_20250704_225237.json'
    
    try:
        # Load the JSON data
        with open(json_file_path, 'r') as f:
            salesforce_data = json.load(f)
        
        tree_structure = salesforce_data['tree']
        
        if test_url not in tree_structure:
            return f"❌ URL not found in tree: {test_url}"
        
        # Get the path from child to root
        path = backtrack_url_tree(test_url, salesforce_data)
        
        rationale_strings = []
        for i, url in enumerate(path):
            url_data = tree_structure[url]
            depth = url_data.get('depth', 'unknown')
            rationale_entry = [f"STEP {i+1}: {url}", f"Depth: {depth}"]
            rationale_found = False
            rationale_text = ""
            # Find the rationale for this URL in its parent's salient links
            if i < len(path) - 1:  # Not the root
                parent_url = path[i+1]
                parent_data = tree_structure[parent_url]
                if 'salient_links' in parent_data:
                    for link in parent_data['salient_links']:
                        if link['url'] == url and 'rationale' in link:
                            rationale_text = f"WHY THIS URL WAS CHOSEN: {link['rationale']}"
                            rationale_found = True
                            break
            # If no rationale found in parent's salient links, look for other rationale fields
            if not rationale_found:
                if 'rationale' in url_data:
                    rationale_text = f"PAGE RATIONALE: {url_data['rationale']}"
                elif 'crawl_reason' in url_data:
                    rationale_text = f"CRAWL REASON: {url_data['crawl_reason']}"
                elif 'description' in url_data:
                    rationale_text = f"DESCRIPTION: {url_data['description']}"
                else:
                    rationale_text = "No rationale found for this URL"
            rationale_entry.append(rationale_text)
            if i < len(path) - 1:
                rationale_entry.append("(parent)")
            else:
                rationale_entry.append("(root)")
            rationale_strings.append(" | ".join(rationale_entry))
        return "\n".join(rationale_strings)
    except FileNotFoundError:
        return f"❌ File not found: {json_file_path}"
    except Exception as e:
        return f"❌ Error: {e}"



def main():
    """
    Main function to orchestrate the page classification process.
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Validate input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    
    # Validate tree file exists if using rationale mode and tree file is specified
    if (args.task_source == 'rationale' or args.task_source == 'rationale_only') and args.tree_file and not os.path.exists(args.tree_file):
        print(f"Error: Tree file '{args.tree_file}' not found")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if args.verbose:
        print(f"Input file: {args.input_file}")
        print(f"Output file: {args.output_file}")
        print(f"Task source: {args.task_source}")
        if (args.task_source == 'rationale' or args.task_source == 'rationale_only') and args.tree_file:
            print(f"Tree file: {args.tree_file}")
        elif args.task_source == 'rationale' or args.task_source == 'rationale_only':
            print("Using hierarchical tree structure from input file for rationales")
        print(f"Timeout: {args.timeout}s")
        print(f"Max content length: {args.max_content}")
        print(f"Max prompt content: {args.max_prompt_content}")
    
    # Determine file type and extract URLs accordingly
    with open(args.input_file, 'r', encoding='utf-8') as f:
        first_lines = f.read(1000)
    
    # Check if it's a hierarchical tree structure file
    if 'HIERARCHICAL URL TREE STRUCTURE' in first_lines or '📁' in first_lines or '📄' in first_lines:
        print("Detected hierarchical tree structure format")
        urls, tree_structure, url_to_page_file = extract_urls_from_hierarchical_tree(args.input_file)
        is_hierarchical = True
        has_local_files = len(url_to_page_file) > 0
        print(f"Local accessibility tree files available: {has_local_files}")
    else:
        print("Detected simple URL list format")
        urls = extract_urls_from_tree(args.input_file)
        tree_structure = {}
        url_to_page_file = {}
        is_hierarchical = False
        has_local_files = False
    
    print(f"Found {len(urls)} URLs")
    
    if args.verbose:
        print("First 10 URLs:")
        for i, url in enumerate(urls[:10]):
            print(f"{i+1}. {url}")
    
    # Process URLs
    payload = []
    page_contents = []
    
    if args.task_source == 'content':
        # Content-based task generation (original behavior)
        for url in tqdm(urls, desc="Processing URLs"):
            # Fetch the page content - prefer local accessibility tree files if available
            if has_local_files and url in url_to_page_file:
                page_content = read_accessibility_tree_content(url_to_page_file[url], max_content_length=args.max_content)
                if args.verbose and page_content['success']:
                    print(f"Using local accessibility tree for {url}")
            else:
                # Fall back to HTTP request if no local file available
                page_content = fetch_page_content(url, timeout=args.timeout, max_content_length=args.max_content)
                if args.verbose and page_content['success']:
                    print(f"Fetched content via HTTP for {url}")
            
            if not page_content['success']:
                if args.verbose:
                    print(f"Failed to get page content for {url}: {page_content['error']}")
                continue
            else:
                page_content = page_content['content']
                page_contents.append(page_content)
            
            # Generate user task prompt
            task_gen_prompt = generate_user_task_prompt(url, page_content, args.max_prompt_content)
            example = {
                "messages": [
                    {"role": "user", "content": task_gen_prompt}
                ]
            }
            payload.append(example)
    
    elif args.task_source == 'rationale':
        # Rationale-based task generation with page content
        for url in tqdm(urls, desc="Processing URLs (rationale + content mode)"):
            # Get path rationale for this URL
            if is_hierarchical:
                path_rationale = get_rationales_from_hierarchical_path(url, tree_structure)
            else:
                path_rationale = get_rationales_along_path(url, args.tree_file)
            
            if "❌" in path_rationale:
                if args.verbose:
                    print(f"Failed to get rationale for {url}: {path_rationale}")
                continue
            
            # Fetch the actual page content for better grounding - prefer local accessibility tree files
            if has_local_files and url in url_to_page_file:
                page_content_result = read_accessibility_tree_content(url_to_page_file[url], max_content_length=args.max_content)
                if args.verbose and page_content_result['success']:
                    print(f"Using local accessibility tree for {url}")
            else:
                # Fall back to HTTP request if no local file available
                page_content_result = fetch_page_content(url, timeout=args.timeout, max_content_length=args.max_content)
                if args.verbose and page_content_result['success']:
                    print(f"Fetched content via HTTP for {url}")
            
            if not page_content_result['success']:
                if args.verbose:
                    print(f"Failed to get page content for {url}: {page_content_result['error']}")
                # Use only rationale if page content fetch fails
                actual_page_content = None
                combined_content = f"RATIONALE:\n{path_rationale}\n\nPAGE CONTENT: Failed to get page content"
            else:
                actual_page_content = page_content_result['content']
                combined_content = f"RATIONALE:\n{path_rationale}\n\nPAGE CONTENT:\n{actual_page_content}"
            
            # Store combined rationale and page content for output
            page_contents.append(combined_content)
            
            # Generate user task prompt from rationale and page content
            task_gen_prompt = generate_user_task_prompt_from_rationale(
                url, path_rationale, actual_page_content, args.max_prompt_content
            )
            example = {
                "messages": [
                    {"role": "user", "content": task_gen_prompt}
                ]
            }
            payload.append(example)
    
    elif args.task_source == 'rationale_only':
        # Rationale-only task generation
        for url in tqdm(urls, desc="Processing URLs (rationale only mode)"):
            # Get path rationale for this URL
            if is_hierarchical:
                path_rationale = get_rationales_from_hierarchical_path(url, tree_structure)
            else:
                path_rationale = get_rationales_along_path(url, args.tree_file)
            
            if "❌" in path_rationale:
                if args.verbose:
                    print(f"Failed to get rationale for {url}: {path_rationale}")
                continue
            
            # Store rationale only for output
            page_contents.append(f"RATIONALE:\n{path_rationale}")
            
            # Generate user task prompt from rationale only
            task_gen_prompt = generate_user_task_prompt_from_rationale(
                url, path_rationale, None, args.max_prompt_content # Pass None for page_content
            )
            example = {
                "messages": [
                    {"role": "user", "content": task_gen_prompt}
                ]
            }
            payload.append(example)
    
    if args.verbose:
        print(f"Processing {len(payload)} pages with LLM...")
    
    # Process LLM batch calls
    results = process_llm_batch_calls(payload)
    
    # Prepare output data
    output_data = []
    for url, result, page_content in zip(urls, results, page_contents):
        output_data.append({
            "url": url,
            "result": result['model_output'],
            "page_content": page_content,
            "task_source": args.task_source,
            "input_format": "hierarchical_tree" if is_hierarchical else "simple_url_list",
            "used_local_accessibility_tree": has_local_files and url in url_to_page_file,
            "page_file": url_to_page_file.get(url, None) if has_local_files else None
        })
    
    # Save results to output file
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"Results saved to {args.output_file}")
    print(f"Processed {len(output_data)} pages successfully using {args.task_source} mode")
    if has_local_files:
        local_files_used = sum(1 for item in output_data if item.get('used_local_accessibility_tree', False))
        print(f"Used local accessibility tree files for {local_files_used} out of {len(output_data)} pages")
    

if __name__ == "__main__":
    main()

