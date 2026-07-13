# GTA: Generating Long-Horizon Tasks for Web Agents at Scale

Official code for **"GTA: Generating Long-Horizon Tasks for Web Agents at Scale"**, accepted to **ACL 2026** (Main, Volume 1).

GTA is a scalable pipeline for generating realistic, multi-hop web-agent tasks paired with executable ground-truth trajectories. It crawls websites into a site graph, retrieves related pages to seed compositional task generation, filters candidates through automated quality control, and records a minimal executable path for deterministic replay. The pipeline has been run on 50+ public websites across e-commerce, healthcare, finance, government, and news domains, in multiple languages, producing both intra-website and cross-website tasks.

## Why GTA

Prior automatic task-generation methods rely on LLM-driven exploration, which is expensive, biased toward "obvious" navigation paths, and tends to collapse into single-hop lookups. GTA instead grounds task generation in the crawled site graph itself, which:

- separates one-time crawling from lightweight, retrieval-seeded generation (far cheaper per task)
- samples diverse, semantically rich regions of a site instead of overfitting to the same few pages
- yields genuinely compositional, multi-hop tasks with a verified, minimal, replayable gold path

See the paper for full details, benchmark results, and human evaluation.

## Pipeline Overview

```
1. Crawl            core/crawler/            -> build a site graph (accessibility trees + link structure)
2. Index & Retrieve  retrieval/indexing/      -> embed pages, build a retrieval index over the graph
3. Generate Tasks    task_generation/         -> retrieval-seeded, in-context multi-hop task generation
4. Verify            task_generation/evaluation/ -> multi-hop / correctness / ambiguity / solvability checks
```

Each generated task is a `<query, answer, path>` triple, where `path` is a minimal sequence of pages that must be visited to derive the answer, enabling deterministic replay and step-level diagnostics.

## Installation

```bash
pip install playwright
playwright install chromium
```

## Quick Start

**1. Crawl a website into a site graph**
```bash
python core/crawler/crawl_target_websites.py
```

**2. Build a retrieval index over the crawled pages**
```bash
python retrieval/indexing/create_webpage_retrieval_index.py \
    data/indices/url_descriptions.json data/indices/webpage_index.pkl
```

**3. Generate multi-hop tasks**
```bash
python task_generation/generators/multi_hop_task_gen.py
```

Cross-website tasks (coordinating across multiple domains) can be generated with:
```bash
python task_generation/generators/cross_website_multi_hop.py
```

## Project Structure

```
core/               Accessibility-tree extraction and web crawling
retrieval/          Embedding-based indexing and search over crawled pages
task_generation/    Multi-hop task generators and quality-control/evaluation
data/               Crawl outputs, generated tasks, and indices
config/             Sample configuration files
notebooks/          Interactive examples
docs/               Extended docs for the crawler and retrieval components
```

For lower-level details (cookie handling, crawl constraints, output formats, config options), see [docs/README_CRAWLER.md](docs/README_CRAWLER.md) and [docs/README_webpage_retrieval.md](docs/README_webpage_retrieval.md).

## Citation

If you find this work useful, please cite:

```bibtex
@inproceedings{huang2026gta,
  title     = {{GTA}: Generating Long-Horizon Tasks for Web Agents at Scale},
  author    = {Huang, Tenghao and Huang, Kung-Hsiang and Choubey, Prafulla Kumar and Zhou, Yilun and Chen, Muhao and May, Jonathan and Wu, Chien-Sheng},
  booktitle = {Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  pages     = {18805--18820},
  year      = {2026},
  month     = jul,
  address   = {Vienna, Austria},
  publisher = {Association for Computational Linguistics}
}
```

## Ethics & Data Use

Crawling is restricted to publicly accessible pages and respects each site's `robots.txt` and rate limits; no login-gated content, personal accounts, or transactional flows are accessed. See the paper's Ethics Statement for full details.

## License

This project builds on the WebArena implementation and follows similar licensing terms.
