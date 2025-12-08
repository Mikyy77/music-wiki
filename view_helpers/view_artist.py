#!/usr/bin/env python3
"""
View detailed information about a specific artist from the joined data
"""

import json
import sys
import argparse
from pathlib import Path


def format_list(items, prefix="  • "):
    """Format a list of items with bullets"""
    if not items:
        return "  None"
    return "\n".join([f"{prefix}{item}" for item in items])


def format_releases(releases):
    """Format release information"""
    if not releases:
        return "  None"
    
    output = []
    for release in releases[:10]:  # Show first 10
        title = release.get('title', 'Unknown')
        dates = release.get('dates', [])
        date = dates[0] if dates else 'Unknown date'
        formats = release.get('formats', [])
        format_str = formats[0] if formats else 'Unknown format'
        output.append(f"  • {title} ({date}, {format_str})")
    
    if len(releases) > 10:
        output.append(f"  ... and {len(releases) - 10} more releases")
    
    return "\n".join(output)


def format_recordings(recordings):
    """Format recording information"""
    if not recordings:
        return "  None"
    
    output = []
    for recording in recordings[:15]:  # Show first 15
        title = recording.get('title', 'Unknown')
        length = recording.get('avg_length_sec', 0)
        if length:
            minutes = int(length // 60)
            seconds = int(length % 60)
            time_str = f"{minutes}:{seconds:02d}"
        else:
            time_str = "?"
        output.append(f"  • {title} ({time_str})")
    
    if len(recordings) > 15:
        output.append(f"  ... and {len(recordings) - 15} more recordings")
    
    return "\n".join(output)


def view_artist(artist_name, input_file):
    """
    Display detailed information about an artist
    
    Args:
        artist_name: Name of the artist to search for
        input_file: Path to JSONL file
    """
    found = False
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            
            # Case-insensitive search
            if record.get('name', '').lower() == artist_name.lower():
                found = True
                
                print("=" * 80)
                print(f"🎵 ARTIST PROFILE")
                print("=" * 80)
                
                # Basic Info
                print(f"\n📌 BASIC INFORMATION")
                print(f"   MusicBrainz Name:  {record.get('name', 'N/A')}")
                print(f"   Wikipedia Title:   {record.get('title', 'N/A')}")
                print(f"   Type:              {record.get('type', 'N/A')} (MB) / {record.get('wiki_type', 'N/A')} (Wiki)")
                print(f"   UUID:              {record.get('uuid', 'N/A')}")
                
                # Location
                area = record.get('area', '')
                origin = record.get('origin', '')
                founded_in = record.get('founded_in', '')
                if area or origin or founded_in:
                    print(f"\n📍 LOCATION")
                    if area:
                        print(f"   Area:              {area}")
                    if origin:
                        print(f"   Origin:            {origin}")
                    if founded_in:
                        print(f"   Founded In:        {founded_in}")
                
                # Dates
                founded = record.get('founded', '')
                years_active = record.get('years_active', '')
                if founded or years_active:
                    print(f"\n📅 DATES")
                    if founded:
                        print(f"   Founded:           {founded}")
                    if years_active:
                        print(f"   Years Active:      {years_active}")
                
                # Genres
                genres = record.get('genres', [])
                wiki_genre = record.get('genre', '')
                if genres or wiki_genre:
                    print(f"\n🎸 GENRES")
                    if genres:
                        print(f"   MusicBrainz:       {', '.join(genres)}")
                    if wiki_genre:
                        print(f"   Wikipedia:         {wiki_genre}")
                
                # Abstract
                abstract = record.get('abstract', '')
                if abstract:
                    print(f"\n📖 DESCRIPTION")
                    # Wrap text at 75 characters
                    words = abstract.split()
                    lines = []
                    current_line = "   "
                    for word in words:
                        if len(current_line) + len(word) + 1 <= 75:
                            current_line += word + " "
                        else:
                            lines.append(current_line.rstrip())
                            current_line = "   " + word + " "
                    if current_line.strip():
                        lines.append(current_line.rstrip())
                    print("\n".join(lines))
                
                # Categories
                categories = record.get('categories', [])
                if categories:
                    print(f"\n🏷️  WIKIPEDIA CATEGORIES")
                    print(format_list(categories[:10]))
                    if len(categories) > 10:
                        print(f"   ... and {len(categories) - 10} more categories")
                
                # Members/Relationships
                relationships = record.get('relationships', {})
                members = relationships.get('members', [])
                if members:
                    print(f"\n👥 MEMBERS")
                    for member in members:
                        print(f"   • {member.get('name', 'Unknown')}")
                
                # Rating
                rating_value = record.get('rating_value')
                rating_percent = record.get('rating_percent')
                if rating_value or rating_percent:
                    print(f"\n⭐ RATING")
                    if rating_value:
                        print(f"   Value:             {rating_value}")
                    if rating_percent:
                        print(f"   Percentage:        {rating_percent}%")
                
                # Statistics
                releases = record.get('releases', [])
                recordings = record.get('recordings', [])
                print(f"\n📊 STATISTICS")
                print(f"   Total Releases:    {len(releases)}")
                print(f"   Total Recordings:  {len(recordings)}")
                
                # Releases
                if releases:
                    print(f"\n💿 RELEASES (showing up to 10)")
                    print(format_releases(releases))
                
                # Recordings
                if recordings:
                    print(f"\n🎵 RECORDINGS (showing up to 15)")
                    print(format_recordings(recordings))
                
                # URLs
                print(f"\n🔗 LINKS")
                print(f"   MusicBrainz:       {record.get('url', 'N/A')}")
                print(f"   Wikipedia:         {record.get('wiki_url', 'N/A')}")
                
                print("\n" + "=" * 80)
                break
    
    if not found:
        print(f"❌ Artist '{artist_name}' not found in {input_file}")
        print(f"\nTip: Try searching with partial name:")
        print(f"  grep -i '{artist_name}' {input_file} | jq -r '.name' | head -5")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="View detailed artist information from joined data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View The Beatles
  python3 view_artist.py "The Beatles"
  
  # View David Bowie
  python3 view_artist.py "David Bowie"
  
  # View from different file
  python3 view_artist.py "Metallica" -f data/joined_artists_flat.jsonl
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
    
    args = parser.parse_args()
    
    # Check if file exists
    if not Path(args.file).exists():
        print(f"❌ Error: File '{args.file}' not found!")
        sys.exit(1)
    
    view_artist(args.artist_name, args.file)


if __name__ == "__main__":
    main()
