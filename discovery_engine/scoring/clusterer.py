"""Cluster similar product signals into one 'product opportunity'.

Cheap deterministic clusterer: token-set Jaccard similarity on normalized titles.
Better than nothing without embeddings, and zero external deps."""
import re

STOP = set("a an the of for and or to in on with from this that is are was were be been being it its they them we us you your i my our".split())

def _tokenize(s: str) -> set[str]:
    if not s:
        return set()
    words = re.findall(r"[a-z0-9]+", s.lower())
    return {w for w in words if w not in STOP and len(w) > 2}

def _jaccard(a: set, b: set) -> float:
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

def cluster(signals: list[dict], min_similarity: float = 0.35) -> list[list[dict]]:
    """Greedy single-link cluster on title-token Jaccard. Returns list of signal-lists."""
    tokens = [_tokenize((s.get("title") or "") + " " + " ".join(s.get("tags") or [])) for s in signals]
    clusters: list[list[int]] = []
    cluster_tokens: list[set] = []
    for i, tk in enumerate(tokens):
        placed = False
        for ci, ctk in enumerate(cluster_tokens):
            if _jaccard(tk, ctk) >= min_similarity:
                clusters[ci].append(i)
                cluster_tokens[ci] = ctk | tk
                placed = True
                break
        if not placed:
            clusters.append([i])
            cluster_tokens.append(tk)
    return [[signals[i] for i in c] for c in clusters]

def cluster_keyword(cluster_signals: list[dict]) -> str:
    """Pick a representative keyword for a cluster - most common non-stop token."""
    counts = {}
    for s in cluster_signals:
        for tok in _tokenize((s.get("title") or "")):
            counts[tok] = counts.get(tok, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]