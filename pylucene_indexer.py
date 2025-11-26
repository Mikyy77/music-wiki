import os
import sys
import json
import time
from collections import defaultdict

import lucene
from java.nio.file import Paths
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, StringField, TextField, StoredField, IntPoint
from org.apache.lucene.index import IndexWriter, IndexWriterConfig, DirectoryReader, Term
from org.apache.lucene.store import FSDirectory
from org.apache.lucene.search import IndexSearcher, TermQuery, BooleanQuery, BooleanClause, FuzzyQuery, PhraseQuery
from org.apache.lucene.queryparser.classic import QueryParser

# Import the old indexer for comparison
from indexer import Indexer, SearchEngine

class PyLuceneIndexer:
    def __init__(self, index_dir="lucene_index"):
        self.index_dir = index_dir
        # Initialize Lucene VM only once
        if not lucene.getVMEnv():
            lucene.initVM(vmargs=['-Djava.awt.headless=true'])
        
        self.directory = FSDirectory.open(Paths.get(index_dir))
        self.analyzer = StandardAnalyzer()
        self.config = IndexWriterConfig(self.analyzer)
        self.writer = None

    def open_writer(self):
        self.config = IndexWriterConfig(self.analyzer)
        self.config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
        self.writer = IndexWriter(self.directory, self.config)

    def close_writer(self):
        if self.writer:
            self.writer.commit()
            self.writer.close()
            self.writer = None

    def add_document(self, doc_id, data):
        if not self.writer:
            raise Exception("Writer not open. Call open_writer() first.")

        doc = Document()
        
        # 1. UUID
        doc.add(StringField("uuid", doc_id, Field.Store.YES))
        
        # 2. Name
        name = data.get("name") or "Unknown"
        doc.add(TextField("name", name, Field.Store.YES))
        
        # 3. Type (Use 'type' or 'mb_type' or 'wiki_type')
        artist_type = data.get("type") or data.get("mb_type") or data.get("wiki_type") or "Unknown"
        doc.add(StringField("type", artist_type, Field.Store.YES))
        
        # 4. Genres / Categories
        # In the joined file, 'categories' from Wikipedia are similar to genres
        genres = " ".join(data.get("categories", []) or [])
        doc.add(TextField("genres", genres, Field.Store.YES))
        
        # 5. Founded In (Might be missing in joined data, default to 0)
        founded_in = data.get("founded_in")
        try:
            founded_year = int(founded_in) if founded_in and str(founded_in).isdigit() else 0
        except:
            founded_year = 0
        doc.add(IntPoint("founded_in", founded_year))
        doc.add(StoredField("founded_in_stored", str(founded_year)))
        
        # 6. Area (Might be missing, default to Unknown)
        area = data.get("area") or "Unknown"
        doc.add(TextField("area", area, Field.Store.YES))

        # 7. URL - Use Wikipedia URL as requested
        url = data.get("wiki_url") or data.get("url") or ""
        doc.add(StoredField("url", url))
        
        # 8. Content - Aggregated text
        # Include abstract for better search
        abstract = data.get("abstract") or ""
        text_parts = [
            name,
            genres,
            artist_type,
            area,
            abstract
        ]
        # Add releases if available (schema might differ)
        if "releases" in data and isinstance(data["releases"], list):
             for r in data["releases"]:
                 if isinstance(r, dict):
                     text_parts.append(str(r.get("title", "") or ""))
        
        full_text = " ".join([t for t in text_parts if t])
        doc.add(TextField("content", full_text, Field.Store.NO))

        self.writer.addDocument(doc)

    def build_index(self, source_path):
        # source_path can be a file (JSONL) or folder
        print(f"Building Lucene index from {source_path}...")
        start_time = time.time()
        self.open_writer()
        
        count = 0
        
        if os.path.isdir(source_path):
            # Old behavior: iterate folder
            for fname in os.listdir(source_path):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(source_path, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    doc_id = data.get("uuid")
                    if doc_id:
                        self.add_document(doc_id, data)
                        count += 1
                except Exception as e:
                    print(f"Error indexing {fname}: {e}")
        else:
            # New behavior: read JSONL file
            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            data = json.loads(line)
                            doc_id = data.get("uuid")
                            if doc_id:
                                self.add_document(doc_id, data)
                                count += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Error reading {source_path}: {e}")

        self.close_writer()
        end_time = time.time()
        print(f"Indexed {count} documents in {end_time - start_time:.2f} seconds.")

    def search(self, query_str, top_n=10):
        if not DirectoryReader.indexExists(self.directory):
            print("Index not found.")
            return []

        reader = DirectoryReader.open(self.directory)
        searcher = IndexSearcher(reader)
        
        # Default to searching the 'content' field if no field specified
        parser = QueryParser("content", self.analyzer)
        try:
            query = parser.parse(query_str)
        except Exception as e:
            print(f"Query parsing error: {e}")
            return []

        score_docs = searcher.search(query, top_n).scoreDocs
        
        results = []
        stored_fields = searcher.storedFields()
        for score_doc in score_docs:
            doc = stored_fields.document(score_doc.doc)
            results.append({
                "uuid": doc.get("uuid"),
                "name": doc.get("name"),
                "type": doc.get("type"),
                "score": score_doc.score,
                "genres": doc.get("genres"),
                "area": doc.get("area"),
                "founded": doc.get("founded_in_stored"),
                "url": doc.get("url")
            })
            
        reader.close()
        return results

def compare_search(old_indexer, new_indexer, query):
    print(f"\n{'='*20} Comparing Query: '{query}' {'='*20}")
    
    # Old Indexer
    print("\n--- Old Indexer (Custom TF-IDF) ---")
    start = time.time()
    # Using 'smooth' idf method as it's usually better
    old_results = SearchEngine(old_indexer).search(query, idf_method="smooth")
    print(f"Time: {time.time() - start:.4f}s")
    
    if not old_results:
        print("No results.")
    else:
        for i, (doc_id, score) in enumerate(old_results[:5], 1):
            name = old_indexer.doc_names.get(doc_id, "Unknown")
            print(f"{i}. {name} (Score: {score:.3f})")

    # New Indexer (PyLucene)
    print("\n--- New Indexer (PyLucene) ---")
    start = time.time()
    new_results = new_indexer.search(query, top_n=5)
    print(f"Time: {time.time() - start:.4f}s")
    
    if not new_results:
        print("No results.")
    else:
        for i, res in enumerate(new_results, 1):
            print(f"{i}. {res['name']} (Score: {res['score']:.3f}) - {res['type']}")
            print(f"   {res['url']}")
            print(f"   Genres: {res['genres'][:50]}... | Area: {res['area']}")

def main():
    default_source = "data/joined_artists_filtered.jsonl"
    
    # Initialize Old Indexer
    print("Loading old indexer...")
    old_indexer = Indexer()
    # Ensure old index is loaded (assuming it exists or is built)
    # If documents are empty, build from the new source
    if not old_indexer.documents:
         print("Building old index from new source...")
         old_indexer.build_from_folder(default_source)
    
    # Initialize New Indexer
    lucene_indexer = PyLuceneIndexer()
    
    # Check if we need to build the index
    if len(sys.argv) > 1 and sys.argv[1] == "--rebuild":
        # Rebuild BOTH indexes if requested
        print("Rebuilding OLD index...")
        old_indexer.documents = {} # Clear old docs to force rebuild
        old_indexer.index = defaultdict(dict)
        old_indexer.build_from_folder(default_source)
        
        print("Rebuilding NEW PyLucene index...")
        lucene_indexer.build_index(default_source)
    elif not os.path.exists("lucene_index"):
        lucene_indexer.build_index(default_source)
    else:
        print("Using existing Lucene index.")

    print("\nPyLucene Search Engine Ready")
    print("Supported Queries:")
    print(" - Boolean: rock AND metal")
    print(" - Phrase: \"The Beatles\"")
    print(" - Fuzzy: Beatles~")
    print(" - Range: founded_in:[1990 TO 2000]")
    print(" - Field: name:Nirvana")
    
    while True:
        query = input("\nEnter query (or 'exit'): ").strip()
        if not query:
            continue
        if query.lower() in ["exit", "quit"]:
            break
            
        compare_search(old_indexer, lucene_indexer, query)

if __name__ == "__main__":
    main()
