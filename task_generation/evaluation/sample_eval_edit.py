from parse_url_tree import parse_url_tree
import random
import pickle
import os
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from tqdm import tqdm

# Import multi-hop task generation functions
from multi_hop_task_gen import read_accessibility_tree_file, generate_multi_hop_task_prompt
from aysnc_llm_call import process_llm_batch_calls


def count_all_children(url_tree, url):
    """
    Count the total number of children nodes (direct and indirect) for a given URL.
    
    Args:
        url_tree: Dictionary mapping URLs to their direct children
        url: The URL to count children for
    
    Returns:
        tuple: (total_count, list_of_all_children)
    """
    visited = set()
    
    def count_recursive(current_url):
        if current_url in visited or current_url not in url_tree:
            return 0
        
        visited.add(current_url)
        children = url_tree[current_url]
        total_count = len(children)  # Count direct children
        
        # Recursively count children of children
        for child in children:
            total_count += count_recursive(child)
        
        return total_count
    
    # Call the recursive function to populate visited set
    total_count = count_recursive(url)
    
    # Process visited set to get all children (excluding the root URL)
    all_children_set = visited.copy()
    all_children_set.discard(url)  # Remove the root URL itself
    
    # Deduplicate URLs by normalizing them
    normalized_children = set()  # set to avoid duplicates
    for child in all_children_set:
        # Remove trailing slash and normalize URL
        normalized = child.rstrip('/')
        normalized_children.add(normalized)
    
    all_children = list(normalized_children)
    return total_count, all_children


def find_urls_with_min_children(url_tree, min_children=5, max_urls=2):
    """
    Find URLs that have at least min_children direct and indirect children.
    
    Args:
        url_tree: Dictionary mapping URLs to their direct children
        min_children: Minimum number of children required
        max_urls: Maximum number of URLs to return
    
    Returns:
        list: List of URLs that meet the criteria
    """
    suitable_urls = []
    url_keys = list(url_tree.keys())
    
    # Shuffle to get random selection
    random.shuffle(url_keys)
    
    for url in url_keys:
        if len(suitable_urls) >= max_urls:
            break
            
        child_count, _ = count_all_children(url_tree, url)
        if child_count >= min_children:
            suitable_urls.append(url)
    
    return suitable_urls


def get_sample_urls(file_path=None, min_children=5):
    """
    Main function to get two sample URLs with at least min_children direct and indirect children.
    
    Args:
        file_path: Path to the URL tree structure file
        min_children: Minimum number of children required
    
    Returns:
        list: Two URLs that meet the criteria
    """
    if file_path is None:
        file_path = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    url_tree = parse_url_tree(file_path)
    sample_urls = find_urls_with_min_children(url_tree, min_children, max_urls=2)
    
    return sample_urls


def get_url_children_info(url, file_path=None):
    """
    Get detailed information about a URL's children.
    
    Args:
        url: The URL to analyze
        file_path: Path to the URL tree structure file
    
    Returns:
        dict: Dictionary containing count and list of children
    """
    if file_path is None:
        file_path = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    url_tree = parse_url_tree(file_path)
    child_count, all_children = count_all_children(url_tree, url)
    
    return {
        'url': url,
        'total_children_count': child_count,
        'all_children': all_children
    }


def url_to_accessibility_file(url: str, accessibility_dir: str) -> Optional[str]:
    """
    Convert a URL to its corresponding accessibility tree file path.
    
    Args:
        url: The URL to convert
        accessibility_dir: Directory containing accessibility tree files
    
    Returns:
        File path if found, None otherwise
    """
    # Try to load URL to filename mapping
    mapping_file = '/path/to/your/data/Agentrek_expriment/espn/url_tree_url_to_filename_mapping.pkl'
    try:
        with open(mapping_file, 'rb') as f:
            url2filename = pickle.load(f)
        
        if url in url2filename:
            filename = url2filename[url]
            file_path = os.path.join(accessibility_dir, filename)
            if os.path.exists(file_path):
                return file_path
    except FileNotFoundError:
        pass
    
    # Fallback: try to find file by URL matching in accessibility files
    if not os.path.exists(accessibility_dir):
        return None
        
    for filename in os.listdir(accessibility_dir):
        if filename.startswith('page_') and filename.endswith('.txt'):
            file_path = os.path.join(accessibility_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                lines = content.split('\n')
                for line in lines[:10]:  # Check first 10 lines for URL
                    if line.startswith('URL:') and url in line:
                        return file_path
            except:
                continue
    
    return None


def sample_url_pairs_for_multihop(url_tree_file=None, num_pairs=2, min_children=5, seed=42):
    """
    Sample pairs of URLs that have sufficient children for multi-hop task generation.
    
    Args:
        url_tree_file: Path to URL tree structure file
        num_pairs: Number of pairs to sample
        min_children: Minimum number of children required for sampling
        seed: Random seed for reproducibility
    
    Returns:
        List of URL pairs suitable for multi-hop tasks
    """
    if url_tree_file is None:
        url_tree_file = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    random.seed(seed)
    
    # Get URLs with sufficient children - we need more than num_pairs * 2 to create pairs
    sample_urls = get_sample_urls(url_tree_file, min_children)
    
    if len(sample_urls) < 2:
        raise ValueError(f"Need at least 2 URLs with {min_children}+ children to create pairs. Found {len(sample_urls)}")
    
    pairs = []
    for _ in range(num_pairs):
        # Sample two different URLs
        if len(sample_urls) >= 2:
            pair = random.sample(sample_urls, 2)
            pairs.append((pair[0], pair[1]))
        else:
            break
    
    return pairs


def get_accessibility_file_pairs(url_tree_file=None, accessibility_dir="espn", num_pairs=2, min_children=5, seed=42):
    """
    Generate pairs of accessibility tree files based on URL sampling with minimum children requirement.
    
    Args:
        url_tree_file: Path to URL tree structure file
        accessibility_dir: Directory containing accessibility tree files
        num_pairs: Number of pairs to generate
        min_children: Minimum number of children required for URL sampling
        seed: Random seed for reproducibility
    
    Returns:
        tuple: (successful_pairs, url_pairs_info) where successful_pairs is list of file path pairs
               and url_pairs_info contains the URL information
    """
    if url_tree_file is None:
        url_tree_file = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    # Sample URL pairs
    url_pairs = sample_url_pairs_for_multihop(url_tree_file, num_pairs, min_children, seed)
    
    # Convert URL pairs to file pairs
    successful_pairs = []
    url_pairs_info = []
    
    for url1, url2 in url_pairs:
        file1 = url_to_accessibility_file(url1, accessibility_dir)
        file2 = url_to_accessibility_file(url2, accessibility_dir)
        
        if file1 and file2:
            successful_pairs.append((file1, file2))
            
            # Get URL info for reporting
            url1_info = get_url_children_info(url1, url_tree_file)
            url2_info = get_url_children_info(url2, url_tree_file)
            url_pairs_info.append({
                'url1': url1,
                'url2': url2,
                'url1_children': url1_info['total_children_count'],
                'url2_children': url2_info['total_children_count'],
                'file1': file1,
                'file2': file2
            })
    
    return successful_pairs, url_pairs_info


def generate_multihop_tasks_from_sampled_urls(url_tree_file=None, accessibility_dir="espn", 
                                            num_pairs=2, min_children=5, seed=42, verbose=False):
    """
    Generate multi-hop task data using URL sampling with minimum children requirement.
    
    Args:
        url_tree_file: Path to URL tree structure file
        accessibility_dir: Directory containing accessibility tree files
        num_pairs: Number of pairs to generate
        min_children: Minimum number of children required for URL sampling
        seed: Random seed for reproducibility
        verbose: Enable verbose output
    
    Returns:
        dict: Information about sampled URLs and file pairs suitable for multi-hop task generation
    """
    if url_tree_file is None:
        url_tree_file = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    # Get file pairs based on URL sampling
    file_pairs, url_pairs_info = get_accessibility_file_pairs(
        url_tree_file, accessibility_dir, num_pairs, min_children, seed
    )
    
    result = {
        'total_url_pairs_sampled': len(url_pairs_info),
        'successful_file_pairs': len(file_pairs),
        'file_pairs': file_pairs,
        'url_pairs_info': url_pairs_info,
        'sampling_parameters': {
            'num_pairs': num_pairs,
            'min_children': min_children,
            'seed': seed,
            'url_tree_file': url_tree_file,
            'accessibility_dir': accessibility_dir
        }
    }
    
    if verbose:
        print(f"URL-based sampling results:")
        print(f"  Requested pairs: {num_pairs}")
        print(f"  Minimum children required: {min_children}")
        print(f"  Successfully sampled URL pairs: {len(url_pairs_info)}")
        print(f"  Successfully mapped to file pairs: {len(file_pairs)}")
        
        for i, info in enumerate(url_pairs_info, 1):
            print(f"  {i}. {info['url1']} ({info['url1_children']} children) <-> {info['url2']} ({info['url2_children']} children)")
    
    return result


def generate_and_save_multihop_tasks(url_tree_file=None, accessibility_dir=None, 
                                   output_file="multihop_tasks_from_sampled_urls.json",
                                   num_pairs=5, min_children=5, max_content=15000, 
                                   seed=42, verbose=False):
    """
    Generate multi-hop tasks from sampled URLs and save to file.
    
    Args:
        url_tree_file: Path to URL tree structure file
        accessibility_dir: Directory containing accessibility tree files
        output_file: Path to save the generated tasks
        num_pairs: Number of URL pairs to generate tasks for
        min_children: Minimum number of children required for URL sampling
        max_content: Maximum content length per page to include in LLM prompt
        seed: Random seed for reproducibility
        verbose: Enable verbose output
    
    Returns:
        dict: Summary of the generation process
    """
    if url_tree_file is None:
        url_tree_file = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    if accessibility_dir is None:
        accessibility_dir = "/path/to/your/data/Agentrek_expriment/crawled_websites/espn.com"
    
    print(f"=== Multi-hop Task Generation from Sampled URLs ===")
    print(f"URL tree file: {url_tree_file}")
    print(f"Accessibility directory: {accessibility_dir}")
    print(f"Output file: {output_file}")
    print(f"Number of pairs: {num_pairs}")
    print(f"Minimum children: {min_children}")
    print(f"Max content per page: {max_content}")
    print(f"Seed: {seed}")
    
    # Get file pairs based on URL sampling
    file_pairs, url_pairs_info = get_accessibility_file_pairs(
        url_tree_file, accessibility_dir, num_pairs, min_children, seed
    )
    
    if len(file_pairs) == 0:
        print("Error: No valid file pairs found for processing")
        return {'error': 'No valid file pairs found'}
    
    print(f"Successfully mapped {len(file_pairs)} URL pairs to accessibility files")
    
    if verbose:
        print("Processing the following URL pairs:")
        for i, info in enumerate(url_pairs_info, 1):
            print(f"  {i}. {info['url1']} ({info['url1_children']} children) <-> {info['url2']} ({info['url2_children']} children)")
    
    # Process page pairs and generate prompts
    payload = []
    successful_pairs = []
    
    for (file1, file2), url_info in zip(file_pairs, url_pairs_info):
        if verbose:
            print(f"Processing: {os.path.basename(file1)} <-> {os.path.basename(file2)}")
        
        # Read both accessibility tree files
        page1_data = read_accessibility_tree_file(file1, max_content)
        page2_data = read_accessibility_tree_file(file2, max_content)
        
        # Skip if either page failed to load
        if not page1_data['success'] or not page2_data['success']:
            if verbose:
                print(f"  Skipping pair due to read error:")
                if not page1_data['success']:
                    print(f"    Page 1 error: {page1_data.get('error', 'Unknown error')}")
                if not page2_data['success']:
                    print(f"    Page 2 error: {page2_data.get('error', 'Unknown error')}")
            continue
        
        # Generate multi-hop task prompt
        task_prompt = generate_multi_hop_task_prompt(page1_data, page2_data)
        
        example = {
            "messages": [
                {"role": "user", "content": task_prompt}
            ]
        }
        payload.append(example)
        successful_pairs.append((page1_data, page2_data, url_info))
    
    print(f"Successfully prepared {len(payload)} pairs for LLM processing")
    
    if len(payload) == 0:
        print("Error: No valid page pairs found for LLM processing")
        return {'error': 'No valid page pairs for LLM processing'}
    
    # Process LLM batch calls
    print(f"Processing {len(payload)} pairs with LLM...")
    try:
        results = process_llm_batch_calls(payload)
        print(f"LLM processing completed for {len(results)} pairs")
    except Exception as e:
        print(f"Error during LLM processing: {e}")
        return {'error': f'LLM processing failed: {e}'}
    
    # Prepare output data
    output_data = []
    
    for (page1_data, page2_data, url_info), result in zip(successful_pairs, results):
        try:
            # Try to parse the LLM output as JSON
            llm_output = result.get('model_output', '')
            
            # Extract JSON from the output if it's wrapped in other text
            import re
            json_match = re.search(r'\[.*\]', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    tasks = json.loads(json_str)
                except json.JSONDecodeError:
                    tasks = [{"error": "Failed to parse LLM output as JSON", "raw_output": llm_output}]
            else:
                tasks = [{"error": "No JSON array found in LLM output", "raw_output": llm_output}]
            
        except Exception as e:
            tasks = [{"error": f"Error processing LLM output: {str(e)}", "raw_output": result.get('model_output', '')}]
        
        output_entry = {
            "url_sampling_info": {
                "url1": url_info['url1'],
                "url2": url_info['url2'],
                "url1_children_count": url_info['url1_children'],
                "url2_children_count": url_info['url2_children'],
                "min_children_threshold": min_children
            },
            "page1": {
                "file_path": page1_data['file_path'],
                "url": page1_data['url'],
                "title": page1_data['title'],
                "content_length": page1_data['content_length']
            },
            "page2": {
                "file_path": page2_data['file_path'],
                "url": page2_data['url'],
                "title": page2_data['title'],
                "content_length": page2_data['content_length']
            },
            "generated_tasks": tasks,
            "generation_timestamp": datetime.now().isoformat(),
            "max_content_per_page": max_content,
            "sampling_method": "url_based_with_min_children"
        }
        output_data.append(output_entry)
    
    # Save results to output file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"Results saved to {output_file}")
    print(f"Successfully generated multi-hop tasks for {len(output_data)} page pairs")
    
    # Print summary statistics
    total_tasks = 0
    successful_tasks = 0
    
    for entry in output_data:
        tasks = entry['generated_tasks']
        total_tasks += len(tasks)
        for task in tasks:
            if 'error' not in task:
                successful_tasks += 1
    
    print(f"Generated {total_tasks} total tasks")
    print(f"Successfully parsed {successful_tasks} tasks")
    if total_tasks > 0:
        print(f"Success rate: {successful_tasks/total_tasks*100:.1f}%")
    
    return {
        'output_file': output_file,
        'total_url_pairs_processed': len(output_data),
        'total_tasks_generated': total_tasks,
        'successful_tasks': successful_tasks,
        'success_rate': successful_tasks/total_tasks*100 if total_tasks > 0 else 0,
        'sampling_parameters': {
            'num_pairs': num_pairs,
            'min_children': min_children,
            'max_content': max_content,
            'seed': seed,
            'url_tree_file': url_tree_file,
            'accessibility_dir': accessibility_dir
        }
    }


# Main execution when run as script
if __name__ == "__main__":
    # Test basic URL sampling
    print("=== Basic URL Sampling ===")
    sample_urls = get_sample_urls()
    
    print(f"Found {len(sample_urls)} URLs with at least 5 children:")
    for i, url in enumerate(sample_urls, 1):
        info = get_url_children_info(url)
        print(f"\n{i}. URL: {url}")
        print(f"   Total children count: {info['total_children_count']}")
        print(f"   Number of unique children: {len(info['all_children'])}")
    
    # Test multi-hop task generation functionality
    print("\n=== Multi-hop Task Generation Sampling ===")
    try:
        multihop_result = generate_multihop_tasks_from_sampled_urls(
            num_pairs=3, 
            min_children=5, 
            accessibility_dir="/path/to/your/data/Agentrek_expriment/crawled_websites/espn.com", 
            verbose=True
        )
        
        print(f"\nMulti-hop sampling summary:")
        print(f"  Total URL pairs sampled: {multihop_result['total_url_pairs_sampled']}")
        print(f"  Successful file pair mappings: {multihop_result['successful_file_pairs']}")
        
        if multihop_result['file_pairs']:
            print(f"\nAccessibility file pairs ready for multi-hop task generation:")
            for i, (file1, file2) in enumerate(multihop_result['file_pairs'], 1):
                print(f"  {i}. {os.path.basename(file1)} <-> {os.path.basename(file2)}")
        
    except Exception as e:
        print(f"Error during multi-hop sampling: {e}")
    
    # Actually generate and save multi-hop tasks
    print("\n" + "="*60)
    print("=== GENERATING AND SAVING MULTI-HOP TASKS ===")
    print("="*60)
    
    try:
        # Generate multi-hop tasks with sampled URLs
        generation_result = generate_and_save_multihop_tasks(
            url_tree_file="/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt",
            accessibility_dir="/path/to/your/data/Agentrek_expriment/crawled_websites/espn.com",
            output_file="multihop_tasks_from_sampled_urls.json",
            num_pairs=5,  # Generate tasks for 5 URL pairs
            min_children=5,  # URLs must have at least 5 children
            max_content=15000,  # Max content per page
            seed=42,
            verbose=True
        )
        
        print(f"\n" + "="*60)
        print("=== GENERATION COMPLETED ===")
        print("="*60)
        
        if 'error' not in generation_result:
            print(f"✅ Successfully completed multi-hop task generation!")
            print(f"📄 Output file: {generation_result['output_file']}")
            print(f"📊 Total URL pairs processed: {generation_result['total_url_pairs_processed']}")
            print(f"📝 Total tasks generated: {generation_result['total_tasks_generated']}")
            print(f"✅ Successful tasks: {generation_result['successful_tasks']}")
            print(f"📈 Success rate: {generation_result['success_rate']:.1f}%")
            
            print(f"\n📋 Sampling parameters used:")
            params = generation_result['sampling_parameters']
            print(f"  • Number of pairs: {params['num_pairs']}")
            print(f"  • Minimum children: {params['min_children']}")
            print(f"  • Max content per page: {params['max_content']}")
            print(f"  • Seed: {params['seed']}")
        else:
            print(f"❌ Error during generation: {generation_result['error']}")
            
    except Exception as e:
        print(f"❌ Fatal error during multi-hop task generation: {e}")
        import traceback
        traceback.print_exc()
    
    # Optional: Show filename mappings if available
    print("\n=== Filename Mappings ===")
    try:
        url2filename = pickle.load(open('/path/to/your/data/Agentrek_expriment/espn/url_tree_url_to_filename_mapping.pkl', 'rb'))
        print(f"Filename mappings for children of first URL:")
        if sample_urls:
            info = get_url_children_info(sample_urls[0])
            for child_url in info['all_children'][:10]:  # Show first 10
                if child_url in url2filename:
                    print(f"  {child_url} -> {url2filename[child_url]}")
    except FileNotFoundError:
        print("Filename mapping file not found.")

