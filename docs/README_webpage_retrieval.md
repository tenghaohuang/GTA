# Webpage Retrieval Index

This toolkit allows you to create semantic search indices from webpage descriptions and find similar webpages based on functionality and content.

## Overview

The system works in two main steps:
1. **Generate webpage descriptions** using `generate_descriptions_url_tree.py`
2. **Create and use retrieval index** using `create_webpage_retrieval_index.py`

## Prerequisites

Install required dependencies:
```bash
pip install sentence-transformers scikit-learn numpy
```

## Quick Start

### Step 1: Generate Webpage Descriptions (if not done already)

```bash
python generate_descriptions_url_tree.py
```

This creates `url_descriptions.json` with format:
```json
{
    "https://example.com/page1": "Description of page 1 functionality...",
    "https://example.com/page2": "Description of page 2 functionality...",
    ...
}
```

### Step 2: Create Retrieval Index

```bash
python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl
```

### Step 3: Search for Similar Webpages

```bash
# Search by query
python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --query "sports news"

# Search by functionality
python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --functionality search filter

# Group similar webpages
python create_webpage_retrieval_index.py url_descriptions.json webpage_index.pkl --group-similar
```

## Features

### 🔍 Query-based Search
Find webpages similar to a text query:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl --query "video streaming and media"
```

### 🔧 Functionality-based Search
Find webpages with specific functionalities:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl --functionality login account profile
```

### 📊 Webpage Grouping
Group webpages with similar functionality:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl --group-similar --group-threshold 0.7
```

### 💾 Export Results
Export search results to JSON:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl --query "shopping" --export-json results.json
```

## Advanced Usage

### Custom Model Selection
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl --model all-mpnet-base-v2
```

Available models:
- `all-MiniLM-L6-v2` (default, fast)
- `all-mpnet-base-v2` (higher quality, slower)
- `multi-qa-MiniLM-L6-cos-v1` (optimized for Q&A)

### Fine-tuned Parameters
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl \
    --query "user account settings" \
    --functionality login account profile \
    --top-k 15 \
    --similarity-threshold 0.2 \
    --group-similar \
    --group-threshold 0.7 \
    --export-json comprehensive_results.json \
    --verbose
```

## Python API Usage

### Basic Usage
```python
from create_webpage_retrieval_index import (
    load_webpage_descriptions,
    create_webpage_retrieval_index,
    retrieve_similar_webpages,
    save_retrieval_index
)

# Load descriptions
descriptions = load_webpage_descriptions("url_descriptions.json")

# Create index
index = create_webpage_retrieval_index(descriptions)

# Search for similar webpages
results = retrieve_similar_webpages("sports news", index, top_k=10)

# Save index for later use
save_retrieval_index(index, "webpage_index.pkl")
```

### Advanced Features
```python
from create_webpage_retrieval_index import (
    find_webpages_by_functionality,
    group_similar_webpages,
    load_retrieval_index
)

# Load existing index
index = load_retrieval_index("webpage_index.pkl")

# Find by functionality
functionality_results = find_webpages_by_functionality(
    ["search", "filter"], index, top_k=5
)

# Group similar webpages
groups = group_similar_webpages(index, similarity_threshold=0.7)
```

## Example Workflows

### 1. Content Discovery
Find webpages with similar content for competitive analysis:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl \
    --query "product catalog and shopping features" \
    --top-k 20 \
    --export-json similar_ecommerce.json
```

### 2. Functionality Analysis
Group webpages by functionality to understand site structure:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl \
    --group-similar \
    --group-threshold 0.6 \
    --export-json functionality_groups.json
```

### 3. Feature Research
Find webpages with specific features across different sites:
```bash
python create_webpage_retrieval_index.py descriptions.json index.pkl \
    --functionality video streaming playlist \
    --similarity-threshold 0.3 \
    --export-json video_features.json
```

## Output Formats

### Search Results
```json
[
    {
        "url": "https://example.com/page1",
        "description": "Page description...",
        "similarity_score": 0.85
    }
]
```

### Grouped Results
```json
[
    [
        {
            "url": "https://example.com/page1",
            "description": "Page description...",
            "similarity_to_first": 1.0
        },
        {
            "url": "https://example.com/page2", 
            "description": "Similar page description...",
            "similarity_to_first": 0.78
        }
    ]
]
```

## Troubleshooting

### Common Issues

1. **"No descriptions found"**
   - Ensure `url_descriptions.json` exists and contains valid data
   - Check that descriptions are not empty or error messages

2. **"No similar webpages found"**
   - Try lowering the similarity threshold (--similarity-threshold 0.1)
   - Use more general query terms
   - Check if your descriptions contain relevant content

3. **Memory issues with large datasets**
   - Use a smaller model like `all-MiniLM-L6-v2`
   - Process descriptions in smaller batches
   - Filter out very long descriptions

### Performance Tips

1. **Faster searches**: Use `all-MiniLM-L6-v2` model
2. **Better quality**: Use `all-mpnet-base-v2` model  
3. **Large datasets**: Save index once, load multiple times
4. **Batch processing**: Use the Python API for multiple queries

## Files

- `create_webpage_retrieval_index.py` - Main script for creating and using retrieval index
- `example_webpage_retrieval.py` - Example usage and demonstrations
- `generate_descriptions_url_tree.py` - Generates webpage descriptions (prerequisite)
- `url_descriptions.json` - Input file with URL-to-description mappings
- `webpage_index.pkl` - Output retrieval index file

## Next Steps

- Integrate with web crawling pipelines
- Add support for multi-modal content (images, videos)
- Implement more sophisticated grouping algorithms
- Add support for temporal analysis of webpage changes