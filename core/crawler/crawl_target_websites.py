#!/usr/bin/env python3
"""
Batch crawler for target websites.
Uses the existing WebCrawler from get_accessibility_tree_public.py to crawl
multiple websites and save results in separate directories.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Import the WebCrawler and related functions from the existing script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from get_accessibility_tree_public import WebCrawler, save_crawl_results

# Example target websites to crawl
TARGET_LINKS = [
    "http://www.espn.com",
    "http://www.mbta.com",
    "http://www.nps.gov",
    "http://www.cvshealth.com",
    "http://www.carnival.com",
    "http://www.underarmour.com",
    "http://www.store.steampowered.com"
]

def get_domain_name(url):
    """Extract clean domain name from URL for directory naming."""
    parsed = urlparse(url)
    domain = parsed.netloc
    # Remove 'www.' prefix if present
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

def crawl_single_website(url, output_base_dir="crawled_websites", 
                        max_depth=4, max_pages=2000, crawl_delay=0.1, 
                        page_timeout=30000, wait_time=3000):
    """Crawl a single website and save results in a dedicated directory.
    
    Args:
        url: URL to crawl
        output_base_dir: Base directory for output
        max_depth: Maximum crawling depth
        max_pages: Maximum pages to crawl
        crawl_delay: Delay between requests in seconds
        page_timeout: Timeout for page operations in milliseconds
        wait_time: Time to wait for dynamic content in milliseconds
    """
    
    domain = get_domain_name(url)
    output_dir = os.path.join(output_base_dir, domain)
    
    print(f"\n{'='*80}")
    print(f"CRAWLING: {url}")
    print(f"Domain: {domain}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*80}")
    
    try:
        # Create the WebCrawler with reasonable limits for batch processing
        crawler = WebCrawler(
            max_depth=max_depth,
            max_pages=max_pages,
            delay=crawl_delay,
            same_domain_only=True,  # Stay within the same domain
            max_links_per_depth=10   # Reasonable number of links per depth
        )
        
        # Start crawling
        start_time = time.time()
        crawled_pages = crawler.crawl_website(
            start_url=url,
            cookies_list=None,
            show_browser=False,
            debug_buttons=False,
            wait_time=wait_time,
            timeout=page_timeout
        )
        end_time = time.time()
        
        # Save results
        save_crawl_results(crawled_pages, output_dir, crawler)
        
        # Create a summary file
        summary = {
            "website": url,
            "domain": domain,
            "crawl_started": datetime.fromtimestamp(start_time).isoformat(),
            "crawl_completed": datetime.fromtimestamp(end_time).isoformat(),
            "duration_seconds": round(end_time - start_time, 2),
            "pages_crawled": len(crawled_pages),
            "total_urls_found": len(crawler.get_all_urls()) if hasattr(crawler, 'get_all_urls') else len(crawled_pages),
            "success": True
        }
        
        with open(os.path.join(output_dir, "crawl_summary.json"), 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✅ Successfully crawled {domain}: {len(crawled_pages)} pages in {summary['duration_seconds']}s")
        return True, summary
        
    except TimeoutError as e:
        print(f"⏰ Timeout crawling {domain}: {str(e)}")
        
        # Save error summary
        os.makedirs(output_dir, exist_ok=True)
        error_summary = {
            "website": url,
            "domain": domain,
            "crawl_started": datetime.now().isoformat(),
            "error": f"Timeout: {str(e)}",
            "error_type": "timeout",
            "success": False
        }
        
        with open(os.path.join(output_dir, "crawl_summary.json"), 'w') as f:
            json.dump(error_summary, f, indent=2)
        
        return False, error_summary
        
    except Exception as e:
        print(f"❌ Error crawling {domain}: {str(e)}")
        
        # Save error summary
        os.makedirs(output_dir, exist_ok=True)
        error_summary = {
            "website": url,
            "domain": domain,
            "crawl_started": datetime.now().isoformat(),
            "error": str(e),
            "error_type": "general",
            "success": False
        }
        
        with open(os.path.join(output_dir, "crawl_summary.json"), 'w') as f:
            json.dump(error_summary, f, indent=2)
        
        return False, error_summary

def main():
    """Main function to crawl all target websites."""
    
    print("Target Website Batch Crawler")
    print(f"Will crawl {len(TARGET_LINKS)} websites")
    print(f"Websites: {', '.join([get_domain_name(url) for url in TARGET_LINKS])}")
    
    # Configuration
    output_base_dir = "crawled_websites"
    max_depth = 4          # Reasonable depth for batch processing
    max_pages = 2000       # Limit pages per site to avoid too much data
    crawl_delay = 0.1      # Delay between requests to be respectful
    page_timeout = 5000   # 30 second timeout for page operations
    wait_time = 1000       # 3 second wait for dynamic content
    
    print(f"\nConfiguration:")
    print(f"- Max depth: {max_depth}")
    print(f"- Max pages per site: {max_pages}")
    print(f"- Crawl delay: {crawl_delay}s")
    print(f"- Page timeout: {page_timeout/1000}s")
    print(f"- Wait time: {wait_time/1000}s")
    print(f"- Output directory: {output_base_dir}")
    
    # Create base output directory
    os.makedirs(output_base_dir, exist_ok=True)
    
    # Track results
    results = []
    successful_crawls = 0
    failed_crawls = 0
    
    total_start_time = time.time()
    
    # Crawl each website
    for i, url in enumerate(TARGET_LINKS, 1):
        print(f"\n[{i}/{len(TARGET_LINKS)}] Processing {url}...")
        
        success, summary = crawl_single_website(
            url, 
            output_base_dir, 
            max_depth, 
            max_pages, 
            crawl_delay,
            page_timeout,
            wait_time
        )
        
        results.append(summary)
        
        if success:
            successful_crawls += 1
        else:
            failed_crawls += 1
        
        # Add a longer delay between websites to be respectful
        if i < len(TARGET_LINKS):
            print(f"Waiting 5 seconds before next website...")
            time.sleep(5)
    
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    # Create overall summary
    overall_summary = {
        "batch_crawl_completed": datetime.fromtimestamp(total_end_time).isoformat(),
        "total_duration_seconds": round(total_duration, 2),
        "total_websites": len(TARGET_LINKS),
        "successful_crawls": successful_crawls,
        "failed_crawls": failed_crawls,
        "configuration": {
            "max_depth": max_depth,
            "max_pages": max_pages,
            "crawl_delay": crawl_delay,
            "page_timeout_ms": page_timeout,
            "wait_time_ms": wait_time,
            "output_directory": output_base_dir
        },
        "individual_results": results
    }
    
    # Save overall summary
    summary_file = os.path.join(output_base_dir, "batch_crawl_summary.json")
    with open(summary_file, 'w') as f:
        json.dump(overall_summary, f, indent=2)
    
    # Print final results
    print(f"\n{'='*80}")
    print("BATCH CRAWL COMPLETED")
    print(f"{'='*80}")
    print(f"Total time: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
    print(f"Successful: {successful_crawls}/{len(TARGET_LINKS)}")
    print(f"Failed: {failed_crawls}/{len(TARGET_LINKS)}")
    print(f"\nResults saved in: {output_base_dir}/")
    print(f"Overall summary: {summary_file}")
    
    # Show directory structure
    print(f"\nDirectory structure:")
    for url in TARGET_LINKS:
        domain = get_domain_name(url)
        domain_dir = os.path.join(output_base_dir, domain)
        if os.path.exists(domain_dir):
            files = os.listdir(domain_dir)
            print(f"  {domain}/ ({len(files)} files)")
    
    print(f"\n📁 All crawled data is available in the '{output_base_dir}' directory")
    print(f"🔍 Each website has its own subdirectory with accessibility trees and metadata")

if __name__ == "__main__":
    main() 