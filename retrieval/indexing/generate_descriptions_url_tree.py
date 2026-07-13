#!/usr/bin/env python3
"""
Generate descriptions for each webpage in the URL tree structure.

This script uses functions from sample_eval_edit.py to load accessibility trees
and generates short descriptions for each webpage focusing on:
- Functionalities
- Why users might click into this page  
- Basic info about what the page is about

These descriptions will be used later for retrieving webpages with similar functionalities.

Output format:
{
    "https://normalized-url-1.com": "Description of webpage 1 functionality and purpose...",
    "https://normalized-url-2.com": "Description of webpage 2 functionality and purpose...",
    ...
}
"""

import os
import json
import pickle
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from tqdm import tqdm

# Import required functions from local modules
from parse_url_tree import parse_url_tree, normalize_url
from multi_hop_task_gen import read_accessibility_tree_file
from aysnc_llm_call import process_llm_batch_calls


def get_all_urls_from_tree(url_tree_file: str = None) -> List[str]:
    """
    Get all URLs from the URL tree structure.
    
    Args:
        url_tree_file: Path to URL tree structure file
        
    Returns:
        List of all URLs in the tree
    """
    if url_tree_file is None:
        url_tree_file = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    url_tree = parse_url_tree(url_tree_file)
    
    # Collect all unique URLs (both parents and children)
    all_urls = set()
    
    for parent_url, children in url_tree.items():
        all_urls.add(parent_url)
        all_urls.update(children)
    
    return list(all_urls)


def url_to_accessibility_file(url: str, accessibility_dir: str) -> Optional[str]:
    """
    Convert a URL to its corresponding accessibility tree file path.
    Reusing the function from sample_eval_edit.py
    
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


def create_description_prompt(page_data: Dict) -> str:
    """
    Create a prompt for the LLM to generate webpage descriptions.
    
    Args:
        page_data: Dictionary containing page information from read_accessibility_tree_file
        
    Returns:
        LLM prompt string
    """
    prompt = f"""You are tasked with generating a concise, informative description for a webpage. The description should focus on functionality and user intent.

**Webpage Information:**
- URL: {page_data['url']}
- Title: {page_data['title']}

**Accessibility Tree Content:**
{page_data['content'][:5000]}{"... [TRUNCATED]" if len(page_data['content']) > 5000 else ""}

**Instructions:**
Generate a 2-3 sentence description that captures:
1. What this webpage is about (main topic/subject)
2. Key functionalities available on this page
3. Why a user would likely visit/click on this page
4. What actions or information users can access here

Focus on practical user needs and page functionality rather than design elements. Be specific and informative.

**Format your response as a single JSON object:**
{{
    "description": "Your 2-3 sentence description here",
    "main_topic": "Primary subject/category of the page",
    "key_functionalities": ["functionality1", "functionality2", "functionality3"],
    "user_intent": "Primary reason users would visit this page"
}}

Respond with only the JSON object, no additional text."""

    return prompt


def process_urls_for_descriptions(url_tree_file: str = None, 
                                accessibility_dir: str = None,
                                max_content: int = 15000,
                                batch_size: int = 10) -> Dict:
    """
    Process all URLs in the tree to prepare them for description generation.
    
    Args:
        url_tree_file: Path to URL tree structure file
        accessibility_dir: Directory containing accessibility tree files
        max_content: Maximum content length per page
        batch_size: Number of URLs to process in each batch
        
    Returns:
        Dictionary containing processed data and statistics
    """
    if url_tree_file is None:
        url_tree_file = "/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt"
    
    if accessibility_dir is None:
        accessibility_dir = "/path/to/your/data/Agentrek_expriment/crawled_websites/espn.com"
    
    print(f"=== Processing URLs for Description Generation ===")
    print(f"URL tree file: {url_tree_file}")
    print(f"Accessibility directory: {accessibility_dir}")
    print(f"Max content per page: {max_content}")
    
    # Get all URLs from the tree
    all_urls = get_all_urls_from_tree(url_tree_file)
    print(f"Found {len(all_urls)} total URLs in the tree")
    
    # Process URLs to find corresponding accessibility files
    successful_mappings = []
    failed_mappings = []
    
    print("Mapping URLs to accessibility files...")
    for url in tqdm(all_urls, desc="Processing URLs"):
        file_path = url_to_accessibility_file(url, accessibility_dir)
        
        if file_path:
            # Try to read the accessibility content
            page_data = read_accessibility_tree_file(file_path, max_content)
            
            if page_data['success']:
                successful_mappings.append({
                    'url': url,
                    'file_path': file_path,
                    'page_data': page_data
                })
            else:
                failed_mappings.append({
                    'url': url,
                    'file_path': file_path,
                    'error': page_data.get('error', 'Unknown error')
                })
        else:
            failed_mappings.append({
                'url': url,
                'file_path': None,
                'error': 'No accessibility file found'
            })
    
    print(f"Successfully mapped {len(successful_mappings)} URLs to accessibility files")
    print(f"Failed to map {len(failed_mappings)} URLs")
    
    return {
        'total_urls': len(all_urls),
        'successful_mappings': successful_mappings,
        'failed_mappings': failed_mappings,
        'success_rate': len(successful_mappings) / len(all_urls) * 100 if all_urls else 0
    }


def generate_descriptions_batch(successful_mappings: List[Dict], 
                              batch_size: int = 20) -> List[Dict]:
    """
    Generate descriptions for webpages using LLM in batches.
    
    Args:
        successful_mappings: List of successfully mapped URL-to-file data
        batch_size: Number of descriptions to generate per batch
        
    Returns:
        List of results with generated descriptions
    """
    print(f"Generating descriptions for {len(successful_mappings)} webpages...")
    
    # Prepare prompts for batch processing
    payload = []
    
    for mapping in successful_mappings:
        page_data = mapping['page_data']
        prompt = create_description_prompt(page_data)
        
        example = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "metadata": {
                "url": mapping['url'],
                "file_path": mapping['file_path'],
                "title": page_data['title']
            }
        }
        payload.append(example)
    
    # Process in batches
    all_results = []
    
    print(f"Processing {len(payload)} items in batch...")
    
    try:
        all_results = process_llm_batch_calls(payload)
        print(f"Successfully processed {len(all_results)} descriptions")
    except Exception as e:
        print(f"Error processing batch: {e}")
        # Add error entries for failed batch
        all_results = []
        for item in payload:
            error_result = {
                'metadata': item['metadata'],
                'model_output': f"Error: {str(e)}",
                'error': True
            }
            all_results.append(error_result)
    
    return all_results


def parse_description_output(llm_output: str) -> Dict:
    """
    Parse the LLM output to extract description information.
    
    Args:
        llm_output: Raw output from the LLM
        
    Returns:
        Parsed description data
    """
    try:
        # Try to parse as JSON directly
        import re
        
        # Look for JSON object in the output
        json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            # Fallback: treat as plain text description
            return {
                "description": llm_output.strip()[:500],  # Limit length
                "main_topic": "Unknown",
                "key_functionalities": [],
                "user_intent": "Unknown",
                "parse_error": "No JSON found in output"
            }
    except json.JSONDecodeError:
        return {
            "description": llm_output.strip()[:500],
            "main_topic": "Unknown", 
            "key_functionalities": [],
            "user_intent": "Unknown",
            "parse_error": "JSON decode error"
        }


def generate_and_save_url_descriptions(url_tree_file: str = None,
                                     accessibility_dir: str = None,
                                     output_file: str = "url_descriptions.json",
                                     max_content: int = 15000,
                                     batch_size: int = 20) -> Dict:
    """
    Main function to generate and save descriptions for all URLs in the tree.
    
    Args:
        url_tree_file: Path to URL tree structure file
        accessibility_dir: Directory containing accessibility tree files
        output_file: Path to save the generated descriptions
        max_content: Maximum content length per page
        batch_size: Number of descriptions to generate per batch
        
    Returns:
        Summary of the generation process
    """
    print("=" * 80)
    print("=== URL DESCRIPTION GENERATION ===")
    print("=" * 80)
    
    # Process URLs and map to accessibility files
    processing_result = process_urls_for_descriptions(
        url_tree_file, accessibility_dir, max_content
    )
    
    if len(processing_result['successful_mappings']) == 0:
        error_msg = "No URLs could be mapped to accessibility files"
        print(f"Error: {error_msg}")
        return {'error': error_msg}
    
    # Generate descriptions using LLM
    llm_results = generate_descriptions_batch(
        processing_result['successful_mappings'], batch_size
    )
    
    # Process and structure the output as a simple dictionary
    url_descriptions = {}
    successful_descriptions = 0
    failed_descriptions = 0
    
    for result in llm_results:
        try:
            metadata = result.get('metadata', {})
            llm_output = result.get('model_output', '')
            url = metadata.get('url', '')
            
            if not url:
                failed_descriptions += 1
                continue
            
            # Parse the LLM output
            parsed_description = parse_description_output(llm_output)
            
            # Get the description text
            if 'parse_error' not in parsed_description and 'processing_error' not in parsed_description:
                description = parsed_description.get('description', '').strip()
                successful_descriptions += 1
            else:
                # Fallback to raw output if parsing failed
                description = llm_output.strip()[:500] if llm_output.strip() else "Error: No description generated"
                failed_descriptions += 1
            
            # Use normalized URL as key
            normalized_url = normalize_url(url)
            url_descriptions[normalized_url] = description
            
        except Exception as e:
            # Handle any processing errors
            failed_descriptions += 1
            url = result.get('metadata', {}).get('url', '')
            if url:
                normalized_url = normalize_url(url)
                url_descriptions[normalized_url] = f"Error processing description: {str(e)}"
    
    # Create metadata dictionary for logging purposes
    generation_metadata = {
        "total_urls_in_tree": processing_result['total_urls'],
        "successfully_mapped_urls": len(processing_result['successful_mappings']),
        "failed_mappings": len(processing_result['failed_mappings']),
        "mapping_success_rate": processing_result['success_rate'],
        "total_descriptions_generated": len(url_descriptions),
        "successful_descriptions": successful_descriptions,
        "failed_descriptions": failed_descriptions,
        "description_success_rate": (successful_descriptions / len(url_descriptions) * 100) if url_descriptions else 0,
        "generation_timestamp": datetime.now().isoformat(),
        "parameters": {
            "url_tree_file": url_tree_file,
            "accessibility_dir": accessibility_dir,
            "max_content": max_content,
            "batch_size": batch_size
        }
    }
    
    # Save the simple dictionary format
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(url_descriptions, f, ensure_ascii=False, indent=2)
    
    # Save metadata to a separate file for reference
    metadata_file = output_file.replace('.json', '_metadata.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(generation_metadata, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("=== GENERATION COMPLETED ===")
    print("=" * 80)
    print(f"✅ Descriptions saved to: {output_file}")
    print(f"📊 Metadata saved to: {metadata_file}")
    print(f"📊 Total URLs in tree: {processing_result['total_urls']}")
    print(f"🗂️  Successfully mapped to files: {len(processing_result['successful_mappings'])} ({processing_result['success_rate']:.1f}%)")
    print(f"📝 Descriptions generated: {len(url_descriptions)}")
    print(f"✅ Successfully parsed descriptions: {successful_descriptions} ({generation_metadata['description_success_rate']:.1f}%)")
    print(f"❌ Failed descriptions: {failed_descriptions}")
    print(f"❌ Failed URL mappings: {len(processing_result['failed_mappings'])}")
    
    return {
        'output_file': output_file,
        'metadata_file': metadata_file,
        'total_urls': processing_result['total_urls'],
        'mapped_urls': len(processing_result['successful_mappings']),
        'mapping_success_rate': processing_result['success_rate'],
        'descriptions_generated': len(url_descriptions),
        'successful_descriptions': successful_descriptions,
        'failed_descriptions': failed_descriptions,
        'description_success_rate': generation_metadata['description_success_rate'],
        'url_descriptions': url_descriptions
    }


def load_url_descriptions(file_path: str) -> Dict[str, str]:
    """
    Load the generated URL descriptions from the output file.
    
    Args:
        file_path: Path to the descriptions JSON file
        
    Returns:
        Dictionary with normalized URLs as keys and descriptions as values
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Description file not found: {file_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from {file_path}: {e}")
        return {}


if __name__ == "__main__":
    # Run the description generation
    try:
        result = generate_and_save_url_descriptions(
            url_tree_file="/path/to/your/data/Agentrek_expriment/url_tree_url_tree_structure.txt",
            accessibility_dir="/path/to/your/data/Agentrek_expriment/crawled_websites/espn.com",
            output_file="url_descriptions.json",
            max_content=15000,
            batch_size=15  # Smaller batch size for more reliable processing
        )
        
        if 'error' not in result:
            print(f"\n🎉 Successfully completed URL description generation!")
            print(f"📈 Overall success rate: {result['description_success_rate']:.1f}%")
            print(f"📝 Generated descriptions for {result['descriptions_generated']} URLs")
            print(f"📄 Output format: Dictionary with normalized URLs as keys, descriptions as values")
            
            # Show a sample of the output
            if 'url_descriptions' in result and result['url_descriptions']:
                print(f"\n📋 Sample descriptions:")
                sample_urls = list(result['url_descriptions'].keys())[:3]
                for i, url in enumerate(sample_urls, 1):
                    description = result['url_descriptions'][url]
                    print(f"  {i}. {url}")
                    print(f"     → {description[:100]}{'...' if len(description) > 100 else ''}")
        else:
            print(f"\n❌ Error: {result['error']}")
            
    except Exception as e:
        print(f"\n💥 Fatal error during description generation: {e}")
        import traceback
        traceback.print_exc()
