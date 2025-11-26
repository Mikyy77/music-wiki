#!/usr/bin/env python3
"""
View artist as simplified JSON with only titles for releases and recordings
"""

import json
import sys
import argparse
from pathlib import Path


def simplify_artist(record):
    """
    Simplify artist record by keeping only titles for releases and recordings
    
    Args:
        record: Full artist record dictionary
        
    Returns:
        Simplified record dictionary
    """
    simplified = record.copy()
    
    # Simplify releases - keep only titles
    if 'releases' in simplified and simplified['releases']:
        simplified['releases'] = [
            release.get('title', 'Unknown')
            for release in simplified['releases']
        ]
    
    # Simplify recordings - keep only titles
    if 'recordings' in simplified and simplified['recordings']:
        simplified['recordings'] = [
            recording.get('title', 'Unknown')
            for recording in simplified['recordings']
        ]
    
    return simplified


def view_artist_json(artist_name, input_file, compact=False):
    """
    Display artist as simplified JSON
    
    Args:
        artist_name: Name of the artist to search for
        input_file: Path to JSONL file
        compact: If True, output compact JSON (no indentation)
    """
    found = False
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            
            # Case-insensitive search
            if record.get('name', '').lower() == artist_name.lower():
                found = True
                simplified = simplify_artist(record)
                
                if compact:
                    print(json.dumps(simplified, ensure_ascii=False))
                else:
                    print(json.dumps(simplified, indent=2, ensure_ascii=False))
                break
    
    if not found:
        print(f"❌ Artist '{artist_name}' not found in {input_file}", file=sys.stderr)
        print(f"\nTip: Try searching with partial name:", file=sys.stderr)
        print(f"  grep -i '{artist_name}' {input_file} | jq -r '.name' | head -5", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="View artist as simplified JSON with only titles for releases/recordings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View The Beatles with formatted JSON
  python3 view_artist_json.py "The Beatles"
  
  # View compact JSON (one line)
  python3 view_artist_json.py "David Bowie" --compact
  
  # Pipe to jq for further processing
  python3 view_artist_json.py "Metallica" | jq '.releases | length'
  
  # Save to file
  python3 view_artist_json.py "Pink Floyd" > pink_floyd.json
  
  # View from different file
  python3 view_artist_json.py "Radiohead" -f data/joined_artists_flat.jsonl
        """
    )
    
    parser.add_argument(
        'artist_name',
        help='Name of the artist to view (case-insensitive)'
    )
    
    parser.add_argument(
        '-f', '--file',
        default='data/joined_artists_filtered.jsonl',
        help='Input JSONL file (default: data/joined_artists_filtered.jsonl)'
    )
    
    parser.add_argument(
        '-c', '--compact',
        action='store_true',
        help='Output compact JSON (no indentation)'
    )
    
    args = parser.parse_args()
    
    # Check if file exists
    if not Path(args.file).exists():
        print(f"❌ Error: File '{args.file}' not found!", file=sys.stderr)
        sys.exit(1)
    
    view_artist_json(args.artist_name, args.file, args.compact)


if __name__ == "__main__":
    main()
