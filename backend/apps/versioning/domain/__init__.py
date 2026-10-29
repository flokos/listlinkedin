"""The versioning domain core: snapshots and diffs as plain data.

Nothing here imports Django, DRF or another app (docs/v2/03-ARCHITECTURE.md rule 1); a test
walks the AST to keep it that way (apps/versioning/tests/test_domain_imports.py).
"""
