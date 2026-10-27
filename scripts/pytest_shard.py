"""Run one slice of the test suite: PYTEST_SHARD=index/total keeps the test files whose path hashes to index.

Whole files stay together so a module's expensive fixtures are built once per shard."""
import os
import zlib


def pytest_collection_modifyitems(config, items):
    shard = os.environ.get('PYTEST_SHARD', '').strip()
    if not shard:
        return
    index, total = (int(part) for part in shard.split('/'))
    keep, drop = [], []
    for item in items:
        (keep if zlib.crc32(item.location[0].encode()) % total == index else drop).append(item)
    items[:] = keep
    config.hook.pytest_deselected(items=drop)
