#!/usr/bin/env python3
"""
View random samples from the joined artists data
"""

import json
import random
import argparse


def view_random_samples(input_file, num_samples=5, compact=False):
    """
    Display random samples from a JSONL file
    
    Args:
        input_file: Path to JSONL file
        num_samples: Number of random samples to display
        compact: If True, show compact view with just key fields
    """
    # Read all lines
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    total = len(lines)
    print(f"📊 Total records: {total:,}")
    print(f"🎲 Showing {min(num_samples, total)} random samples:\n")
    print("=" * 80)
    
    # Get random samples
    samples = random.sample(lines, min(num_samples, total))
    
    for i, line in enumerate(samples, 1):
        record = json.loads(line)
        
        print(f"\n🎵 Sample {i}:")
        print("-" * 80)
        
        if compact:
            # Compact view - just key fields
            print(f"Name (MB):        {record.get('name', 'N/A')}")
            print(f"Title (Wiki):     {record.get('title', 'N/A')}")
            print(f"Type:             {record.get('type', 'N/A')} → {record.get('wiki_type', 'N/A')}")
            print(f"Area/Origin:      {record.get('area', record.get('origin', 'N/A'))}")
            print(f"Genres:           {', '.join(record.get('genres', [])) or record.get('genre', 'N/A')}")
            print(f"MusicBrainz URL:  {record.get('url', 'N/A')}")
            print(f"Wikipedia URL:    {record.get('wiki_url', 'N/A')}")
            
            # Show a snippet of abstract if available
            abstract = record.get('abstract', '')
            if abstract:
                snippet = abstract[:200] + "..." if len(abstract) > 200 else abstract
                print(f"Abstract:         {snippet}")
                
            # Show some stats
            num_releases = len(record.get('releases', []))
            num_recordings = len(record.get('recordings', []))
            if num_releases > 0 or num_recordings > 0:
                print(f"Stats:            {num_releases} releases, {num_recordings} recordings")
        else:
            # Full JSON view
            print(json.dumps(record, indent=2, ensure_ascii=False))
        
        print("-" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="View random samples from joined artists data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View 5 random samples in compact format
  python3 view_random_samples.py
  
  # View 10 random samples
  python3 view_random_samples.py -n 10
  
  # View full JSON format
  python3 view_random_samples.py --full
  
  # View from different file
  python3 view_random_samples.py -f data/joined_artists_flat.jsonl
        """
    )
    
    parser.add_argument(
        '-f', '--file',
        default='data/joined_artists_filtered.jsonl',
        help='Input JSONL file (default: data/joined_artists_filtered.jsonl)'
    )
    
    parser.add_argument(
        '-n', '--num',
        type=int,
        default=5,
        help='Number of random samples to display (default: 5)'
    )
    
    parser.add_argument(
        '--full',
        action='store_true',
        help='Show full JSON instead of compact view'
    )
    
    args = parser.parse_args()
    
    view_random_samples(args.file, args.num, compact=not args.full)


if __name__ == "__main__":
    main()
