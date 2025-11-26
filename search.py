import math
from collections import defaultdict

class SearchEngine:
    def __init__(self, indexer):
        self.indexer = indexer

    def idf_classic(self, term):
        N = len(self.indexer.documents)
        df = len(self.indexer.index.get(term, {}))
        if df == 0:
            return 0
        return math.log(N / df)

    def idf_smooth(self, term):
        N = len(self.indexer.documents)
        df = len(self.indexer.index.get(term, {}))
        return math.log(1 + N / (1 + df))

    def search(self, query, idf_method="classic", top_k=10):
        query_tokens = self.indexer.tokenize(query)
        scores = defaultdict(float)

        for term in query_tokens:
            postings = self.indexer.index.get(term, {})
            if not postings:
                continue

            idf = self.idf_classic(term) if idf_method == "classic" else self.idf_smooth(term)

            for doc_id, tf in postings.items():
                scores[doc_id] += tf * idf

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
