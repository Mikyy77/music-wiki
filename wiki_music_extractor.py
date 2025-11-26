import argparse
import bz2
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from lxml import etree

class WikiMusicExtractor:
    def __init__(self):
        self.infobox_patterns = [
            re.compile(r'{{\s*Infobox\s+musical\s+artist', re.IGNORECASE),
            re.compile(r'{{\s*Infobox\s+band', re.IGNORECASE),
            re.compile(r'{{\s*Infobox\s+album', re.IGNORECASE),
            re.compile(r'{{\s*Infobox\s+song', re.IGNORECASE),
            re.compile(r'{{\s*Infobox\s+musical\s+work', re.IGNORECASE),
        ]

        self.category_patterns = {
            'artist': [
                'singers', 'vocalists', 'male singers', 'female singers',
                'musicians', 'instrumentalists', 'multi-instrumentalists',
                'songwriters', 'composers', 'lyricists', 'singer-songwriters',
                'record producers', 'music producers', 'hip hop producers',
                'djs', 'disc jockeys', 'turntablists',
                'rappers', 'hip hop musicians', 'mcs'
            ],
            'band': [
                'bands', 'musical groups', 'rock bands', 'metal bands', 
                'pop bands', 'jazz bands', 'boy bands', 'girl groups',
                'musical duos', 'duos'
            ]
        }

        self.title_keywords = {
            'artist': ['singer', 'vocalist', 'musician', 'songwriter', 'composer', 'producer', 'dj', 'rapper', 'mc'],
            'band': ['band', 'group', 'ensemble', 'duo']
        }

        self.music_signals = ['music', 'song', 'album', 'artist', 'composer', 'recording', 'instrument']
        
        # Categories that indicate non-music content (for filtering false positives)
        self.exclusion_patterns = [
            'telecommunication', 'signal processing', 'wireless', 'broadband', 'bandwidth',
            'radio technology', 'internet', 'networking', 'legal', 'marine', 'railway',
            'physics', 'engineering', 'computer', 'software', 'television technology',
            'broadcasting', 'spectrum management', 'frequency', 'radio spectrum'
        ]

        self.stats = {
            'total_pages': 0,
            'music_pages': 0,
            'entities_by_type': defaultdict(int),
            'filtered_false_positives': 0
        }

        self.entities = {}

    def extract_categories(self, text):
        return [m.group(1).strip() for m in re.finditer(r'\[\[Category:([^\]|]+)', text, re.IGNORECASE)]

    def clean_wiki_value(self, value):
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
        
        # Handle {{flatlist}} and other list templates
        flatlist_match = re.search(r'\{\{flatlist\s*\|([^}]+)\}\}', value, re.IGNORECASE)
        if flatlist_match:
            value = flatlist_match.group(1)
        
        # Remove wikilinks: [[Link|Display]] or [[Link]] -> Display or Link
        value = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', value)
        
        # Remove remaining templates like {{sfn|...}}
        value = re.sub(r'\{\{[^\}]+\}\}', '', value)
        
        # Remove HTML tags
        value = re.sub(r'<[^>]+>', '', value)
        
        # Remove refs like <ref>...</ref>
        value = re.sub(r'<ref[^>]*>.*?</ref>', '', value, flags=re.DOTALL)
        
        # Clean up whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        return value if value else None

    def extract_infobox_metadata(self, text):
        """Extract and clean infobox fields with better template handling."""
        metadata = {}
        
        # Find infobox with proper nested brace handling
        match = re.search(r'\{\{Infobox[^{]+?\n(.*?)\n\}\}', text, re.DOTALL | re.IGNORECASE)
        if not match:
            return metadata
        
        infobox = match.group(0)
        
        fields = {
            'genre': r'\|\s*genre\s*=\s*([^\n|]+)',
            'origin': r'\|\s*(?:origin|birth_place)\s*=\s*([^\n|]+)',
            'years_active': r'\|\s*years_active\s*=\s*([^\n|]+)',
            'label': r'\|\s*label\s*=\s*([^\n|]+)',
            'members': r'\|\s*(?:members|current_member_of)\s*=\s*([^\n|]+)',
            'birth_name': r'\|\s*birth_name\s*=\s*([^\n|]+)',
        }
        
        for name, pattern in fields.items():
            fmatch = re.search(pattern, infobox, re.IGNORECASE)
            if fmatch:
                raw_value = fmatch.group(1).strip()
                cleaned = self.clean_wiki_value(raw_value)
                if cleaned:
                    metadata[name] = cleaned
        
        return metadata

    def extract_abstract(self, text):
        """Extract clean opening paragraph(s), skipping infoboxes and templates."""
        lines = text.split('\n')
        abstract = []
        inside_template = 0
        started = False  # Track if we've started collecting text
        
        for line in lines:
            # Track template nesting
            inside_template += line.count('{{') - line.count('}}')
            if inside_template > 0:
                continue
            
            # Stop at first section header
            if line.startswith('=='):
                break
            
            # Skip template/infobox lines and metadata lines
            if line.startswith('{{') or line.startswith('[[') or line.startswith('|') or line.startswith('#'):
                continue
            
            # Clean wikilinks: [[Link|Display]] -> Display, [[Link]] -> Link
            clean = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', line)
            
            # Remove bold/italic markup
            clean = re.sub(r"'{2,}", '', clean)
            
            # Remove citations/refs
            clean = re.sub(r'<ref[^>]*>.*?</ref>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'\{\{[Cc]ite[^}]*\}\}', '', clean)
            clean = re.sub(r'\{\{[Ee]fn[^}]*\}\}', '', clean)
            
            # Remove HTML tags
            clean = re.sub(r'<[^>]+>', '', clean)
            
            # Remove remaining simple templates
            clean = re.sub(r'\{\{[^\}]+\}\}', '', clean)
            
            # Clean whitespace
            clean = re.sub(r'\s+', ' ', clean).strip()
            
            # Skip lines that start with leftover template markers
            if clean.startswith('}}') or clean.startswith('|'):
                continue
            
            if clean:
                started = True
                abstract.append(clean)
            elif started:
                # Stop on first blank line after we've started collecting
                break
            
            # Limit length
            if len(' '.join(abstract)) > 500:
                break
        
        result = ' '.join(abstract)
        # Final cleanup of any remaining artifacts
        result = re.sub(r'\}\}+', '', result).strip()
        return result

    def is_music_related(self, title, text, categories):
        title_l = title.lower()
        cat_text = ' '.join(categories).lower()
        combined = title_l + ' ' + cat_text
        
        # First, check for exclusion patterns (false positives)
        for exclusion in self.exclusion_patterns:
            if exclusion in cat_text:
                self.stats['filtered_false_positives'] += 1
                return None
        
        # Check if basic music signals are present
        has_music_signal = any(sig in combined for sig in self.music_signals)
        
        # Check for the word "band" using word boundaries to avoid "bandwidth", "husband", etc.
        has_band_word = bool(re.search(r'\bband\b', combined, re.IGNORECASE))
        
        # If no music signals and no proper "band" word, reject
        if not has_music_signal and not has_band_word:
            return None
        
        # If ONLY "band" word is present (no other music signals), require strong category evidence
        if has_band_word and not has_music_signal:
            # Must have at least one music-specific category
            music_category_found = False
            for t, cats in self.category_patterns.items():
                if any(c in cat_text for c in cats):
                    music_category_found = True
                    break
            if not music_category_found:
                self.stats['filtered_false_positives'] += 1
                return None
        
        # Now determine entity type
        if any(p.search(text) for p in self.infobox_patterns):
            for t, cats in self.category_patterns.items():
                if any(c in cat_text for c in cats):
                    return t
            for t, kws in self.title_keywords.items():
                # Use word boundary for "band" keyword
                if t == 'band':
                    if re.search(r'\bband\b', title_l, re.IGNORECASE):
                        return t
                else:
                    if any(k in title_l for k in kws):
                        return t
            return 'artist'
        else:
            for t, cats in self.category_patterns.items():
                if any(c in cat_text for c in cats):
                    return t
            for t, kws in self.title_keywords.items():
                # Use word boundary for "band" keyword
                if t == 'band':
                    if re.search(r'\bband\b', title_l, re.IGNORECASE):
                        return t
                else:
                    if any(k in title_l for k in kws):
                        return t
        return None

    def normalize_surface(self, text):
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        return text.strip()

    def process_page(self, page_elem):
        title = page_elem.findtext(".//{*}title")
        text = page_elem.findtext(".//{*}revision/{*}text")
        if not title or not text:
            return None
        categories = self.extract_categories(text)
        entity_type = self.is_music_related(title, text, categories)
        if not entity_type:
            return None
        abstract = self.extract_abstract(text)
        metadata = self.extract_infobox_metadata(text)
        # Build Wikipedia URL from title (spaces -> underscores)
        wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        entity = {
            "id": title.replace(' ', '_'),
            "title": title,
            "type": entity_type,
            "url": wiki_url,
            "categories": categories,
            "abstract": abstract,
            **metadata
        }
        self.stats['music_pages'] += 1
        self.stats['entities_by_type'][entity_type] += 1
        return entity

    def stream_dump(self, dump_file, limit=None, out_jsonl: Path = None, out_entity_lookup: Path = None):
        """
        Stream pages from a compressed Wikipedia dump and optionally write
        entities to JSONL and/or an entity lookup TSV as they are found to avoid
        keeping everything in memory.
        """
        start_time = time.time()
        print(f"Reading dump: {dump_file}")

        # Determine whether to store entities in memory
        store_entities = not (out_jsonl or out_entity_lookup)

        # Flags to indicate streaming wrote outputs (so save_* can skip)
        self._written_jsonl = False
        self._written_entity_lookup = False

        jsonl_f = None
        lookup_f = None
        try:
            if out_jsonl:
                out_jsonl.parent.mkdir(parents=True, exist_ok=True)
                jsonl_f = open(out_jsonl, 'w', encoding='utf-8')
                self._written_jsonl = True
            if out_entity_lookup:
                out_entity_lookup.parent.mkdir(parents=True, exist_ok=True)
                lookup_f = open(out_entity_lookup, 'w', encoding='utf-8')
                lookup_f.write("surface\twiki_title\ttype\tnorm\n")
                self._written_entity_lookup = True

            with bz2.open(dump_file, 'rb') as f:
                context = etree.iterparse(f, events=('end',), tag='{*}page')
                for _, elem in context:
                    self.stats['total_pages'] += 1
                    try:
                        entity = self.process_page(elem)
                        if entity:
                            # Write immediately to outputs if requested
                            if jsonl_f:
                                jsonl_f.write(json.dumps(entity, ensure_ascii=False) + '\n')
                            if lookup_f:
                                norm = self.normalize_surface(entity['title'])
                                lookup_f.write(f"{entity['title']}\t{entity['title']}\t{entity['type']}\t{norm}\n")
                            # Only keep in memory when not streaming to disk
                            if store_entities:
                                self.entities[entity['title']] = entity
                    except Exception as e:
                        # Log the error and continue processing other pages
                        page_title = elem.findtext(".//{*}title")
                        print(f"Error processing page {page_title or 'UNKNOWN'}: {type(e).__name__}: {e}")
                        if not hasattr(self.stats, 'errors'):
                            self.stats['errors'] = 0
                        self.stats['errors'] += 1
                    finally:
                        # free memory from the parsed XML
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                    
                    # Progress logging every 10k pages
                    if self.stats['total_pages'] % 10000 == 0:
                        elapsed = time.time() - start_time
                        rate = self.stats['total_pages'] / elapsed if elapsed > 0 else 0
                        print(f"Processed {self.stats['total_pages']:,} pages in {elapsed:.1f}s ({rate:.0f} pages/sec) | Found {self.stats['music_pages']:,} music entities")
                    
                    if limit and self.stats['total_pages'] >= limit:
                        print(f"Reached page limit of {limit}")
                        break
        finally:
            if jsonl_f:
                jsonl_f.close()
            if lookup_f:
                lookup_f.close()

        elapsed_time = time.time() - start_time
        print(f"✅ Finished streaming Wikipedia dump in {elapsed_time:.1f}s ({elapsed_time/60:.1f} minutes)")

    def save_jsonl(self, output_file):
        # If streaming already wrote the JSONL, skip to avoid duplication
        if getattr(self, '_written_jsonl', False):
            print(f"JSONL was already written during streaming; skipping save → {output_file}")
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for e in self.entities.values():
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
        print(f"Saved {len(self.entities)} entities → {output_file}")

    def save_entity_lookup(self, output_file):
        # If streaming already wrote the entity lookup, skip to avoid duplication
        if getattr(self, '_written_entity_lookup', False):
            print(f"Entity lookup was already written during streaming; skipping save → {output_file}")
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("surface\twiki_title\ttype\tnorm\n")
            for e in self.entities.values():
                norm = self.normalize_surface(e['title'])
                f.write(f"{e['title']}\t{e['title']}\t{e['type']}\t{norm}\n")
        print(f"Saved entity lookup with {len(self.entities)} entries → {output_file}")

    def print_stats(self):
        print("\n==================== EXTRACTION STATS ====================")
        print(f"Total pages processed: {self.stats['total_pages']:,}")
        print(f"Music entities found:  {self.stats['music_pages']:,}")
        print(f"False positives filtered: {self.stats['filtered_false_positives']:,}")
        if hasattr(self.stats, 'errors') and self.stats['errors'] > 0:
            print(f"Pages with errors:     {self.stats['errors']:,}")
        print("\nEntities by type:")
        for t, c in self.stats['entities_by_type'].items():
            print(f"  {t:12s} {c:,}")
        print("==========================================================\n")


def main():
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description="Extract music entities from Wikipedia dump")
    parser.add_argument("--dump", required=True, type=Path, help="Path to enwiki-latest-pages-articles.xml.bz2")
    parser.add_argument("--limit", type=int, help="Limit number of pages (optional, for testing)")
    parser.add_argument("--out-jsonl", type=Path, default=Path("data/wiki_music.jsonl"))
    parser.add_argument("--out-entity-lookup", type=Path, default=Path("entities/wiki_music_entity_lookup.tsv"))
    args = parser.parse_args()

    if not args.dump.exists():
        print(f"Dump file not found: {args.dump}")
        sys.exit(1)

    extractor = WikiMusicExtractor()
    extractor.stream_dump(args.dump, limit=args.limit, out_jsonl=args.out_jsonl, out_entity_lookup=args.out_entity_lookup)
    extractor.save_jsonl(args.out_jsonl)
    extractor.save_entity_lookup(args.out_entity_lookup)
    extractor.print_stats()
    
    total_time = time.time() - start_time
    print(f"\nTotal execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)")


if __name__ == "__main__":
    main()
