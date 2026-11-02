# Third-party code and tools

## Replication package of Zeng et al. (2019)

Y. Zeng, J. Chen, W. Shang and T.-H. Chen, "Studying the characteristics of logging practices in mobile apps: a case study on F-Droid", *Empirical Software Engineering*, 24(6), 2019.

The following files adapt code from the `LogDetector` tool of that replication package (detection predicate, srcML calls, commit traversal, three-pass method matching and Levenshtein statement matching). The adaptations are described in each file's header.

- `src/parsing/srcml_parser.py` (from `logdetector/codetransform.py`)
- `src/detection/log_detection.py` (from `logdetector/codetransform.py`)
- `src/detection/verbosity.py` (from `logdetector/metrics.py`)
- `src/detection/scan.py`
- `src/mining/git_walker.py` (from `logdetector/utils/githelper.py` and `logdetector/detector.py`)
- `src/mining/method_differ.py` (from `logdetector/detector.py`)
- `src/matching/statement_matcher.py` (from `logdetector/detector.py`)

The replication package does not include a licence file. Its authors keep the rights to the original code.

## LogAdvisor (Zhu et al., 2015)

The "logged catch" and "empty catch" method features in `src/features/method_features.py` follow the feature definitions of LogAdvisor (J. Zhu et al., "Learning to log: helping developers make informed logging decisions", ICSE 2015). No LogAdvisor code is included.

## Tools called at run time

srcML (https://www.srcml.org) and Git are invoked as external programs and are not distributed with this code. Python dependencies are listed in `pyproject.toml` and `requirements-lock.txt` under their own licences.
