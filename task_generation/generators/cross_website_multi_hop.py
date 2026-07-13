#!/usr/bin/env python3
"""
Cross-Website Multi-Hop Task Generator

This script generates multi-hop tasks by randomly sampling one webpage from each of two folders
and creating queries that require information from both pages.

Modified to:
- Take two folder arguments (--folder1 and --folder2) instead of one
- Randomly sample one webpage from each folder for each task pair
- Generate cross-website multi-hop queries spanning different domains

Usage:
    python cross_website_multi_hop.py --folder1 student_com --folder2 ticketcenter_com --output multi_hop_tasks.json --num-pairs 50
"""

import json
import argparse
import os
import sys
import random
from tqdm import tqdm
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Import our utility functions
from AA_utils import get_LLM_response
from aysnc_llm_call import process_llm_batch_calls


def parse_arguments():
    """
    Parse command line arguments for the multi-hop task generation script.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Multi-hop Task Generator - Generate queries spanning multiple webpages using accessibility tree files from two different folders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --folder1 student_com --folder2 ticketcenter_com --output multi_hop_tasks.json --num-pairs 50
  %(prog)s --folder1 student_com --folder2 ticketcenter_com --output multi_hop_tasks.json --num-pairs 100 --max-content 20000
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--folder1',
        type=str,
        required=True,
        help='First directory containing accessibility tree files'
    )
    
    parser.add_argument(
        '--folder2',
        type=str,
        required=True,
        help='Second directory containing accessibility tree files'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='multi_hop_tasks.json',
        help='Path to the output JSON file (default: multi_hop_tasks.json)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--num-pairs',
        type=int,
        default=50,
        help='Number of page pairs to generate multi-hop tasks for (default: 50)'
    )
    
    parser.add_argument(
        '--max-content',
        type=int,
        default=15000,
        help='Maximum content length per page to include in LLM prompt (default: 15000)'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducible sampling (default: 42)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()


def get_accessibility_files(accessibility_dir: str) -> List[str]:
    """
    Get list of accessibility tree files from the specified directory.
    
    Args:
        accessibility_dir (str): Directory containing accessibility tree files
    
    Returns:
        List[str]: List of accessibility tree file paths
    """
    if not os.path.exists(accessibility_dir):
        raise FileNotFoundError(f"Accessibility directory not found: {accessibility_dir}")
    
    files = []
    for filename in os.listdir(accessibility_dir):
        if filename.startswith('page_') and filename.endswith('.txt'):
            files.append(os.path.join(accessibility_dir, filename))
    
    return files


def read_accessibility_tree_file(file_path: str, max_content: int = 15000) -> Dict:
    """
    Read and parse an accessibility tree file.
    
    Args:
        file_path (str): Path to the accessibility tree file
        max_content (int): Maximum content length to extract
    
    Returns:
        Dict: Parsed file information including URL, title, content
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Extract metadata from the first few lines
        url = ""
        title = ""
        depth = ""
        
        for line in lines[:10]:  # Check first 10 lines for metadata
            if line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
            elif line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
            elif line.startswith('Depth:'):
                depth = line.replace('Depth:', '').strip()
        
        # Get the accessibility tree content (after the separator line)
        separator_index = -1
        for i, line in enumerate(lines):
            if '---' in line:
                separator_index = i
                break
        
        if separator_index != -1:
            tree_content = '\n'.join(lines[separator_index + 1:])
        else:
            tree_content = content
        
        # Limit content length
        if len(tree_content) > max_content:
            tree_content = tree_content[:max_content] + "... [TRUNCATED]"
        
        return {
            'success': True,
            'file_path': file_path,
            'url': url,
            'title': title,
            'depth': depth,
            'content': tree_content,
            'content_length': len(tree_content)
        }
        
    except Exception as e:
        return {
            'success': False,
            'file_path': file_path,
            'error': str(e),
            'url': '',
            'title': '',
            'content': '',
            'content_length': 0
        }


def sample_cross_folder_pairs(files1: List[str], files2: List[str], num_pairs: int, seed: int = 42) -> List[Tuple[str, str]]:
    """
    Randomly sample pairs by selecting one file from each folder.
    
    Args:
        files1 (List[str]): List of file paths from first folder
        files2 (List[str]): List of file paths from second folder
        num_pairs (int): Number of pairs to sample
        seed (int): Random seed for reproducibility
    
    Returns:
        List[Tuple[str, str]]: List of file path pairs (file from folder1, file from folder2)
    """
    random.seed(seed)
    
    if len(files1) < 1:
        raise ValueError("Need at least 1 file in first folder")
    if len(files2) < 1:
        raise ValueError("Need at least 1 file in second folder")
    
    pairs = []
    for _ in range(num_pairs):
        # Sample one file from each folder
        file1 = random.choice(files1)
        file2 = random.choice(files2)
        pairs.append((file1, file2))
    
    return pairs


def generate_multi_hop_task_prompt(page1_data: Dict, page2_data: Dict) -> str:
    """
    Create a prompt for generating multi-hop tasks that span two webpages.
    
    Args:
        page1_data (Dict): Data from first accessibility tree file
        page2_data (Dict): Data from second accessibility tree file
    
    Returns:
        str: The formatted prompt for the LLM
    """
    
    prompt = f"""You are a helpful assistant that creates multi-hop user tasks that span across multiple webpages. Multi-hop tasks require information, actions, or navigation across multiple pages to complete successfully.

You are given two different webpages with their accessibility tree content. Your job is to analyze both pages and generate meaningful multi-hop tasks that a real user might want to accomplish using both pages.

=== PAGE 1 ===
URL: {page1_data['url']}
Title: {page1_data['title']}
Accessibility Tree Content:
{page1_data['content']}

=== PAGE 2 ===
URL: {page2_data['url']}
Title: {page2_data['title']}
Accessibility Tree Content:
{page2_data['content']}

=== TASK REQUIREMENTS ===

Generate multi-hop tasks that:
1. **Require information from BOTH pages** - The task cannot be completed using just one page
2. **Are realistic and meaningful** - Something a real user would actually want to do
3. **Leverage the specific functionality** of both pages based on their content
4. **Are actionable and measurable** - Clear success criteria can be established

=== MULTI-HOP TASK TYPES ===

Consider these types of multi-hop tasks:
- **Comparison tasks**: Compare information, features, prices, or options across both pages
- **Information aggregation**: Gather complementary information from both pages
- **Cross-reference tasks**: Use information from one page to verify or enhance information from another
- **Sequential workflow**: Complete a process that requires steps on both pages
- **Decision-making**: Use both pages to make an informed choice or recommendation

=== OUTPUT FORMAT ===

Generate 2-3 multi-hop tasks in the following JSON format:

[
    {{
        "task": "Compare the rent prices for student accommodation between [specific property from page 1] and [specific property from page 2], and determine which offers better value considering location and amenities.",
        "evaluation_criteria": "The task requires extracting rent prices from both pages, identifying the locations and amenities of each property, and providing a comparative analysis. Success criteria: (1) Correctly identify rent prices from both pages, (2) List key amenities and location advantages of each property, (3) Provide reasoned recommendation based on value proposition.",
        "pages_required": ["Page 1: Extract price and amenities info", "Page 2: Extract price and amenities info"],
        "task_type": "comparison"
    }},
    {{
        "task": "Find the cheapest accommodation option between the two pages and then look up additional information about the area or university nearby using the other page.",
        "evaluation_criteria": "Task requires price comparison across both pages to identify the cheapest option, then using the other page to research the surrounding area, nearby universities, or local amenities. Success criteria: (1) Correctly identify the cheapest option with exact price, (2) Provide relevant area/university information from the other page, (3) Assess if the cheaper option is still a good choice given the location context.",
        "pages_required": ["Page 1: Price comparison", "Page 2: Area/university research"],
        "task_type": "information_aggregation"
    }}
]

=== IMPORTANT GUIDELINES ===

- Make tasks **specific** to the actual content found in both pages
- Ensure tasks **cannot be completed** with just one page
- Focus on **realistic user scenarios** that would naturally span multiple pages
- Include **concrete evaluation criteria** that can be objectively assessed
- Reference **specific elements, prices, names, or features** from the pages when possible
- Make sure the tasks are **challenging but achievable** given the page content

Analyze both pages carefully and generate meaningful multi-hop tasks that showcase the value of using multiple pages together."""

    return prompt


def main():
    """
    Main function to orchestrate the multi-hop task generation process.
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up paths
    folder1 = args.folder1
    folder2 = args.folder2

    # Validate input directories exist
    if not os.path.exists(folder1):
        print(f"Error: First folder '{folder1}' not found")
        sys.exit(1)
    
    if not os.path.exists(folder2):
        print(f"Error: Second folder '{folder2}' not found")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if args.verbose:
        print(f"First folder: {folder1}")
        print(f"Second folder: {folder2}")
        print(f"Output file: {args.output}")
        print(f"Number of pairs: {args.num_pairs}")
        print(f"Max content per page: {args.max_content}")
        print(f"Random seed: {args.seed}")
    
    # Get list of accessibility tree files from both folders
    try:
        files1 = get_accessibility_files(folder1)
        files2 = get_accessibility_files(folder2)
        print(f"Found {len(files1)} accessibility tree files in folder1: {folder1}")
        print(f"Found {len(files2)} accessibility tree files in folder2: {folder2}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    if len(files1) < 1:
        print(f"Error: Need at least 1 accessibility tree file in folder1: {folder1}")
        sys.exit(1)
    
    if len(files2) < 1:
        print(f"Error: Need at least 1 accessibility tree file in folder2: {folder2}")
        sys.exit(1)
    
    # Sample page pairs across folders
    page_pairs = sample_cross_folder_pairs(files1, files2, args.num_pairs, args.seed)
    print(f"Generated {len(page_pairs)} cross-folder page pairs")
    
    if args.verbose:
        print("Sample page pairs:")
        for i, (file1, file2) in enumerate(page_pairs[:5]):
            print(f"{i+1}. [{os.path.basename(folder1)}] {os.path.basename(file1)} <-> [{os.path.basename(folder2)}] {os.path.basename(file2)}")
    
    # Process page pairs and generate prompts
    payload = []
    successful_pairs = []
    
    for file1, file2 in tqdm(page_pairs, desc="Processing page pairs"):
        # Read both accessibility tree files
        page1_data = read_accessibility_tree_file(file1, args.max_content)
        page2_data = read_accessibility_tree_file(file2, args.max_content)
        
        # Skip if either page failed to load
        if not page1_data['success'] or not page2_data['success']:
            if args.verbose:
                print(f"Skipping pair due to read error:")
                if not page1_data['success']:
                    print(f"  Page 1 error: {page1_data.get('error', 'Unknown error')}")
                if not page2_data['success']:
                    print(f"  Page 2 error: {page2_data.get('error', 'Unknown error')}")
            continue
        
        # Generate multi-hop task prompt
        task_prompt = generate_multi_hop_task_prompt(page1_data, page2_data)
        
        example = {
            "messages": [
                {"role": "user", "content": task_prompt}
            ]
        }
        payload.append(example)
        successful_pairs.append((page1_data, page2_data))
    
    print(f"Successfully prepared {len(payload)} pairs for LLM processing")
    
    if len(payload) == 0:
        print("Error: No valid page pairs found for processing")
        sys.exit(1)
    
    if args.verbose:
        print(f"Processing {len(payload)} pairs with LLM...")
    
    # Process LLM batch calls
    try:
        results = process_llm_batch_calls(payload)
        print(f"LLM processing completed for {len(results)} pairs")
    except Exception as e:
        print(f"Error during LLM processing: {e}")
        sys.exit(1)
    
    # Prepare output data
    output_data = []
    
    for (page1_data, page2_data), result in zip(successful_pairs, results):
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
            "max_content_per_page": args.max_content
        }
        output_data.append(output_entry)
    
    # Save results to output file
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"Results saved to {args.output}")
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


if __name__ == "__main__":
    main()
