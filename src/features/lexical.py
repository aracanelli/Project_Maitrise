"""
Identifier subtokens and a stable hashing trick.

The tabular x_ features and the graph node tokens use the same buckets, so both
representations get the same lexical information. md5 is used instead of hash() because
Python salts str hashes per process.
"""

import hashlib
import re

N_BUCKETS = 128

_CAMEL = re.compile(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+')


def subtokens(identifier):
    """'updateHUDText_now' -> ['update', 'hud', 'text', 'now']"""
    if not identifier:
        return []
    out = []
    for part in re.split(r'[^A-Za-z0-9]+', identifier):
        if not part:
            continue
        for tok in _CAMEL.findall(part):
            tok = tok.lower()
            if len(tok) > 1 and not tok.isdigit():
                out.append(tok)
    return out


_bucket_cache = {}


def bucket(token, n_buckets=N_BUCKETS):
    key = (token, n_buckets)
    b = _bucket_cache.get(key)
    if b is None:
        b = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % n_buckets
        _bucket_cache[key] = b
    return b


def bucket_counts(tokens, n_buckets=N_BUCKETS):
    counts = [0] * n_buckets
    for t in tokens:
        counts[bucket(t, n_buckets)] += 1
    return counts
