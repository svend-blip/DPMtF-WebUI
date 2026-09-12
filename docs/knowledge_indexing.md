# Knowledge Indexing

This file documents the default exclusions and the document size cap applied
by `knowledge/indexer.py`.

## Default directory-name exclusions

`logs`, `jobs`, `.flowrunner`, `.pytest_cache`, `.playwright-mcp`,
`.superpowers`, `.ruff_cache`, `.mypy_cache`, `.claude`, `knowledge_index`,
`dist`, `build`, `exports`, `backups`.

## Prefix exclusion

Any directory or file whose name starts with `.aider` is excluded
(`_DEFAULT_EXCLUDED_PREFIXES`).

## Default suffix exclusions

`.log`, `.jsonl`, `.bak`, `.tar`, `.gz`, `.zip`, `.whl`, `.parquet`,
`.leann`, `.idx`.

## Document size cap

`config.get_knowledge_max_document_chars()` reads
`[knowledge] max_document_chars` from `dpmtf.ini` and defaults to `20000`
when the key or section is absent. When a document's content is longer than
the cap, the indexer truncates `content` to that many characters and sets
`"truncated": true` on the emitted record; the key is absent otherwise.
`size_bytes` always keeps the real, pre-truncation file size. The CLI flag
`--max-document-chars N` overrides the configured value for one run; a
non-positive `N` is rejected with exit 1 before any manifest is written.

## Maintenance-loop consequence

`knowledge/maintenance.py` compares freshly loaded document text against the
manifest's **capped** `content`, so a document larger than the cap is
reported as changed on every maintenance pass. This is the intended
consequence of capping at record-build time; `knowledge/maintenance.py` is
not modified by this run.
