#!/usr/bin/env python3.11
"""
Analyze the PRX RSS feed structure and extract all available fields.

This script fetches the RSS feed and provides a comprehensive analysis
of all data elements that could be used for creating Ghost posts.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request


def analyze_feed(feed_url: str) -> dict:
    """Fetch and analyze the RSS feed."""

    print(f"Fetching RSS feed from: {feed_url}")

    # Add user agent to avoid 403 errors
    req = Request(feed_url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; PodcastAggregator/1.0)'
    })

    with urlopen(req) as response:
        xml_content = response.read().decode('utf-8')

    # Parse XML
    root = ET.fromstring(xml_content)

    # Extract channel-level information
    channel = root.find('channel')

    channel_info = {}
    if channel is not None:
        for child in channel:
            if child.tag != 'item':
                channel_info[child.tag] = child.text or ""
                # Also capture attributes
                if child.attrib:
                    channel_info[f"{child.tag}_attributes"] = child.attrib

    # Analyze items (episodes)
    items = channel.findall('item') if channel is not None else []

    print(f"\nFound {len(items)} episodes in the feed")

    # Collect all unique fields across all items
    all_fields = set()
    field_examples = {}
    field_namespaces = {}

    for item in items:
        for child in item:
            # Get tag with namespace
            tag_full = child.tag
            # Get tag without namespace
            tag_local = tag_full.split('}')[-1] if '}' in tag_full else tag_full

            all_fields.add(tag_local)

            # Store namespace info
            if '}' in tag_full:
                namespace = tag_full.split('}')[0].strip('{')
                field_namespaces[tag_local] = namespace

            # Store an example value (from first occurrence)
            if tag_local not in field_examples:
                value = child.text or ""
                if child.attrib:
                    value = f"Text: {value}, Attributes: {child.attrib}"
                field_examples[tag_local] = value[:500]  # Truncate long values

    # Detailed analysis of first item
    first_item_analysis = {}
    if items:
        first_item = items[0]
        for child in first_item:
            tag_local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            first_item_analysis[tag_local] = {
                "text": child.text or "",
                "attributes": child.attrib,
                "has_children": len(list(child)) > 0,
            }

            # If has children, include those too
            if len(list(child)) > 0:
                first_item_analysis[tag_local]["children"] = {
                    subchild.tag.split('}')[-1]: subchild.text or ""
                    for subchild in child
                }

    return {
        "feed_url": feed_url,
        "analyzed_at": datetime.utcnow().isoformat(),
        "channel_info": channel_info,
        "total_episodes": len(items),
        "all_fields": sorted(list(all_fields)),
        "field_examples": field_examples,
        "field_namespaces": field_namespaces,
        "first_item_detailed": first_item_analysis,
        "raw_xml_sample": xml_content[:2000],  # First 2000 chars of XML
    }


def main():
    """Analyze the PRX RSS feed and save results."""

    feed_url = "https://f.prxu.org/3329/feed-rss.xml"

    analysis = analyze_feed(feed_url)

    # Save raw XML
    output_dir = Path("knowledge/prx")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save analysis
    analysis_file = output_dir / "feed_analysis.json"
    analysis_file.write_text(json.dumps(analysis, indent=2), encoding='utf-8')

    # Also save a more readable markdown version
    md_file = output_dir / "feed_structure.md"

    md_content = f"""# PRX RSS Feed Structure Analysis

**Feed URL:** {feed_url}
**Analyzed:** {analysis['analyzed_at']}
**Total Episodes:** {analysis['total_episodes']}

## Channel Information

"""

    for key, value in sorted(analysis['channel_info'].items()):
        if not key.endswith('_attributes') and len(str(value)) < 200:
            md_content += f"- **{key}:** {value}\n"

    md_content += "\n## Available Fields Per Episode\n\n"
    md_content += "The following fields are available in episode items:\n\n"

    for field in analysis['all_fields']:
        namespace = analysis['field_namespaces'].get(field, 'standard RSS')
        example = analysis['field_examples'].get(field, '')

        md_content += f"### `{field}`\n\n"
        md_content += f"**Namespace:** {namespace}\n\n"

        if example:
            # Truncate very long examples
            if len(example) > 300:
                example = example[:300] + "..."
            md_content += f"**Example:**\n```\n{example}\n```\n\n"

    md_content += "\n## First Episode Detailed Analysis\n\n"
    md_content += "```json\n"
    md_content += json.dumps(analysis['first_item_detailed'], indent=2)
    md_content += "\n```\n"

    md_file.write_text(md_content, encoding='utf-8')

    print(f"\n✓ Analysis saved to {analysis_file}")
    print(f"✓ Markdown report saved to {md_file}")
    print(f"\nFound {len(analysis['all_fields'])} unique fields across all episodes")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
