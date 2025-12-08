
import sys
import os

# Add parent directory to path to import pylucene_indexer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylucene_indexer import PyLuceneIndexer

def main():
    if not os.path.exists("lucene_index"):
        print("Index not found. Please run pylucene_indexer.py to build it first.")
        sys.exit(1)

    indexer = PyLuceneIndexer()
    
    queries = ["beetles", "beetles~", "The Beatles", "beatles"]
    
    print("Reproduction Test for 'beetles' vs 'The Beatles'")
    print("================================================")
    
    for q in queries:
        print(f"\nQuery: '{q}'")
        results = indexer.search(q, top_n=5)
        if not results:
            print("  No results.")
        else:
            for i, res in enumerate(results, 1):
                print(f"  {i}. {res['name']} (Score: {res['score']:.3f})")

if __name__ == "__main__":
    main()
