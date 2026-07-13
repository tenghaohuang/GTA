from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import json
import re
import argparse
import os

def create_task_retrieval_index(parsed_results):
    """
    Create a retrieval index using page content as context for embeddings.
    
    Args:
        parsed_results: List of parsed results containing URLs, tasks, and page content
    
    Returns:
        dict: Contains embeddings (from page content), task_texts, urls, and model for retrieval
    """
    # Initialize sentence transformer model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Prepare data for indexing
    task_texts = []
    urls = []
    task_metadata = []
    
    for result in parsed_results:
        url = result['url']
        for task in result['tasks']:
            # Use page content as context for embedding generation
            # This provides richer context than just task descriptions
            web_content = result['page_content']
            task_texts.append(web_content)
            urls.append(url)
            task_metadata.append({
                'url': url,
                'task': task['task'],
                'evaluation_criteria': task['evaluation_criteria']
            })
    
    # Generate embeddings for all page content contexts
    print(f"Generating embeddings for {len(task_texts)} tasks...")
    embeddings = model.encode(task_texts, show_progress_bar=True)
    
    # Create the retrieval index
    index = {
        'embeddings': embeddings,
        'task_texts': task_texts,
        'urls': urls,
        'task_metadata': task_metadata,
        'model': model
    }
    
    return index

def retrieve_similar_tasks(query, index, top_k=5, similarity_threshold=0.3):
    """
    Retrieve URLs with tasks similar to the query.
    
    Args:
        query (str): Query text to find similar tasks
        index (dict): The retrieval index
        top_k (int): Number of top results to return
        similarity_threshold (float): Minimum similarity score
    
    Returns:
        list: List of similar tasks with URLs and similarity scores
    """
    # Encode the query
    query_embedding = index['model'].encode([query])
    
    # Calculate similarities
    similarities = cosine_similarity(query_embedding, index['embeddings'])[0]
    
    # Get top-k most similar tasks
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        if similarities[idx] >= similarity_threshold:
            results.append({
                'url': index['urls'][idx],
                'task': index['task_metadata'][idx]['task'],
                'evaluation_criteria': index['task_metadata'][idx]['evaluation_criteria'],
                'similarity_score': float(similarities[idx]),
                'task_context': index['task_texts'][idx]
            })
    
    return results

def create_multi_hop_task(similar_tasks, max_hops=3):
    """
    Create a complex multi-hop task from similar tasks.
    
    Args:
        similar_tasks (list): List of similar tasks from retrieval
        max_hops (int): Maximum number of hops/steps in the complex task
    
    Returns:
        dict: Complex multi-hop task with steps and evaluation criteria
    """
    if len(similar_tasks) < 2:
        return None
    
    # Select diverse URLs for multi-hop task
    selected_tasks = []
    used_urls = set()
    
    for task in similar_tasks:
        if task['url'] not in used_urls and len(selected_tasks) < max_hops:
            selected_tasks.append(task)
            used_urls.add(task['url'])
    
    if len(selected_tasks) < 2:
        return None
    
    # Create multi-hop task description
    multi_hop_task = {
        'task_type': 'multi_hop',
        'steps': [],
        'urls': [],
        'overall_task': f"Complete a multi-step task across {len(selected_tasks)} different websites",
        'evaluation_criteria': []
    }
    
    for i, task in enumerate(selected_tasks, 1):
        step = {
            'step_number': i,
            'url': task['url'],
            'task': task['task'],
            'evaluation_criteria': task['evaluation_criteria']
        }
        multi_hop_task['steps'].append(step)
        multi_hop_task['urls'].append(task['url'])
        multi_hop_task['evaluation_criteria'].append(f"Step {i}: {task['evaluation_criteria']}")
    
    return multi_hop_task

def save_retrieval_index(index, filepath):
    """Save the retrieval index to disk."""
    with open(filepath, 'wb') as f:
        pickle.dump(index, f)
    print(f"Retrieval index saved to {filepath}")

def load_retrieval_index(filepath):
    """Load the retrieval index from disk."""
    with open(filepath, 'rb') as f:
        index = pickle.load(f)
    print(f"Retrieval index loaded from {filepath}")
    return index



def parse_user_task_result(entry):
    """
    Parses a dict with keys 'url', 'result', and 'page_content', where 'result' is a string
    containing a JSON list of tasks (possibly wrapped in triple backticks and/or 'json' code block).

    Returns:
        dict with keys:
            - url (str)
            - tasks (list of dicts with 'task' and 'evaluation_criteria')
            - page_content (str)
    """
    url = entry.get('url')
    page_content = entry.get('page_content')
    result_str = entry.get('result', '')

    # Remove triple backticks and optional 'json' language marker
    # e.g. ```json\n[ ... ]\n```
    result_str = result_str.strip()
    # Remove code block markers if present
    if result_str.startswith("```"):
        # Remove the first line (```json or ```)
        lines = result_str.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove the last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        result_str = "\n".join(lines).strip()

    # Now try to parse the JSON
    try:
        tasks = json.loads(result_str)
    except Exception as e:
        # If parsing fails, try to extract the first JSON array using regex
        match = re.search(r'(\[.*\])', result_str, re.DOTALL)
        if match:
            try:
                tasks = json.loads(match.group(1))
            except Exception as e2:
                print(f"Failed to parse tasks JSON for url {url}: {e2}")
                tasks = []
        else:
            print(f"Failed to find JSON array in result for url {url}: {e}")
            tasks = []

    return {
        "url": url,
        "tasks": tasks,
        "page_content": page_content
    }



def main():
    parser = argparse.ArgumentParser(description='Create and test a retrieval index for tasks')
    parser.add_argument('input_file', help='Path to the JSON file with user task results')
    parser.add_argument('output_file', help='Path to save the retrieval index (pkl file)')
    parser.add_argument('--query', help='Optional query to test retrieval')
    parser.add_argument('--top-k', type=int, default=10, help='Number of top results to return (default: 10)')
    parser.add_argument('--similarity-threshold', type=float, default=0.3, help='Minimum similarity score (default: 0.3)')
    parser.add_argument('--max-hops', type=int, default=3, help='Maximum number of hops for multi-hop tasks (default: 3)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found")
        return
    
    # Create the retrieval index from parsed results
    with open(args.input_file, 'r', encoding='utf-8') as f:
        user_task_results = json.load(f)
    
    print("Creating task retrieval index...")
    parsed_results = []
    for result in user_task_results:
        parsed = parse_user_task_result(result)
        if parsed['tasks']:  # Only include results with valid tasks
            parsed_results.append(parsed)
    
    if args.verbose:
        print(f"Parsed {len(parsed_results)} valid results from {len(user_task_results)} total entries")
    
    retrieval_index = create_task_retrieval_index(parsed_results)
    print(f"Created index with {len(retrieval_index['task_texts'])} task entries")
    
    # Save the index
    save_retrieval_index(retrieval_index, args.output_file)
    
    # Test retrieval if query is provided
    if args.query:
        print(f"\nTesting retrieval with query: '{args.query[:100]}{'...' if len(args.query) > 100 else ''}'")
        similar_tasks = retrieve_similar_tasks(args.query, retrieval_index, top_k=args.top_k, similarity_threshold=args.similarity_threshold)
        
        print(f"\nFound {len(similar_tasks)} similar tasks:")
        for i, task in enumerate(similar_tasks, 1):
            print(f"{i}. URL: {task['url']}")
            print(f"   Task: {task['task']}")
            print(f"   Similarity: {task['similarity_score']:.3f}")
            if args.verbose:
                print(f"   Evaluation: {task['evaluation_criteria']}")
            print()
        
        # Create multi-hop task example
        if len(similar_tasks) >= 2:
            multi_hop_task = create_multi_hop_task(similar_tasks, max_hops=args.max_hops)
            if multi_hop_task:
                print(f"\nExample multi-hop task created with {len(multi_hop_task['steps'])} steps:")
                print(f"Overall task: {multi_hop_task['overall_task']}")
                for step in multi_hop_task['steps']:
                    print(f"  Step {step['step_number']}: {step['task']} (URL: {step['url']})")


if __name__ == "__main__":
    main()