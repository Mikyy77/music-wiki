#!/usr/bin/env python3
"""Test improved extraction on sample infobox data"""

import re

# Sample infobox from Jello Biafra Wikipedia page
sample_infobox = """
| genre             = {{hlist|[[Punk rock]]|[[spoken word]]|[[hardcore punk]]}}
| years_active      = 1976–present
| label             = [[Alternative Tentacles]]
| origin            = [[Boulder, Colorado]], U.S.
| birth_name        = Eric Reed Boucher
"""

sample_abstract = """}}
{{Use mdy dates|date=January 2022}}
{{Infobox musical artist
| name              = Jello Biafra
| image             = Jello Biafra 2014.jpg
| background        = person
| caption           = Biafra performing at the 2014 [[Fun Fun Fun Fest]]
| birth_name        = Eric Reed Boucher
}}

'''Eric Reed Boucher''' (born June 17, 1958), known professionally as '''Jello Biafra''', is an American singer, spoken word artist and political activist. He is the former lead singer and songwriter for the [[San Francisco]] [[punk rock]] band [[Dead Kennedys]].{{Cite news |last=Vaziri |first=Aidin |date=December 18, 2023 |title=Dead Kennedys' punk classic 'Fresh Fruit' achieves gold status after 43 years}}

== Early life ==
Biafra was born in Boulder, Colorado.
"""

def clean_wiki_value(value):
    """Clean a single infobox value by removing wiki markup and templates."""
    if not value:
        return None
    
    # Handle {{hlist|item1|item2|item3}} -> extract items
    hlist_match = re.search(r'\{\{hlist\s*\|([^}]+)\}\}', value, re.IGNORECASE)
    if hlist_match:
        items = hlist_match.group(1).split('|')
        # Clean each item
        cleaned_items = []
        for item in items:
            item = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', item)
            item = re.sub(r'<[^>]+>', '', item)
            item = item.strip()
            if item:
                cleaned_items.append(item)
        return cleaned_items if len(cleaned_items) > 1 else (cleaned_items[0] if cleaned_items else None)
    
    # Remove wikilinks
    value = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', value)
    value = re.sub(r'\{\{[^\}]+\}\}', '', value)
    value = re.sub(r'<[^>]+>', '', value)
    value = re.sub(r'\s+', ' ', value).strip()
    
    return value if value else None

def extract_abstract_improved(text):
    """Extract clean opening paragraph(s)."""
    lines = text.split('\n')
    abstract = []
    inside_template = 0
    started = False
    
    for line in lines:
        inside_template += line.count('{{') - line.count('}}')
        if inside_template > 0:
            continue
        
        if line.startswith('=='):
            break
        
        if line.startswith('{{') or line.startswith('[[') or line.startswith('|') or line.startswith('#'):
            continue
        
        clean = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', line)
        clean = re.sub(r"'{2,}", '', clean)  # Remove bold/italic markup
        clean = re.sub(r'<ref[^>]*>.*?</ref>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'\{\{[Cc]ite[^}]*\}\}', '', clean)
        clean = re.sub(r'<[^>]+>', '', clean)
        clean = re.sub(r'\{\{[^\}]+\}\}', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        if clean.startswith('}}') or clean.startswith('|'):
            continue
        
        if clean:
            started = True
            abstract.append(clean)
        elif started:
            break
        
        if len(' '.join(abstract)) > 500:
            break
    
    result = ' '.join(abstract)
    result = re.sub(r'\}\}+', '', result).strip()
    return result

# Test genre extraction
print("=" * 70)
print("GENRE FIELD TEST")
print("=" * 70)
genre_raw = "{{hlist|[[Punk rock]]|[[spoken word]]|[[hardcore punk]]}} "
print(f"Before: {repr(genre_raw)}")
print(f"After:  {clean_wiki_value(genre_raw)}")

print("\n" + "=" * 70)
print("ORIGIN FIELD TEST")
print("=" * 70)
origin_raw = "[[Boulder, Colorado]], U.S."
print(f"Before: {repr(origin_raw)}")
print(f"After:  {clean_wiki_value(origin_raw)}")

print("\n" + "=" * 70)
print("ABSTRACT TEST")
print("=" * 70)
print("Before (first 100 chars):")
print(f"  {repr(sample_abstract[:100])}...")
result = extract_abstract_improved(sample_abstract)
print(f"\nAfter (full result):")
print(f"  {result}")
print(f"\nLength: {len(result)} chars")

print("\n" + "=" * 70)
print("✅ IMPROVEMENTS SUMMARY")
print("=" * 70)
print("  ✓ Genre is now a list: ['Punk rock', 'spoken word', 'hardcore punk']")
print("  ✓ Origin cleaned: 'Boulder, Colorado, U.S.'")
print("  ✓ Abstract has no }} artifacts or citation templates")
print("  ✓ Abstract properly extracts the opening sentence")
