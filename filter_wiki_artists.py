#!/usr/bin/env python3
"""
Filter Wikipedia music entities to only include artists and bands.
Excludes albums, genres, instruments, and other non-artist entities.
"""

import json
import argparse
from pathlib import Path
from collections import Counter


def filter_artists(input_file, output_file, types_to_keep=None):
    """
    Filter JSONL file to only keep specified entity types.
    
    Args:
        input_file: Path to input JSONL file
        output_file: Path to output filtered JSONL file
        types_to_keep: List of entity types to keep (default: ['artist', 'band'])
    """
    if types_to_keep is None:
        # Default: keep artists and bands (excludes albums, genres, instruments)
        types_to_keep = ['artist', 'band']
    
    types_to_keep = set(types_to_keep)
    
    stats = {
        'total': 0,
        'kept': 0,
        'filtered_out': 0,
        'type_counts': Counter(),
        'kept_type_counts': Counter()
    }
    
    print(f"Reading from: {input_file}")
    print(f"Writing to: {output_file}")
    print(f"Keeping types: {', '.join(sorted(types_to_keep))}")
    print()
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            stats['total'] += 1
            
            try:
                entity = json.loads(line)
                entity_type = entity.get('type', 'unknown')
                stats['type_counts'][entity_type] += 1
                
                if entity_type in types_to_keep:
                    f_out.write(line)
                    stats['kept'] += 1
                    stats['kept_type_counts'][entity_type] += 1
                else:
                    stats['filtered_out'] += 1
                
                # Progress indicator
                if stats['total'] % 1000 == 0:
                    print(f"Processed {stats['total']:,} entities... Kept {stats['kept']:,}", end='\r')
            
            except json.JSONDecodeError as e:
                print(f"\n⚠️  Warning: Invalid JSON at line {stats['total']}: {e}")
                stats['filtered_out'] += 1
    
    print()  # New line after progress indicator
    print("\n" + "=" * 60)
    print("FILTERING RESULTS")
    print("=" * 60)
    print(f"Total entities processed: {stats['total']:,}")
    print(f"Entities kept:            {stats['kept']:,}")
    print(f"Entities filtered out:    {stats['filtered_out']:,}")
    print(f"Retention rate:           {stats['kept']/stats['total']*100:.1f}%")
    
    print("\nOriginal type distribution:")
    for entity_type, count in stats['type_counts'].most_common():
        print(f"  {entity_type:15s} {count:,}")
    
    print("\nKept type distribution:")
    for entity_type, count in stats['kept_type_counts'].most_common():
        print(f"  {entity_type:15s} {count:,}")
    
    print("=" * 60)
    print(f"\n✅ Filtered data saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Filter Wikipedia music entities to only artists and bands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Keep only artists and bands (default)
  python3 filter_wiki_artists.py --input data/wiki_music.jsonl --output data/wiki_artists_only.jsonl
  
  # Keep only artists
  python3 filter_wiki_artists.py --input data/wiki_music.jsonl --output data/wiki_filtered.jsonl --types artist
  
  # Keep only bands
  python3 filter_wiki_artists.py --input data/wiki_music.jsonl --output data/wiki_artists.jsonl --types band
        """
    )
    
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('data/wiki_music.jsonl'),
        help='Input JSONL file (default: data/wiki_music.jsonl)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/wiki_artists_only.jsonl'),
        help='Output filtered JSONL file (default: data/wiki_artists_only.jsonl)'
    )
    
    parser.add_argument(
        '--types',
        nargs='+',
        default=['artist', 'band'],
        help='Entity types to keep (default: artist band - excludes albums, genres, instruments)'
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"❌ Error: Input file not found: {args.input}")
        return 1
    
    filter_artists(args.input, args.output, args.types)
    return 0


if __name__ == '__main__':
    exit(main())
