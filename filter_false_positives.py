#!/usr/bin/env python3
"""
Filter out false positive matches based on Wikipedia categories
"""
import json

# Categories that indicate NON-music entities (must be primary, not secondary)
FALSE_POSITIVE_KEYWORDS = [
    'greek gods', 'roman gods', 'greek deities', 'roman deities',
    'mythological', 'mythology',
    'biblical', 'kings of israel', 'monarchs', 'pharaohs',
    'saints',
    'fictional characters',
    'television characters',
    'film characters'
]

def is_false_positive(record):
    """Check if record is likely a false positive based on categories"""
    categories_str = ' '.join(record.get('categories', [])).lower()
    
    # Keep virtual/fictional bands - they're real music acts
    if any(keyword in categories_str for keyword in ['musical groups', 'music groups', 'rock groups', 'hip-hop groups']):
        return False
    
    # Check for obvious false positive indicators
    for fp_keyword in FALSE_POSITIVE_KEYWORDS:
        if fp_keyword in categories_str:
            return True
    
    # Check if it has NO music-related categories at all
    music_keywords = ['music', 'singer', 'song', 'album', 'band', 'artist', 'musician', 'record']
    has_music = any(keyword in categories_str for keyword in music_keywords)
    
    # If no music categories and very few total categories, likely false positive
    if not has_music and len(record.get('categories', [])) > 5:
        return True
    
    return False

def main():
    input_file = 'data/joined_artists_flat.jsonl'
    output_file = 'data/joined_artists_filtered.jsonl'
    
    total = 0
    filtered_out = 0
    kept = 0
    duplicates = 0
    seen_uuids = set()
    
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            total += 1
            record = json.loads(line)
            
            # Check for duplicates by UUID
            uuid = record.get('uuid')
            if uuid in seen_uuids:
                duplicates += 1
                print(f"Duplicate: {record['name']} (UUID: {uuid})")
                continue
            
            if is_false_positive(record):
                filtered_out += 1
                print(f"Filtered: {record['name']} -> {record['title']}")
            else:
                seen_uuids.add(uuid)
                kept += 1
                outfile.write(line)
    
    print(f"\n{'='*60}")
    print(f"Total records:     {total:,}")
    print(f"Kept:              {kept:,}")
    print(f"Filtered out:      {filtered_out:,}")
    print(f"Duplicates:        {duplicates:,}")
    print(f"{'='*60}")
    print(f"\nCreated: {output_file}")

if __name__ == "__main__":
    main()
