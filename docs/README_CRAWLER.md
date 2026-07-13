# Website Crawler for Extensive URL Discovery

This crawler is optimized to discover and crawl **many URLs** from each target website, not just single pages.

## Key Features

- **Deep Crawling**: Goes 4 levels deep into website structure
- **High Volume**: Crawls up to 2000 pages per website  
- **Extensive URL Discovery**: Samples up to 50 links per depth level
- **Fast Crawling**: 0.1 second delay between requests
- **Separate Storage**: Each website gets its own directory
- **Accessibility Trees**: Extracts full accessibility information for each page

## Configuration

The crawler is configured for maximum URL discovery:

- `max_depth=4` - Goes deep into website structure
- `max_pages=2000` - High limit to capture many URLs
- `max_links_per_depth=50` - Discovers many links at each level
- `crawl_delay=0.1` - Fast crawling (0.1s between requests)
- `same_domain_only=True` - Stays within each target domain

## Usage

### 1. Test with a few websites first:
```bash
cd Agentrek_expriment
python test_crawler.py
```

### 2. Run the full crawler on all 20 target websites:
```bash
python crawl_target_websites.py
```

### 3. Analyze results to see URL discovery statistics:
```bash
python analyze_crawl_results.py
```

## Target Websites

The crawler will process these 20 websites:
- yellowpages.com
- facebook.com  
- last.fm
- ebay.com
- drugs.com
- new.mta.info
- resy.com
- mail.google.com
- spothero.com
- ticketcenter.com
- dmv.virginia.gov
- espn.com
- amazon.com
- wikipedia.org
- mbta.com
- nps.gov
- cvshealth.com
- carnival.com
- underarmour.com
- store.steampowered.com

## Output Structure

```
crawled_websites/
├── yellowpages.com/
│   ├── accessibility_data.json     # All URL data in structured format
│   ├── crawl_summary.json         # Crawl statistics and metadata
│   ├── crawled_pages.json         # Raw crawled page data
│   └── crawl_log.txt             # Detailed crawl log
├── facebook.com/
│   └── ...
└── batch_crawl_summary.json      # Overall statistics
```

## Data Access

Each website directory contains:

1. **`accessibility_data.json`** - Main data file with accessibility trees for all URLs
2. **`crawl_summary.json`** - Statistics (pages crawled, URLs discovered, duration)
3. **`crawled_pages.json`** - Raw page data
4. **`crawl_log.txt`** - Detailed crawling log

### Example: Loading URL data
```python
import json

# Load all accessibility data for a website
with open('crawled_websites/wikipedia.org/accessibility_data.json', 'r') as f:
    data = json.load(f)

accessibility_dict = data['accessibility_data']

# Get all URLs discovered
all_urls = list(accessibility_dict.keys())
print(f"Discovered {len(all_urls)} URLs from wikipedia.org")

# Access specific URL data
url_data = accessibility_dict['https://en.wikipedia.org/wiki/Main_Page']
tree_text = url_data['tree_text']
depth = url_data['depth']
```

## Expected Results

With these settings, you should expect:
- **100-2000 URLs per website** (depending on site structure)
- **Deep crawling** through multiple levels of navigation
- **Comprehensive accessibility data** for each discovered URL
- **Fast processing** with 0.1s delays

## Monitoring Progress

The crawler shows real-time statistics:
```
✅ Successfully crawled wikipedia.org:
   📄 Pages crawled: 1,234
   🔗 Total URLs discovered: 2,456
   ❌ Failed URLs: 12
   ⏱️  Duration: 245.6s
```

## Analysis

Run the analysis script to see:
- Total URLs discovered across all websites
- Top performing websites (most URLs found)
- Success/failure rates
- Time statistics

This setup will give you extensive URL coverage from each target website! 