"""Judge for the held-out scenarios (WP-10).

The scenarios live outside the repository clone, in a judge-only folder (``BATATIS_JUDGE_DIR``). The judge runs the
system under test in a separate process, prints only aggregate scores and error categories, and runs the test split
once per registered arm. See ``cli.py`` for the commands and ``lock.py`` for the run-once rules.
"""
