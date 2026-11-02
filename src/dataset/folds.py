"""
Leave-one-repository-out fold eligibility, written to folds.json.

A repository is held out as a test fold for a task when it has at least
`min_test_positives` positives; folds below `low_support_positives` are flagged.
Repositories under the threshold are listed in `excluded` with their count and still
train every fold.

With the positives' commits, each task also gets `per_repo` (n_pos, n_pos_commits =
distinct commits among the positives, max_commit_share = largest share of the positives
held by one commit, None without positives) and `few_commit_folds`, the test repositories
whose positives come from at most `few_commits` commits: their test metrics describe a
handful of commits, not a repository.

The counts are the assembled positives, before any view, feature or graph failure of
later stages; the model stage has to re-check the thresholds on the instances it
actually evaluates.
"""


def make_folds(pos_counts, repo_order, min_test, low_support, pos_commits=None, few_commits=2):
    """pos_counts: {task: {repo: n_pos}}; repo_order fixes the order of the lists.

    pos_commits (optional): {task: {repo: Counter(commit_id -> positives)}}.
    """
    folds = {}
    for task, counts in pos_counts.items():
        test_repos = []
        low = []
        excluded = {}
        for repo in repo_order:
            if repo not in counts:
                continue
            n = counts[repo]
            if n >= min_test:
                test_repos.append(repo)
                if n < low_support:
                    low.append(repo)
            else:
                excluded[repo] = n
        folds[task] = {"test_repos": test_repos, "low_support": low, "excluded": excluded}
        if pos_commits is None:
            continue
        per_repo = {}
        for repo in repo_order:
            if repo not in counts:
                continue
            commits = pos_commits.get(task, {}).get(repo, {})
            n = counts[repo]
            share = round(max(commits.values()) / n, 4) if n and commits else None
            per_repo[repo] = {"n_pos": n, "n_pos_commits": len(commits), "max_commit_share": share}
        folds[task]["per_repo"] = per_repo
        folds[task]["few_commit_folds"] = [r for r in test_repos if per_repo[r]["n_pos_commits"] <= few_commits]
    return folds
