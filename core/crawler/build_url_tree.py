#!/usr/bin/env python3
"""
URL Tree Builder Script

DESCRIPTION:
    Extract URLs from txt files and build a hierarchical URL tree structure.
    Analyzes website structure by organizing URLs by domain and path hierarchy.

INPUT SPECIFICATIONS:
    - Input Folder: Directory containing .txt files
    - File Format: Each .txt file must have its first line in format: "URL: <url>"
    - File Encoding: UTF-8 text files with .txt extension
    - URL Format: Valid URLs with scheme, domain, and optional path/query/fragment

    Example input file content:
        URL: https://example.com/category/subcategory/page.html?param=value
        Additional content can follow...

OUTPUT SPECIFICATIONS:
    1. Console Output:
        - Processing status and statistics
        - Domain summary with URL counts
        - Hierarchical tree structure display

    2. Files Generated:
        a) <prefix>_url_tree_structure.txt
           - Human-readable hierarchical tree structure
           - Domain statistics and URL organization
           
        b) url_tree_analysis.json
           - Machine-readable JSON with complete tree structure
           - Summary statistics and metadata
           - Structure: {"summary": {...}, "tree": {...}, "total_urls": int}
           
        c) <prefix>_url_to_filename_mapping.pkl
           - Python pickle file mapping URLs to source filenames
           - Format: {url: filename, ...}
           
        d) Mermaid Diagram Code (returned by main())
           - Text representation of tree as Mermaid graph
           - Limited to max_nodes for readability

    3. Data Structures:
        - URL Tree: Nested dictionaries with 'urls' and 'children' keys
        - URL Stats: Dictionary mapping domains to URL counts
        - URL Mapping: Dictionary mapping URLs to source filenames

USAGE:
    python build_url_tree.py INPUT_FOLDER [OPTIONS]
    
    Required:
        INPUT_FOLDER        Path to directory containing .txt files with URLs
    
    Optional:
        --prefix, -p        Prefix for output files (default: url_tree)
        --output-dir, -o    Output directory (default: current directory)
        --max-nodes, -m     Maximum nodes in Mermaid diagram (default: 50)
        --no-pickle         Skip generating pickle file
        --no-json           Skip generating JSON file
        --no-txt            Skip generating text tree file
        --quiet, -q         Suppress non-essential output
        --help, -h          Show help message
    
    Examples:
        python build_url_tree.py /path/to/txt/files
        python build_url_tree.py /path/to/txt/files --prefix mysite --max-nodes 100
        python build_url_tree.py /path/to/txt/files --output-dir ./results --quiet

DEPENDENCIES:
    - Python 3.6+
    - Standard library modules only (os, re, argparse, urllib.parse, collections, json, pickle)
"""

import os
import re
import argparse
from urllib.parse import urlparse
from collections import defaultdict
import json
import pickle
from typing import List, Dict, Any, Tuple, Optional, TextIO

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Extract URLs from txt files and build a hierarchical URL tree structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python build_url_tree.py /path/to/txt/files
    python build_url_tree.py /path/to/txt/files --prefix mysite --max-nodes 100
    python build_url_tree.py /path/to/txt/files --output-dir ./results
        """
    )
    
    parser.add_argument(
        'input_folder',
        help='Path to directory containing .txt files with URLs'
    )
    
    parser.add_argument(
        '--prefix', '-p',
        default='url_tree',
        help='Prefix for output files (default: url_tree)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='.',
        help='Output directory for generated files (default: current directory)'
    )
    
    parser.add_argument(
        '--max-nodes', '-m',
        type=int,
        default=50,
        help='Maximum nodes in Mermaid diagram (default: 50)'
    )
    
    parser.add_argument(
        '--no-pickle',
        action='store_true',
        help='Skip generating pickle file'
    )
    
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='Skip generating JSON file'
    )
    
    parser.add_argument(
        '--no-txt',
        action='store_true',
        help='Skip generating text tree file'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )
    
    return parser.parse_args()

def extract_urls_from_folder(folder_path: str, quiet: bool = False) -> List[Dict[str, str]]:
    """Extract URLs from the first line of all txt files in the folder.
    
    Args:
        folder_path (str): Path to directory containing .txt files
        quiet (bool): Suppress non-essential output
        
    Returns:
        List[Dict[str, str]]: List of dictionaries with 'url' and 'file' keys
    """
    urls = []
    
    # Get all txt files in the folder
    txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    txt_files.sort()  # Sort for consistent processing
    
    if not quiet:
        print(f"Found {len(txt_files)} txt files in {folder_path}")
    
    for filename in txt_files:
        file_path = os.path.join(folder_path, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                # Extract URL from "URL: https://..." format
                if first_line.startswith('URL: '):
                    url = first_line[5:]  # Remove "URL: " prefix
                    urls.append({
                        'url': url,
                        'file': filename
                    })
                elif not quiet:
                    print(f"Warning: {filename} doesn't start with 'URL: '")
        except Exception as e:
            if not quiet:
                print(f"Error reading {filename}: {e}")
    
    return urls

def build_url_tree(urls: List[Dict[str, str]]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Build a hierarchical tree structure from URLs.
    
    Args:
        urls (List[Dict[str, str]]): List of URL dictionaries from extract_urls_from_folder
        
    Returns:
        Tuple[Dict[str, Any], Dict[str, int]]: 
            - Tree structure (nested dicts with 'urls' and 'children' keys)
            - URL statistics (domain -> count mapping)
    """
    tree = defaultdict(lambda: {'urls': [], 'children': defaultdict(lambda: {'urls': [], 'children': defaultdict(dict)})})
    url_stats = defaultdict(int)
    
    for item in urls:
        url = item['url']
        parsed = urlparse(url)
        
        # Count domains
        domain = parsed.netloc
        url_stats[domain] += 1
        
        # Build path hierarchy
        path = parsed.path.strip('/')
        path_parts = [p for p in path.split('/') if p] if path else []
        
        # Navigate/create the tree structure
        current_level = tree[domain]
        
        # If this is a root path, add it to the domain's root
        if not path_parts:
            current_level['urls'].append({
                'url': url,
                'file': item['file'],
                'query': parsed.query,
                'fragment': parsed.fragment,
                'path': '/'
            })
        else:
            # Navigate through the path parts to create hierarchy
            for i, part in enumerate(path_parts):
                if part not in current_level['children']:
                    current_level['children'][part] = {'urls': [], 'children': defaultdict(lambda: {'urls': [], 'children': defaultdict(dict)})}
                
                # If this is the final part, add the URL here
                if i == len(path_parts) - 1:
                    current_level['children'][part]['urls'].append({
                        'url': url,
                        'file': item['file'],
                        'query': parsed.query,
                        'fragment': parsed.fragment,
                        'path': '/' + '/'.join(path_parts)
                    })
                else:
                    # Move to next level
                    current_level = current_level['children'][part]
    
    return tree, url_stats

def create_url_to_filename_mapping(urls: List[Dict[str, str]]) -> Dict[str, str]:
    """Create a mapping from URLs to their source filenames.
    
    Args:
        urls (List[Dict[str, str]]): List of URL dictionaries
        
    Returns:
        Dict[str, str]: Mapping from URL to filename
    """
    url_to_filename = {}
    
    for item in urls:
        url = item['url']
        filename = item['file']
        url_to_filename[url] = filename
    
    return url_to_filename

def save_url_mapping_to_pickle(url_mapping: Dict[str, str], pickle_filename: str = 'url_to_filename_mapping.pkl', quiet: bool = False) -> bool:
    """Save the URL to filename mapping to a pickle file.
    
    Args:
        url_mapping (Dict[str, str]): URL to filename mapping
        pickle_filename (str): Output pickle file path
        quiet (bool): Suppress non-essential output
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(pickle_filename, 'wb') as f:
            pickle.dump(url_mapping, f)
        if not quiet:
            print(f"📦 URL to filename mapping saved to '{pickle_filename}'")
            print(f"   Contains {len(url_mapping)} URL mappings")
        return True
    except Exception as e:
        if not quiet:
            print(f"Error saving pickle file: {e}")
        return False

def load_url_mapping_from_pickle(pickle_filename: str = 'url_to_filename_mapping.pkl') -> Optional[Dict[str, str]]:
    """Load the URL to filename mapping from a pickle file.
    
    Args:
        pickle_filename (str): Input pickle file path
        
    Returns:
        Optional[Dict[str, str]]: URL to filename mapping, or None if failed
    """
    try:
        with open(pickle_filename, 'rb') as f:
            url_mapping = pickle.load(f)
        print(f"📦 Loaded {len(url_mapping)} URL mappings from '{pickle_filename}'")
        return url_mapping
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        return None

def print_tree_structure(tree: Dict[str, Any], url_stats: Dict[str, int], output_file: Optional[TextIO] = None) -> None:
    """Print the URL tree in a readable format and optionally save to file.
    
    Args:
        tree (Dict[str, Any]): Hierarchical URL tree structure
        url_stats (Dict[str, int]): Domain statistics
        output_file (Optional[TextIO]): File object to write to (in addition to console)
        
    Returns:
        None: Prints to console and optionally writes to file
    """
    def write_line(text=""):
        print(text)
        if output_file:
            output_file.write(text + "\n")
    
    def print_tree_node(node, indent_level=0, path_name=""):
        """Recursively print tree nodes with proper indentation."""
        indent = "  " * indent_level
        
        # Print URLs at this level
        for item in node['urls']:
            query_str = f"?{item['query']}" if item['query'] else ""
            fragment_str = f"#{item['fragment']}" if item['fragment'] else ""
            write_line(f"{indent}📄 {item['path']}{query_str}{fragment_str}")
            write_line(f"{indent}   └── {item['url']} -> {item['file']}")
        
        # Print children
        for child_name, child_node in sorted(node['children'].items()):
            child_path = f"{path_name}/{child_name}" if path_name else f"/{child_name}"
            total_urls = count_urls_in_subtree(child_node)
            
            if total_urls > 0:
                write_line(f"{indent}📁 {child_path}/ ({total_urls} URLs)")
                print_tree_node(child_node, indent_level + 1, child_path)
    
    def count_urls_in_subtree(node):
        """Count total URLs in a subtree."""
        count = len(node['urls'])
        for child in node['children'].values():
            count += count_urls_in_subtree(child)
        return count
    
    write_line("\n" + "="*80)
    write_line("HIERARCHICAL URL TREE STRUCTURE")
    write_line("="*80)
    
    write_line(f"\nDOMAIN SUMMARY:")
    write_line("-" * 40)
    for domain, count in sorted(url_stats.items(), key=lambda x: x[1], reverse=True):
        write_line(f"{domain}: {count} URLs")
    
    write_line(f"\nHIERARCHICAL TREE STRUCTURE:")
    write_line("-" * 40)
    
    for domain in sorted(tree.keys()):
        write_line(f"\n🌐 {domain} ({url_stats[domain]} URLs)")
        print_tree_node(tree[domain], 1)

def create_mermaid_diagram(tree: Dict[str, Any], url_stats: Dict[str, int], max_nodes: int = 50) -> str:
    """Create a Mermaid diagram for the URL tree.
    
    Args:
        tree (Dict[str, Any]): Hierarchical URL tree structure
        url_stats (Dict[str, int]): Domain statistics
        max_nodes (int): Maximum number of nodes to include in diagram
        
    Returns:
        str: Mermaid diagram code as text
    """
    diagram_lines = ["graph TD"]
    node_counter = 0
    
    def count_urls_in_subtree(node):
        """Count total URLs in a subtree."""
        count = len(node['urls'])
        for child in node['children'].values():
            count += count_urls_in_subtree(child)
        return count
    
    def add_tree_nodes(node, parent_id, path_prefix="", depth=0):
        """Recursively add nodes to the Mermaid diagram."""
        nonlocal node_counter
        
        if node_counter >= max_nodes or depth > 3:  # Limit depth to avoid clutter
            return
        
        # Add direct URLs at this level
        for item in node['urls']:
            if node_counter >= max_nodes:
                break
            url_id = f"U{node_counter}"
            path_display = item['path']
            if len(path_display) > 25:
                path_display = path_display[:22] + "..."
            
            query_str = f"?{item['query'][:10]}..." if item['query'] and len(item['query']) > 10 else f"?{item['query']}" if item['query'] else ""
            diagram_lines.append(f'    {url_id}["{path_display}{query_str}"]')
            diagram_lines.append(f'    {parent_id} --> {url_id}')
            node_counter += 1
        
        # Add child directories
        for child_name, child_node in sorted(list(node['children'].items())[:5]):  # Limit to 5 children
            if node_counter >= max_nodes:
                break
            
            child_id = f"D{node_counter}"
            child_path = f"{path_prefix}/{child_name}" if path_prefix else f"/{child_name}"
            url_count = count_urls_in_subtree(child_node)
            
            if url_count > 0:
                path_display = child_path if len(child_path) < 25 else child_path[:22] + "..."
                diagram_lines.append(f'    {child_id}["{path_display}/<br/>({url_count} URLs)"]')
                diagram_lines.append(f'    {parent_id} --> {child_id}')
                node_counter += 1
                
                add_tree_nodes(child_node, child_id, child_path, depth + 1)
    
    # Add root node
    diagram_lines.append('    Root["URL Tree Structure"]')
    
    # Add domain nodes
    for domain in sorted(url_stats.keys()):
        if node_counter >= max_nodes:
            break
        domain_id = f"D{node_counter}"
        diagram_lines.append(f'    {domain_id}["{domain}<br/>({url_stats[domain]} URLs)"]')
        diagram_lines.append(f'    Root --> {domain_id}')
        node_counter += 1
        
        # Add tree structure for this domain
        add_tree_nodes(tree[domain], domain_id, "", 0)
    
    return "\n".join(diagram_lines)

def main(args: Optional[argparse.Namespace] = None) -> str:
    """Main execution function.
    
    Processes URLs from the specified folder and generates output files.
    
    Args:
        args (Optional[argparse.Namespace]): Command line arguments. If None, will parse from sys.argv
    
    Returns:
        str: Mermaid diagram code for the URL tree
        
    Side Effects:
        - Creates output files in specified directory
        - Prints progress and results to console (unless quiet mode)
    """
    if args is None:
        args = parse_arguments()
    
    # Validate input folder
    if not os.path.exists(args.input_folder):
        print(f"Error: Input folder '{args.input_folder}' does not exist")
        return ""
    
    if not os.path.isdir(args.input_folder):
        print(f"Error: '{args.input_folder}' is not a directory")
        return ""
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Extract URLs
    if not args.quiet:
        print("Extracting URLs from txt files...")
    urls = extract_urls_from_folder(args.input_folder, args.quiet)
    if not args.quiet:
        print(f"Extracted {len(urls)} URLs")
    
    if not urls:
        print("No URLs found in the input folder")
        return ""
    
    # Build tree
    if not args.quiet:
        print("Building URL tree...")
    tree, url_stats = build_url_tree(urls)
    
    # Create URL to filename mapping
    if not args.quiet:
        print("Creating URL to filename mapping...")
    url_mapping = create_url_to_filename_mapping(urls)
    
    generated_files = []
    
    # Save URL mapping to pickle file
    if not args.no_pickle:
        pickle_filename = os.path.join(args.output_dir, f'{args.prefix}_url_to_filename_mapping.pkl')
        if save_url_mapping_to_pickle(url_mapping, pickle_filename, args.quiet):
            generated_files.append(pickle_filename)
    
    # Print results and save to txt file
    if not args.no_txt:
        txt_output_path = os.path.join(args.output_dir, f'{args.prefix}_url_tree_structure.txt')
        with open(txt_output_path, 'w', encoding='utf-8') as txt_file:
            print_tree_structure(tree, url_stats, txt_file if not args.quiet else None)
        generated_files.append(txt_output_path)
    elif not args.quiet:
        # Print to console only if not saving to file
        print_tree_structure(tree, url_stats)
    
    # Save detailed results to JSON
    if not args.no_json:
        def convert_tree_to_dict(node):
            """Convert tree node to JSON-serializable dictionary."""
            result = {
                'urls': node['urls'],
                'children': {}
            }
            for name, child in node['children'].items():
                result['children'][name] = convert_tree_to_dict(child)
            return result
        
        json_tree = {}
        for domain, domain_tree in tree.items():
            json_tree[domain] = convert_tree_to_dict(domain_tree)
        
        output_data = {
            'summary': dict(url_stats),
            'tree': json_tree,
            'total_urls': len(urls),
            'generation_args': {
                'input_folder': args.input_folder,
                'prefix': args.prefix,
                'max_nodes': args.max_nodes
            }
        }
        
        json_output_path = os.path.join(args.output_dir, f'{args.prefix}_analysis.json')
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        generated_files.append(json_output_path)
    
    # Print summary of generated files
    if not args.quiet and generated_files:
        print(f"\n📊 Generated {len(generated_files)} output file(s):")
        for file_path in generated_files:
            print(f"   📄 {file_path}")
    
    # Create Mermaid diagram
    mermaid_code = create_mermaid_diagram(tree, url_stats, args.max_nodes)
    
    # Demonstrate loading the pickle file
    if not args.no_pickle and not args.quiet:
        pickle_filename = os.path.join(args.output_dir, f'{args.prefix}_url_to_filename_mapping.pkl')
        if os.path.exists(pickle_filename):
            print("\n🔍 Demonstrating pickle file usage:")
            loaded_mapping = load_url_mapping_from_pickle(pickle_filename)
            if loaded_mapping and len(loaded_mapping) > 0:
                # Show a few examples
                example_urls = list(loaded_mapping.keys())[:3]
                for url in example_urls:
                    print(f"   {url} -> {loaded_mapping[url]}")
                if len(loaded_mapping) > 3:
                    print(f"   ... and {len(loaded_mapping) - 3} more mappings")
    
    return mermaid_code

if __name__ == "__main__":
    try:
        args = parse_arguments()
        mermaid_diagram = main(args)
        if mermaid_diagram and not args.quiet:
            print(f"\n🌳 URL Tree visualization ready!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import sys
        sys.exit(1)
