"""
Seeded, nested negative sampling.

Per (task, repository) the candidate negatives are sorted by instance_id and shuffled
once with a seed derived from the experiment seed, the task and the repository. The
position in that shuffle is `neg_rank`; a negative belongs to setting R=r when
neg_rank < r * n_pos. Because every setting cuts the same shuffle, R1 ⊂ R4 ⊂ R10, and
because the seed is per (task, repo), a repository's sample does not depend on which
other repositories are processed or in what order.
"""

import random


def sampling_key(seed, task, repo):
    # str seeds are hashed with sha512 by random.seed, so this is stable across runs
    return f"{seed}:{task}:{repo}"


def rank_negatives(negatives, n_pos, ratios, key):
    """Assign neg_rank and in_R{r} to negative instances (in place). Returns them in rank order."""
    negatives = sorted(negatives, key=lambda r: r["instance_id"])
    random.Random(key).shuffle(negatives)
    for rank, inst in enumerate(negatives):
        inst["neg_rank"] = rank
        for r in ratios:
            inst[f"in_R{r}"] = rank < r * n_pos
    return negatives


def mark_positives(positives, ratios):
    for inst in positives:
        inst["neg_rank"] = -1
        for r in ratios:
            inst[f"in_R{r}"] = True


def sample_stats(n_pos, n_pool, ratios):
    n_neg = {}
    achieved = {}
    for r in ratios:
        n = min(r * n_pos, n_pool)
        n_neg[f"R{r}"] = n
        achieved[f"R{r}"] = round(n / n_pos, 4) if n_pos else None
    return n_neg, achieved
