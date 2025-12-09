#!/usr/bin/env python3
"""
Test precision and recall metrics for both indexers.
Compares old custom TF-IDF indexer vs new PyLucene indexer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indexer import Indexer
from search import SearchEngine
from pylucene_indexer import PyLuceneIndexer
import lucene


# Ground truth: manually verified relevant results for test queries
# Only checking if first result is the exact match for these direct band name queries
GROUND_TRUTH = {
    # Original 15 queries - exact matches
    "beatles": {
        "relevant": ["The Beatles"],
        "description": "Direct match - should find The Beatles first"
    },
    "queen": {
        "relevant": ["Queen"],
        "description": "Direct match - should find Queen first"
    },
    "miles davis": {
        "relevant": ["Miles Davis"],
        "description": "Direct match - should find Miles Davis first"
    },
    "rolling stones": {
        "relevant": ["The Rolling Stones"],
        "description": "Direct match - should find The Rolling Stones first"
    },
    "led zeppelin": {
        "relevant": ["Led Zeppelin"],
        "description": "Direct match - should find Led Zeppelin first"
    },
    "pink floyd": {
        "relevant": ["Pink Floyd"],
        "description": "Direct match - should find Pink Floyd first"
    },
    "metallica": {
        "relevant": ["Metallica"],
        "description": "Direct match - should find Metallica first"
    },
    "jimi hendrix": {
        "relevant": ["Jimi Hendrix"],
        "description": "Direct match - should find Jimi Hendrix first"
    },
    "u2": {
        "relevant": ["U2"],
        "description": "Direct match - should find U2 first"
    },
    "the who": {
        "relevant": ["The Who"],
        "description": "Direct match - should find The Who first"
    },
    "black sabbath": {
        "relevant": ["Black Sabbath"],
        "description": "Direct match - should find Black Sabbath first"
    },
    "the doors": {
        "relevant": ["The Doors"],
        "description": "Direct match - should find The Doors first"
    },
    "john lennon": {
        "relevant": ["John Lennon"],
        "description": "Direct match - should find John Lennon first"
    },
    "david bowie": {
        "relevant": ["David Bowie"],
        "description": "Direct match - should find David Bowie first"
    },
    "radiohead": {
        "relevant": ["Radiohead"],
        "description": "Direct match - should find Radiohead first"
    },
    
    # Additional rock/metal bands
    "iron maiden": {
        "relevant": ["Iron Maiden"],
        "description": "Direct match - famous metal band"
    },
    "megadeth": {
        "relevant": ["Megadeth"],
        "description": "Direct match - thrash metal band"
    },
    "deep purple": {
        "relevant": ["Deep Purple"],
        "description": "Direct match - classic rock band"
    },
    "judas priest": {
        "relevant": ["Judas Priest"],
        "description": "Direct match - heavy metal band"
    },
    "foo fighters": {
        "relevant": ["Foo Fighters"],
        "description": "Direct match - modern rock band"
    },
    
    # Alternative/indie
    "red hot chili peppers": {
        "relevant": ["Red Hot Chili Peppers"],
        "description": "Direct match - alternative rock band"
    },
    "the cure": {
        "relevant": ["The Cure"],
        "description": "Direct match - post-punk band"
    },
    "r.e.m.": {
        "relevant": ["R.E.M."],
        "description": "Direct match - alternative rock band"
    },
    "sonic youth": {
        "relevant": ["Sonic Youth"],
        "description": "Direct match - noise rock band"
    },
    
    # Jazz artists
    "bill evans": {
        "relevant": ["Bill Evans"],
        "description": "Direct match - jazz pianist"
    },
    "dave brubeck": {
        "relevant": ["Dave Brubeck"],
        "description": "Direct match - jazz pianist"
    },
    
    # Reggae
    "bob marley": {
        "relevant": ["Bob Marley"],
        "description": "Direct match - reggae legend"
    },
    
    # Electronic/experimental
    "daft punk": {
        "relevant": ["Daft Punk"],
        "description": "Direct match - electronic duo"
    },
    
    # Partial name queries
    "floyd": {
        "relevant": ["Pink Floyd"],
        "description": "Partial name - should find Pink Floyd"
    },
    "zeppelin": {
        "relevant": ["Led Zeppelin"],
        "description": "Partial name - should find Led Zeppelin"
    },
    
    # Without "The" prefix
    "cure": {
        "relevant": ["The Cure"],
        "description": "Name without 'The' - should find The Cure"
    },
    "doors": {
        "relevant": ["The Doors"],
        "description": "Name without 'The' - should find The Doors"
    },
    
    # Common misspellings
    "metalica": {
        "relevant": ["Metallica"],
        "description": "Misspelling - should find Metallica with fuzzy match"
    },
    "beetles": {
        "relevant": ["The Beatles"],
        "description": "Misspelling - should find The Beatles with fuzzy match"
    },
    
    # Multi-word descriptive queries
    "british rock band 1960s": {
        "relevant": ["The Beatles", "The Rolling Stones", "The Who"],
        "description": "Descriptive query - should find classic British rock bands"
    },
    "jazz trumpet": {
        "relevant": ["Miles Davis"],
        "description": "Genre + instrument query"
    },
    "grunge seattle": {
        "relevant": ["Pearl Jam", "Soundgarden", "Alice in Chains"],
        "description": "Genre + location query"
    },
    
    # Genre-based queries
    "thrash metal": {
        "relevant": ["Metallica", "Megadeth"],
        "description": "Genre query - should find thrash metal bands"
    },
    "progressive rock": {
        "relevant": ["Pink Floyd"],
        "description": "Genre query - should find prog rock bands"
    },
    
    # Additional exact matches for diversity
    "beastie boys": {
        "relevant": ["Beastie Boys"],
        "description": "Direct match - hip hop group"
    },
    "death cab for cutie": {
        "relevant": ["Death Cab for Cutie"],
        "description": "Direct match - indie rock band"
    },
    "elliott smith": {
        "relevant": ["Elliott Smith"],
        "description": "Direct match - singer-songwriter"
    },
    "amorphis": {
        "relevant": ["Amorphis"],
        "description": "Direct match - Finnish metal band"
    },
    "at the gates": {
        "relevant": ["At the Gates"],
        "description": "Direct match - melodic death metal band"
    }
}


def calculate_metrics(retrieved_names, relevant_names, k=10):
    """
    Calculate precision and recall for exact match at top-1.
    For direct artist/band name queries, we only check if the first result is correct.
    
    Precision@1 = 1 if first result is in relevant set, else 0
    Recall@1 = 1 if first result is in relevant set, else 0
    """
    # Check if first result matches
    if retrieved_names and relevant_names:
        first_result = retrieved_names[0]
        is_correct = first_result in relevant_names
        
        precision = 1.0 if is_correct else 0.0
        recall = 1.0 if is_correct else 0.0
        f1 = 1.0 if is_correct else 0.0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "relevant_retrieved": 1 if is_correct else 0,
            "total_retrieved": 1,
            "total_relevant": len(relevant_names),
            "first_result": first_result,
            "correct": is_correct
        }
    
    return {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "relevant_retrieved": 0,
        "total_retrieved": 0,
        "total_relevant": len(relevant_names),
        "first_result": None,
        "correct": False
    }


def test_indexer(indexer_name, search_func, queries_with_truth, k=10):
    """Test an indexer and return aggregated metrics."""
    
    all_metrics = []
    
    print(f"\n{'='*80}")
    print(f"Testing: {indexer_name}")
    print('='*80)
    
    for query, truth in queries_with_truth.items():
        relevant_names = truth["relevant"]
        
        # Get search results
        results = search_func(query, k)
        
        # Calculate metrics
        metrics = calculate_metrics(results, relevant_names, k)
        all_metrics.append(metrics)
        
        status = "✓" if metrics['correct'] else "✗"
        print(f"\nQuery: '{query}' {status}")
        print(f"  Expected: {relevant_names[0]}")
        print(f"  Got:      {metrics['first_result']}")
        print(f"  Correct:  {'YES' if metrics['correct'] else 'NO'}")
        
        # Show top 3 results for context
        print(f"  Top 3:    {', '.join(results[:3])}")
    
    # Calculate accuracy (percentage of correct first results)
    correct_count = sum(1 for m in all_metrics if m['correct'])
    accuracy = correct_count / len(all_metrics)
    
    print(f"\n{'-'*80}")
    print(f"RESULTS for {indexer_name}:")
    print(f"  Accuracy (Top-1): {accuracy:.1%} ({correct_count}/{len(all_metrics)} correct)")
    print(f"  Avg Precision@1:  {accuracy:.3f}")
    print(f"  Avg Recall@1:     {accuracy:.3f}")
    
    return {
        "name": indexer_name,
        "accuracy": accuracy,
        "correct_count": correct_count,
        "total_queries": len(all_metrics),
        "avg_precision": accuracy,
        "avg_recall": accuracy,
        "all_metrics": all_metrics
    }


def main():
    print("="*80)
    print("TOP-1 ACCURACY EVALUATION")
    print("="*80)
    print(f"Number of test queries: {len(GROUND_TRUTH)}")
    print(f"Evaluation metric: Top-1 Accuracy (is first result correct?)")
    print(f"Test type: Direct artist/band name queries")
    
    # Initialize indexers
    print("\nInitializing indexers...")
    old_indexer = Indexer()
    if not old_indexer.documents:
        print("Building old indexer...")
        old_indexer.build_from_folder("data/joined_artists_filtered.jsonl")
    
    if not lucene.getVMEnv():
        lucene.initVM(vmargs=['-Djava.awt.headless=true'])
    new_indexer = PyLuceneIndexer()
    
    # Define search functions
    def old_search(query, k=10):
        search_engine = SearchEngine(old_indexer)
        results = search_engine.search(query, idf_method="smooth", top_k=k)
        return [old_indexer.doc_names.get(doc_id, "Unknown") for doc_id, score in results]
    
    def new_search(query, k=10):
        results = new_indexer.search(query, top_n=k)
        return [r['name'] for r in results]
    
    # Test both indexers
    k = 10
    old_results = test_indexer("Old Indexer (Custom TF-IDF)", old_search, GROUND_TRUTH, k)
    new_results = test_indexer("New Indexer (PyLucene)", new_search, GROUND_TRUTH, k)
    
    # Comparison
    print(f"\n\n{'='*80}")
    print("FINAL COMPARISON")
    print('='*80)
    
    print(f"\n{'Metric':<25} {'Old Indexer':<20} {'PyLucene':<20} {'Winner'}")
    print('-'*80)
    
    old_acc = old_results['accuracy']
    new_acc = new_results['accuracy']
    old_correct = old_results['correct_count']
    new_correct = new_results['correct_count']
    total = old_results['total_queries']
    
    winner = "PyLucene" if new_acc > old_acc else "Old" if old_acc > new_acc else "Tie"
    improvement = ((new_acc - old_acc) / old_acc * 100) if old_acc > 0 else 0
    
    print(f"{'Top-1 Accuracy':<25} {old_acc:.1%} ({old_correct}/{total}){'':<6} {new_acc:.1%} ({new_correct}/{total}){'':<6} {winner}")
    if improvement != 0:
        print(f"\nImprovement: {improvement:+.1f}%")
    
    print("\n" + "="*80)
    
    # Save results
    import json
    output = {
        "ground_truth": GROUND_TRUTH,
        "old_indexer": old_results,
        "new_indexer": new_results,
        "k": k
    }
    
    with open("evaluation_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("Detailed results saved to: evaluation_results.json")


if __name__ == "__main__":
    main()
