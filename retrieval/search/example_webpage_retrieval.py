#!/usr/bin/env python3
"""
Example script demonstrating how to use the webpage retrieval index.

This script shows various ways to:
1. Create a retrieval index from webpage descriptions
2. Search for similar webpages using queries
3. Find webpages by functionality
4. Group similar webpages together
"""

import json
from create_webpage_retrieval_index import (
    load_webpage_descriptions,
    create_webpage_retrieval_index,
    retrieve_similar_webpages,
    find_webpages_by_functionality,
    group_similar_webpages,
    save_retrieval_index,
    load_retrieval_index
)


def example_create_and_search():
    """Example of creating an index and performing searches."""
    
    print("=" * 80)
    print("🔍 WEBPAGE RETRIEVAL INDEX EXAMPLE")
    print("=" * 80)
    
    # File paths (adjust these to match your actual files)
    descriptions_file = "url_descriptions.json"
    index_file = "webpage_retrieval_index.pkl"
    
    # Step 1: Load webpage descriptions
    print("\n📋 Step 1: Loading webpage descriptions...")
    try:
        descriptions = load_webpage_descriptions(descriptions_file)
        print(f"✅ Loaded {len(descriptions)} webpage descriptions")
        
        # Show a sample
        sample_urls = list(descriptions.keys())[:3]
        print("\n📄 Sample descriptions:")
        for i, url in enumerate(sample_urls, 1):
            desc = descriptions[url]
            print(f"  {i}. {url}")
            print(f"     → {desc[:100]}{'...' if len(desc) > 100 else ''}")
    
    except Exception as e:
        print(f"❌ Error loading descriptions: {e}")
        print("💡 Make sure you have run generate_descriptions_url_tree.py first")
        return
    
    # Step 2: Create retrieval index
    print(f"\n🔧 Step 2: Creating retrieval index...")
    try:
        index = create_webpage_retrieval_index(descriptions)
        save_retrieval_index(index, index_file)
        print(f"✅ Index created and saved to {index_file}")
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        return
    
    # Step 3: Test different types of searches
    print(f"\n🔍 Step 3: Testing retrieval functionality...")
    
    # Example 1: Query-based search
    print("\n🎯 Example 1: Query-based search")
    test_queries = [
        "sports news and live scores",
        "video content and streaming",
        "user account and profile settings",
        "shopping and e-commerce features"
    ]
    
    for query in test_queries:
        print(f"\n🔎 Query: '{query}'")
        results = retrieve_similar_webpages(query, index, top_k=5, similarity_threshold=0.2)
        
        if results:
            print(f"📊 Found {len(results)} similar webpages:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result['url']} (similarity: {result['similarity_score']:.3f})")
        else:
            print("❌ No similar webpages found")
    
    # Example 2: Functionality-based search
    print(f"\n🎯 Example 2: Functionality-based search")
    functionality_examples = [
        ["search", "filter"],
        ["video", "media", "streaming"],
        ["login", "authentication", "account"],
        ["shopping", "cart", "purchase"]
    ]
    
    for functionality_keywords in functionality_examples:
        print(f"\n🔧 Functionality: {', '.join(functionality_keywords)}")
        results = find_webpages_by_functionality(functionality_keywords, index, top_k=3)
        
        if results:
            print(f"📊 Found {len(results)} matching webpages:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result['url']} (similarity: {result['similarity_score']:.3f})")
        else:
            print("❌ No matching webpages found")
    
    # Example 3: Group similar webpages
    print(f"\n🎯 Example 3: Grouping similar webpages")
    groups = group_similar_webpages(index, similarity_threshold=0.6, max_group_size=5)
    
    if groups:
        print(f"📊 Found {len(groups)} groups of similar webpages:")
        for i, group in enumerate(groups[:3], 1):  # Show first 3 groups
            print(f"\n📂 Group {i} ({len(group)} webpages):")
            for j, webpage in enumerate(group, 1):
                print(f"  {j}. {webpage['url']} (similarity: {webpage['similarity_to_first']:.3f})")
    else:
        print("❌ No groups found (try lowering the similarity threshold)")
    
    print(f"\n✅ Example completed! Index saved as {index_file}")


def example_load_and_search():
    """Example of loading an existing index and performing searches."""
    
    print("\n" + "=" * 80)
    print("📁 LOADING EXISTING INDEX EXAMPLE")
    print("=" * 80)
    
    index_file = "webpage_retrieval_index.pkl"
    
    try:
        # Load existing index
        print(f"\n📂 Loading existing index from {index_file}...")
        index = load_retrieval_index(index_file)
        
        # Perform a custom search
        custom_query = input("\n🔍 Enter a search query (or press Enter for default): ").strip()
        if not custom_query:
            custom_query = "sports statistics and live updates"
        
        print(f"🔎 Searching for: '{custom_query}'")
        results = retrieve_similar_webpages(custom_query, index, top_k=10, similarity_threshold=0.1)
        
        if results:
            print(f"\n📊 Found {len(results)} similar webpages:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. URL: {result['url']}")
                print(f"   Similarity: {result['similarity_score']:.3f}")
                print(f"   Description: {result['description'][:200]}{'...' if len(result['description']) > 200 else ''}")
        else:
            print("❌ No similar webpages found. Try a different query or lower the similarity threshold.")
    
    except FileNotFoundError:
        print(f"❌ Index file not found: {index_file}")
        print("💡 Run the create example first to generate the index")
    except Exception as e:
        print(f"❌ Error loading index: {e}")


def print_usage_instructions():
    """Print usage instructions for the command line interface."""
    
    print("\n" + "=" * 80)
    print("📖 COMMAND LINE USAGE INSTRUCTIONS")
    print("=" * 80)
    
    print("""
🚀 Basic Usage:
   python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl

🔍 With query search:
   python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --query "sports news"

🔧 With functionality search:
   python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --functionality search filter

📊 With grouping similar webpages:
   python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --group-similar

💾 Export results to JSON:
   python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --query "video" --export-json results.json

🎛️ Advanced options:
   python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl \\
       --query "user account settings" \\
       --functionality login account profile \\
       --top-k 15 \\
       --similarity-threshold 0.2 \\
       --group-similar \\
       --group-threshold 0.7 \\
       --export-json comprehensive_results.json \\
       --verbose

📋 Available models (use --model):
   - all-MiniLM-L6-v2 (default, fast and efficient)
   - all-mpnet-base-v2 (higher quality, slower)
   - multi-qa-MiniLM-L6-cos-v1 (optimized for Q&A)
   
🔧 Parameters:
   --top-k: Number of results to return (default: 10)
   --similarity-threshold: Minimum similarity score (default: 0.3)
   --group-threshold: Similarity threshold for grouping (default: 0.7)
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print_usage_instructions()
    elif len(sys.argv) > 1 and sys.argv[1] == "--load":
        example_load_and_search()
    else:
        example_create_and_search()
        print_usage_instructions()