# Runbook: Elasticsearch operations

- Disk watermarks: at the high watermark (90%) shards are moved off the node. At the flood stage
  (95%) every index with a shard on that node becomes read-only, and unassigned shards make
  searches fail with "all shards failed".
- Recovery: free disk (delete old snapshots or logs on the node, not live indices) or add
  capacity, then clear the block with `PUT <index>/_settings {"index.blocks.read_only_allow_delete": null}`.
- Never delete live indices to free space. Re-indexing search-products takes about 6 hours.
- Alert on disk usage above 85% per data node.
