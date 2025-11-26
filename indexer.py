import os
import json
import re
import math
from collections import defaultdict, Counter
from search import SearchEngine


class Indexer:
    def __init__(self, index_file="index_data.json"):
        self.index = defaultdict(dict)
        self.documents = {}
        self.doc_lengths = {}
        self.doc_names = {}
        self.doc_meta = {}  # stores metadata for each artist
        self.index_file = index_file

        if os.path.exists(index_file):
            self.load_index()
            print(f"Loaded existing index from {index_file} ({len(self.documents)} docs)")
        else:
            print("No existing index found, will build a new one.")

    # tokenizer
    def tokenize(self, text):
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return [t for t in text.split() if len(t) > 2]

    # adds new document to the index
    def add_document(self, doc_id, name, text):
        tokens = self.tokenize(text)
        if not tokens:
            return

        self.documents[doc_id] = text
        self.doc_lengths[doc_id] = len(tokens)
        self.doc_names[doc_id] = name.strip() if name else "Unknown"

        tf_counts = Counter(tokens)
        for term, tf in tf_counts.items():
            self.index[term][doc_id] = tf

    # build index from source (folder or JSONL file)
    def build_from_folder(self, source_path):
        new_docs = 0
        all_docs_text = []
        all_metadata = []

        def process_data(data):
            doc_id = data.get("uuid")
            if not doc_id:
                return False

            name = data.get("name") or "Unknown"

            # always refresh metadata
            # Use wiki_url if available, else fallback
            url = data.get("wiki_url") or data.get("url") or f"https://musicbrainz.org/artist/{doc_id}"
            
            # Type: try wiki_type, mb_type, type
            artist_type = data.get("wiki_type") or data.get("mb_type") or data.get("type") or "Unknown"
            
            # Genres: try categories (wiki) or genres (mb)
            genres = data.get("categories") or data.get("genres", []) or ["Unknown"]
            
            founded_in = data.get("founded_in") or "Unknown"
            area = data.get("area") or "Unknown"
            rating = data.get("rating_value") or 0

            # store metadata
            self.doc_meta[doc_id] = {
                "url": url,
                "type": artist_type,
                "genres": genres,
                "founded_in": founded_in,
                "area": area,
                "rating": rating,
            }

            # check if this is a new document
            is_new = doc_id not in self.documents

            # build text and index (always, even for existing docs)
            # Include abstract if available
            abstract = data.get("abstract") or ""
            
            text_parts = [
                name,
                " ".join(genres),
                " ".join(data.get("other_tags", []) or []),
                artist_type,
                founded_in,
                area,
                abstract
            ]
            
            # Handle releases (might be different structure in joined data)
            if "releases" in data and isinstance(data["releases"], list):
                for r in data["releases"]:
                    if isinstance(r, dict):
                        text_parts.append(str(r.get("title", "") or ""))
                        text_parts.append(str(r.get("artist", "") or ""))
            
            # Handle recordings
            if "recordings" in data and isinstance(data["recordings"], list):
                for rec in data["recordings"]:
                    if isinstance(rec, dict):
                        text_parts.append(str(rec.get("title", "") or ""))
            
            # Handle relationships
            rels = data.get("relationships", {})
            if rels:
                rel_names = []
                for key in ["members", "original_members", "artistic_directors"]:
                    for person in rels.get(key, []):
                        if isinstance(person, dict):
                            rel_names.append(person.get("name", ""))
                text_parts.append(" ".join(rel_names))

            full_text = " ".join([t for t in text_parts if t])
            self.add_document(doc_id, name, full_text)
            return is_new

        if os.path.isdir(source_path):
            print(f"Building index from folder: {source_path}")
            for fname in os.listdir(source_path):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(source_path, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if process_data(data):
                        new_docs += 1
                except Exception as e:
                    print(f"Error processing {fname}: {e}")
        else:
            print(f"Building index from file: {source_path}")
            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            data = json.loads(line)
                            if process_data(data):
                                new_docs += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Error reading {source_path}: {e}")

        if new_docs > 0:
            print(f"Indexed {new_docs} new artists (total: {len(self.documents)})")
        else:
            print(f"Refreshed metadata for {len(self.documents)} existing artists")

        # Always save to persist metadata updates
        self.save_index()
        self.save_extras(all_docs_text, all_metadata)
        self.compute_idf()

    # save index to file
    def save_index(self):
        data = {
            "index": {k: dict(v) for k, v in self.index.items()},
            "documents": self.documents,
            "doc_lengths": self.doc_lengths,
            "doc_names": self.doc_names,
            "doc_meta": self.doc_meta,
        }
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Index updated and saved to {self.index_file}")

    # load index from file
    def load_index(self):
        with open(self.index_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.index = defaultdict(dict, {k: v for k, v in data["index"].items()})
        self.documents = data["documents"]
        self.doc_lengths = data["doc_lengths"]
        self.doc_names = data["doc_names"]
        self.doc_meta = data.get("doc_meta", {})

    # save extra parts for analysis
    def save_extras(self, docs, metadata):
        os.makedirs("index_parts", exist_ok=True)
        sample = dict(list(self.index.items())[:500])
        with open("index_parts/inverted_index_sample.json", "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2)
        with open("index_parts/docs.json", "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2)
        with open("index_parts/metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        print("Saved index_parts/: inverted_index_sample.json, docs.json, metadata.json")

    def compute_idf(self):
        """Compute and save classic + smooth IDF values."""
        N = len(self.documents)
        idf_basic = {}
        idf_smooth = {}

        for term, postings in self.index.items():
            df = len(postings)
            idf_basic[term] = math.log10(N / df) if df else 0
            idf_smooth[term] = math.log10(1 + N / (1 + df))

        os.makedirs("index_parts", exist_ok=True)
        with open("index_parts/idf_basic.json", "w", encoding="utf-8") as f:
            json.dump(idf_basic, f, indent=2)
        with open("index_parts/idf_smooth.json", "w", encoding="utf-8") as f:
            json.dump(idf_smooth, f, indent=2)

        print(f"Saved IDF files: {len(idf_basic)} terms (basic + smooth)")


def main():
    indexer = Indexer()
    folder = "parsed_artists"

    if not indexer.documents:
        print("Building new index from parsed_artists folder...")
        indexer.build_from_folder(folder)
    else:
        print(f"Loaded existing index with {len(indexer.documents)} artists.")

    engine = SearchEngine(indexer)
    print("\nMusicBrainz Artist Search Engine — Ready")
    print("Type your query (or 'update' to refresh index, 'exit' to quit)\n")

    while True:
        query = input("Query: ").strip()
        if not query:
            continue
        if query.lower() in ["exit", "quit"]:
            print("Exiting search engine.")
            break
        elif query.lower() == "update":
            indexer.build_from_folder(folder)
            continue

        results1 = engine.search(query, idf_method="classic")
        results2 = engine.search(query, idf_method="smooth")

        print(f"\nSearch query: '{query}'")

        def print_results(results, title):
            print(f"\n=== {title} ===")
            if not results:
                print("No results found.\n")
                return

            for rank, (doc_id, score) in enumerate(results[:10], start=1):
                artist_name = indexer.doc_names.get(doc_id, "Unknown Artist")
                meta = indexer.doc_meta.get(doc_id, {})

                genres = ", ".join(meta.get("genres", [])[:3]) or "Unknown"
                rating = f" • Rating: {meta.get('rating')}/5" if meta.get("rating") else ""
                founded_in = meta.get("founded_in")
                founded_text = f" • Founded: {founded_in}" if founded_in and founded_in != "Unknown" else ""

                print(f"{rank:>2}. {artist_name} ({meta.get('type', 'Unknown')}) — Score: {round(score, 3)}{rating}")
                print(f"    {genres} • {meta.get('area', 'Unknown')}{founded_text}")
                print(f"    {meta.get('url', 'Unknown')}")
                print()

        print_results(results1, "Classic TF-IDF Ranking")
        print_results(results2, "Smooth TF-IDF Ranking")
        print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
