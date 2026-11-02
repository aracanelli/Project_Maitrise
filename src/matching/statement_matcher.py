"""
Match the logging statements of the pre- and post-state of one method pair.

Adapted from the replication package of Zeng et al. (2019), logdetector/detector.py
(compare_logging_method_calls). The similarity is the same: Levenshtein.ratio on the
statement text, ratio > 0.5 (`levenshtein_threshold` in configs/extraction.yaml).

Differences from upstream:
- only statements with the same logging_style can be paired (a System.out call is
  never "the same statement" as a logger call)
- upstream walks parent x head in a nested loop and overwrites mappings as it goes,
  so its result depends on statement order (a parent call can lose its partner and
  stay unmatched although another candidate is free). Here every candidate pair above
  the threshold is sorted by (-ratio, pre_index, post_index) and accepted greedily
  one-to-one, which is deterministic.
- returns positions instead of writing database rows

Statements are the compact log dicts of src/mining/method_differ.py (any dict with
"call_text" and "logging_style" works).
"""

import re

import Levenshtein


def match_statements(pre_logs, post_logs, threshold=0.5):
    """Return (pairs, unmatched_pre, unmatched_post).

    pairs is a list of (pre_pos, post_pos, ratio) sorted by pre_pos; positions are
    indexes into the two input lists.
    """
    candidates = []
    for i, a in enumerate(pre_logs):
        for j, b in enumerate(post_logs):
            if a["logging_style"] != b["logging_style"]:
                continue
            ratio = Levenshtein.ratio(a["call_text"], b["call_text"])
            if ratio > threshold:
                candidates.append((-ratio, i, j))
    candidates.sort()

    used_pre = set()
    used_post = set()
    pairs = []
    for neg_ratio, i, j in candidates:
        if i in used_pre or j in used_post:
            continue
        used_pre.add(i)
        used_post.add(j)
        pairs.append((i, j, -neg_ratio))
    pairs.sort()

    unmatched_pre = [i for i in range(len(pre_logs)) if i not in used_pre]
    unmatched_post = [j for j in range(len(post_logs)) if j not in used_post]
    return pairs, unmatched_pre, unmatched_post


def normalized_call_text(call_text):
    """Call text without whitespace, used to tell a text edit from an identical statement."""
    return "".join(call_text.split())


# Statement continuity. The upstream ratio is computed on the whole call text, so short
# calls that share a prefix such as `Gdx.app.debug(TAG, "` pass 0.5 although their
# messages are unrelated. Two statements count as the same one only if their payloads
# are also similar: the arguments without whitespace and without a leading Level.X argument.

_LEVEL_ARG = re.compile(r'^(?:[\w.]*\.)?\w*Level\.[A-Za-z]+,?')


def payload_text(call_text):
    t = "".join(call_text.split())
    i = t.find("(")
    args = t[i + 1:-1] if i >= 0 and t.endswith(")") else t[i + 1:] if i >= 0 else t
    return _LEVEL_ARG.sub("", args)


def payload_ratio(a_text, b_text):
    pa, pb = payload_text(a_text), payload_text(b_text)
    if not pa and not pb:
        return 1.0
    return Levenshtein.ratio(pa, pb)


def _receiver(call_name):
    return call_name.rsplit(".", 1)[0] if "." in call_name else ""


def is_conversion(a, b, threshold):
    """A statement rewritten from one logging style to another (System.out -> logger, ...)."""
    if a["logging_style"] == b["logging_style"]:
        return None
    if "formal" not in (a["logging_style"], b["logging_style"]):
        return None
    for x, y in ((a, b), (b, a)):
        # e.printStackTrace() <-> logger.error("...", e)
        if x["call_name"].endswith(".printStackTrace"):
            recv = _receiver(x["call_name"])
            if recv and re.search(r'\b' + re.escape(recv) + r'\b', payload_text(y["call_text"])):
                return 1.0
    r = payload_ratio(a["call_text"], b["call_text"])
    return r if r >= threshold else None


def pair_conversions(pre_logs, post_logs, unmatched_pre, unmatched_post, threshold):
    """Greedy one-to-one style conversions among the unmatched statements of one method pair."""
    candidates = []
    for i in unmatched_pre:
        for j in unmatched_post:
            r = is_conversion(pre_logs[i], post_logs[j], threshold)
            if r is not None:
                candidates.append((-r, i, j))
    candidates.sort()
    used_pre, used_post, pairs = set(), set(), []
    for neg_r, i, j in candidates:
        if i in used_pre or j in used_post:
            continue
        used_pre.add(i)
        used_post.add(j)
        pairs.append((i, j, -neg_r))
    return sorted(pairs)
