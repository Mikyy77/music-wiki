import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from lxml import etree
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, MapType

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
        
        self.exclusion_patterns = [
            'telecommunication', 'signal processing', 'wireless', 'broadband', 'bandwidth',
            'radio technology', 'internet', 'networking', 'legal', 'marine', 'railway',
            'physics', 'engineering', 'computer', 'software', 'television technology',
            'broadcasting', 'spectrum management', 'frequency', 'radio spectrum'
        ]

    def extract_categories(self, text):
        return [m.group(1).strip() for m in re.finditer(r'\[\[Category:([^\]|]+)', text, re.IGNORECASE)]

    def clean_wiki_value(self, value):
        """Clean a single infobox value by removing wiki markup and templates."""
        if not value:
            return None
        
        hlist_match = re.search(r'\{\{hlist\s*\|([^}]+)\}\}', value, re.IGNORECASE)
        if hlist_match:
            items = hlist_match.group(1).split('|')
            cleaned_items = []
            for item in items:
                item = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', item)
                item = re.sub(r'<[^>]+>', '', item)
                item = item.strip()
                if item:
                    cleaned_items.append(item)
            return cleaned_items if len(cleaned_items) > 1 else (cleaned_items[0] if cleaned_items else None)
        
        flatlist_match = re.search(r'\{\{flatlist\s*\|([^}]+)\}\}', value, re.IGNORECASE)
        if flatlist_match:
            value = flatlist_match.group(1)
        
        value = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', value)
        value = re.sub(r'\{\{[^\}]+\}\}', '', value)
        value = re.sub(r'<[^>]+>', '', value)
        value = re.sub(r'<ref[^>]*>.*?</ref>', '', value, flags=re.DOTALL)
        value = re.sub(r'\s+', ' ', value).strip()
        
        return value if value else None

    def extract_infobox_metadata(self, text):
        """Extract and clean infobox fields with better template handling."""
        metadata = {}
        
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
            clean = re.sub(r"'{2,}", '', clean)
            clean = re.sub(r'<ref[^>]*>.*?</ref>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'\{\{[Cc]ite[^}]*\}\}', '', clean)
            clean = re.sub(r'\{\{[Ee]fn[^}]*\}\}', '', clean)
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

    def is_music_related(self, title, text, categories):
        title_l = title.lower()
        cat_text = ' '.join(categories).lower()
        combined = title_l + ' ' + cat_text
        
        for exclusion in self.exclusion_patterns:
            if exclusion in cat_text:
                return None
        
        has_music_signal = any(sig in combined for sig in self.music_signals)
        has_band_word = bool(re.search(r'\bband\b', combined, re.IGNORECASE))
        
        if not has_music_signal and not has_band_word:
            return None
        
        if has_band_word and not has_music_signal:
            music_category_found = False
            for t, cats in self.category_patterns.items():
                if any(c in cat_text for c in cats):
                    music_category_found = True
                    break
            if not music_category_found:
                return None
        
        if any(p.search(text) for p in self.infobox_patterns):
            for t, cats in self.category_patterns.items():
                if any(c in cat_text for c in cats):
                    return t
            for t, kws in self.title_keywords.items():
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
                if t == 'band':
                    if re.search(r'\bband\b', title_l, re.IGNORECASE):
                        return t
                else:
                    if any(k in title_l for k in kws):
                        return t
        return None

    def process_xml_string(self, xml_string):
        """Process a raw XML string (content between </page> tags)."""
        try:
            # Reconstruct valid XML for the page
            # Spark's lineSep='</page>' gives us the content BEFORE the separator.
            # We need to find the start of <page> and append </page>
            start_idx = xml_string.find("<page>")
            if start_idx == -1:
                return None
            
            clean_xml = xml_string[start_idx:] + "</page>"
            
            # Parse XML
            # Use recover=True to handle potential malformed bits
            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(clean_xml, parser=parser)
            
            title = root.findtext(".//{*}title")
            text = root.findtext(".//{*}revision/{*}text")
            
            if not title or not text:
                return None
                
            categories = self.extract_categories(text)
            entity_type = self.is_music_related(title, text, categories)
            
            if not entity_type:
                return None
                
            abstract = self.extract_abstract(text)
            metadata = self.extract_infobox_metadata(text)
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
            return entity
            
        except Exception as e:
            # In a distributed environment, we might want to log this but avoid crashing
            return None

def process_partition(iterator):
    """Worker function to process a partition of XML strings."""
    extractor = WikiMusicExtractor()
    for row in iterator:
        # row.value contains the text line (XML chunk)
        if row.value:
            result = extractor.process_xml_string(row.value)
            if result:
                yield result

def main():
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description="Extract music entities from Wikipedia dump using PySpark")
    parser.add_argument("--dump", required=True, type=str, help="Path to enwiki-latest-pages-articles.xml.bz2")
    parser.add_argument("--limit", type=int, help="Limit number of records to process (optional, for testing)")
    parser.add_argument("--out-jsonl", type=str, default="data/wiki_music.jsonl", help="Output directory for JSONL files")
    args = parser.parse_args()

    # Initialize Spark Session
    spark = SparkSession.builder \
        .appName("WikiMusicExtractor") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .getOrCreate()
        
    spark.sparkContext.setLogLevel("WARN")

    print(f"Reading dump: {args.dump}")
    
    # Read XML dump using 'lineSep' to split by </page>
    # This is a robust way to handle large XML files in Spark without external XML libraries
    raw_df = spark.read.option("lineSep", "</page>").text(args.dump)
    
    if args.limit:
        print(f"Limiting to {args.limit} records")
        raw_df = raw_df.limit(args.limit)

    # Process using RDD mapPartitions
    # This allows us to instantiate the extractor once per partition
    entities_rdd = raw_df.rdd.mapPartitions(process_partition)
    
    # Convert back to DataFrame
    # We let Spark infer the schema from the first few rows, or we could define it
    # Inferring is safer as fields might vary
    if entities_rdd.isEmpty():
        print("No entities found!")
    else:
        entities_df = spark.createDataFrame(entities_rdd)
        
        print(f"Writing results to {args.out_jsonl}")
        entities_df.write.mode("overwrite").json(args.out_jsonl)
        
        count = entities_df.count()
        print(f"Extracted {count:,} music entities")

    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.1f}s ({elapsed_time/60:.1f} minutes)")
    
    spark.stop()

if __name__ == "__main__":
    main()
