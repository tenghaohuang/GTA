#!/usr/bin/env python3

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
        description="Multi-hop Task Generator - Generate queries spanning multiple webpages using accessibility tree files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --accessibility-dir student_com --output multi_hop_tasks.json --num-pairs 50
  %(prog)s --accessibility-dir student_com --output multi_hop_tasks.json --num-pairs 100 --max-content 20000
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--accessibility-dir',
        type=str,
        default='student_com',
        help='Directory containing accessibility tree files (default: student_com)'
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


def sample_page_pairs(files: List[str], num_pairs: int, seed: int = 42) -> List[Tuple[str, str]]:
    """
    Randomly sample pairs of accessibility tree files.
    
    Args:
        files (List[str]): List of file paths
        num_pairs (int): Number of pairs to sample
        seed (int): Random seed for reproducibility
    
    Returns:
        List[Tuple[str, str]]: List of file path pairs
    """
    random.seed(seed)
    
    if len(files) < 2:
        raise ValueError("Need at least 2 files to create pairs")
    
    pairs = []
    for _ in range(num_pairs):
        # Sample two different files
        pair = random.sample(files, 2)
        pairs.append((pair[0], pair[1]))
    
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

Generate DETERMINISTIC tasks with factual, verifiable answers. Focus on these types:
- **Information extraction**: Find specific facts, numbers, dates, or details from both pages
- **Data aggregation**: Calculate totals, counts, or combine numerical data from both pages
- **Cross-verification**: Check if information on one page matches or contradicts the other
- **Sequential lookup**: Use information from one page to find related details on the other
- **Relationship mapping**: Identify connections, dependencies, or links between the pages
- **Fact retrieval**: Answer specific questions that require information from both pages

AVOID open-ended comparisons, subjective evaluations, or "determine which is better" tasks.

=== OUTPUT FORMAT ===

Generate 2-3 multi-hop tasks in the following JSON format. For each task, provide both the task description AND the correct answer based on the information available in both pages:

[
    {{
        "task": "What is the total monthly cost if a student rents the accommodation from page 1 and also subscribes to the internet service plan mentioned on page 2?",
        "evaluation_criteria": "Task requires extracting the exact rental price from page 1 and the internet service cost from page 2, then calculating the total. Success criteria: (1) Correctly identify rent price from page 1, (2) Correctly identify internet service cost from page 2, (3) Provide accurate sum of both costs.",
        "pages_required": ["Page 1: Extract rental price", "Page 2: Extract internet service cost"],
        "task_type": "data_aggregation",
        "answer": "The accommodation rental cost from page 1 is $850 per month for Riverside Apartments. The premium internet service plan from page 2 costs $45 per month. The total monthly cost would be $850 + $45 = $895 per month."
    }},
    {{
        "task": "Does the contact phone number listed for the property management on page 1 match the customer service number provided on page 2?",
        "evaluation_criteria": "Task requires finding the specific phone number on page 1 and the customer service number on page 2, then comparing them for exact match. Success criteria: (1) Extract correct phone number from page 1, (2) Extract correct customer service number from page 2, (3) State whether they match or not.",
        "pages_required": ["Page 1: Extract contact phone number", "Page 2: Extract customer service number"],
        "task_type": "cross_verification",
        "answer": "The property management contact number on page 1 is (555) 123-4567. The customer service number on page 2 is (555) 123-4567. Yes, both numbers match exactly."
    }},
    {{
        "task": "How many total parking spaces are available across all properties mentioned on both pages?",
        "evaluation_criteria": "Task requires counting parking spaces from each property listed on both pages and calculating the sum. Success criteria: (1) Identify all properties on both pages, (2) Extract parking space count for each property, (3) Calculate correct total.",
        "pages_required": ["Page 1: Count parking spaces", "Page 2: Count parking spaces"],
        "task_type": "information_extraction",
        "answer": "From page 1: Riverside Apartments has 120 parking spaces and University Heights has 85 parking spaces. From page 2: Campus Gardens offers 95 parking spaces and Downtown Plaza has 60 parking spaces. Total parking spaces across all properties: 120 + 85 + 95 + 60 = 360 parking spaces."
    }}
]

=== IMPORTANT GUIDELINES ===

- Generate **DETERMINISTIC tasks** with clear, factual answers that can be objectively verified
- Make tasks **specific** to the actual content found in both pages
- Ensure tasks **cannot be completed** with just one page
- Focus on **data extraction, calculation, verification, and fact-finding** rather than subjective comparisons
- Include **concrete evaluation criteria** that can be objectively assessed
- Reference **specific elements, prices, names, numbers, dates, or features** from the pages
- Ask for **exact information** (phone numbers, addresses, prices, counts, dates) rather than opinions
- Create tasks that have **one correct answer** based on the page content

**PRIORITIZE these task types:**
- Counting or calculating totals from both pages
- Verifying if specific information matches between pages
- Finding exact details that require both pages
- Extracting and combining factual data
- Yes/No questions with clear verification criteria

**For the answers:**
- Provide **complete and accurate answers** based solely on the information available in both pages
- Use **specific data, prices, names, and details** found in the actual page content
- Write answers as **factual statements** with exact numbers, names, and details
- If information is missing or unclear, acknowledge this naturally in the answer
- Ensure the answer demonstrates **genuine multi-hop reasoning** that requires both pages
- Include **step-by-step reasoning** showing how information from both pages was combined
- Make answers **deterministic and verifiable** - avoid subjective language or recommendations

Analyze both pages carefully and generate meaningful multi-hop tasks that showcase the value of using multiple pages together."""

    return prompt


def main():
    """
    Main function to orchestrate the multi-hop task generation process.
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up paths
    accessibility_dir = args.accessibility_dir
    


    # Validate input directory exists
    if not os.path.exists(accessibility_dir):
        print(f"Error: Accessibility directory '{accessibility_dir}' not found")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if args.verbose:
        print(f"Accessibility directory: {accessibility_dir}")
        print(f"Output file: {args.output}")
        print(f"Number of pairs: {args.num_pairs}")
        print(f"Max content per page: {args.max_content}")
        print(f"Random seed: {args.seed}")
    
    # Get list of accessibility tree files
    try:
        accessibility_files = get_accessibility_files(accessibility_dir)
        print(f"Found {len(accessibility_files)} accessibility tree files")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    if len(accessibility_files) < 2:
        print("Error: Need at least 2 accessibility tree files to generate multi-hop tasks")
        sys.exit(1)
    
    # Sample page pairs
    page_pairs = sample_page_pairs(accessibility_files, args.num_pairs, args.seed)
    print(f"Generated {len(page_pairs)} page pairs")
    
    if args.verbose:
        print("Sample page pairs:")
        for i, (file1, file2) in enumerate(page_pairs[:5]):
            print(f"{i+1}. {os.path.basename(file1)} <-> {os.path.basename(file2)}")
    
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
