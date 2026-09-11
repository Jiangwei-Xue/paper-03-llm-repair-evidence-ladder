# E5/VCR Evidence

This directory contains 2,400 row-ledger records and 2,400 replay-index records
across three evidence strata. Every record has a canonical self-hash, and each
replay record links to its corresponding row-ledger hash. Run `replay_all.py` from
the release root to validate counts, hashes, links, and canonical claim metrics.
