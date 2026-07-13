#!/usr/bin/env python3
"""
Utility functions for working with URL to filename mappings stored in pickle files.
"""

import pickle
import os

def load_url_mapping(pickle_filename='student_com_url_to_filename_mapping.pkl'):
    """Load the URL to filename mapping from a pickle file."""
    try:
        with open(pickle_filename, 'rb') as f:
            url_mapping = pickle.load(f)
        print(f"✅ Loaded {len(url_mapping)} URL mappings from '{pickle_filename}'")
        return url_mapping
    except FileNotFoundError:
        print(f"❌ Pickle file '{pickle_filename}' not found.")
        return None
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return None

def find_filename_by_url(url_mapping, search_url):
    """Find the filename for a specific URL."""
    if url_mapping and search_url in url_mapping:
        return url_mapping[search_url]
    return None

def find_urls_by_filename(url_mapping, search_filename):
    """Find all URLs that come from a specific filename."""
    if not url_mapping:
        return []
    
    matching_urls = [url for url, filename in url_mapping.items() 
                     if filename == search_filename]
    return matching_urls

def search_urls_by_pattern(url_mapping, pattern):
    """Find URLs that contain a specific pattern."""
    if not url_mapping:
        return []
    
    matching_urls = [url for url in url_mapping.keys() 
                     if pattern.lower() in url.lower()]
    return matching_urls

def get_mapping_statistics(url_mapping):
    """Get statistics about the URL mapping."""
    if not url_mapping:
        return None
    
    # Count unique filenames
    unique_files = set(url_mapping.values())
    
    # Count URLs per file
    file_counts = {}
    for filename in url_mapping.values():
        file_counts[filename] = file_counts.get(filename, 0) + 1
    
    stats = {
        'total_urls': len(url_mapping),
        'unique_files': len(unique_files),
        'avg_urls_per_file': len(url_mapping) / len(unique_files) if unique_files else 0,
        'file_counts': file_counts
    }
    
    return stats

def print_mapping_info(pickle_filename='student_com_url_to_filename_mapping.pkl'):
    """Print comprehensive information about the URL mapping."""
    url_mapping = load_url_mapping(pickle_filename)
    
    if not url_mapping:
        return
    
    stats = get_mapping_statistics(url_mapping)
    
    print(f"\n📊 URL Mapping Statistics:")
    print(f"   Total URLs: {stats['total_urls']}")
    print(f"   Unique files: {stats['unique_files']}")
    print(f"   Average URLs per file: {stats['avg_urls_per_file']:.2f}")
    
    print(f"\n📁 Files with most URLs:")
    sorted_files = sorted(stats['file_counts'].items(), key=lambda x: x[1], reverse=True)
    for filename, count in sorted_files[:5]:
        print(f"   {filename}: {count} URLs")
    
    print(f"\n🔗 Sample URL mappings:")
    sample_urls = list(url_mapping.keys())[:5]
    for url in sample_urls:
        print(f"   {url}")
        print(f"   └── {url_mapping[url]}")

def example_usage():
    """Demonstrate how to use the URL mapping utilities."""
    print("🚀 URL Mapping Utilities - Example Usage")
    print("=" * 50)
    
    # Load the mapping
    url_mapping = load_url_mapping()
    
    if not url_mapping:
        print("No mapping available. Please run build_url_tree.py first.")
        return
    
    # Print overall info
    print_mapping_info()
    
    # Example searches
    print(f"\n🔍 Example Searches:")
    
    # Search for URLs containing "login"
    login_urls = search_urls_by_pattern(url_mapping, "login")
    if login_urls:
        print(f"\n   URLs containing 'login' ({len(login_urls)} found):")
        for url in login_urls[:3]:
            print(f"   • {url} -> {url_mapping[url]}")
        if len(login_urls) > 3:
            print(f"   ... and {len(login_urls) - 3} more")
    
    # Find URLs from a specific file (if any)
    if url_mapping:
        sample_filename = list(url_mapping.values())[0]
        urls_from_file = find_urls_by_filename(url_mapping, sample_filename)
        print(f"\n   URLs from '{sample_filename}':")
        for url in urls_from_file[:3]:
            print(f"   • {url}")

if __name__ == "__main__":
    example_usage()