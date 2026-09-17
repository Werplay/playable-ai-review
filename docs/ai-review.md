# Local AI code review

`./scripts/ai-review` reviews local Git changes using only a developer-run Ollama instance. It does not execute project code, upload source, require a PAT, or use GitHub Actions, webhooks, repository secrets, or a server.

## Prerequisites and setup

- macOS or Linux, Git, Python 3.10+, and [Ollama](https://ollama.com/).
- Install and start Ollama, then install both local models:

  ```sh
  ollama pull qwen2.5-coder:7b
  ollama pull qwen3-embedding:0.6b
  ```

The Markdown and JSON reports need no Python packages. For optional DOCX output, use an isolated environment:

```sh
python3 -m venv .venv-ai-review
. .venv-ai-review/bin/activate
python -m pip install -r requirements-ai-review.txt
```

## Usage

```sh
./scripts/ai-review --base origin/master
./scripts/ai-review --staged
./scripts/ai-review --range HEAD~3..HEAD
./scripts/ai-review --base origin/master --output ./ai-review-report
./scripts/ai-review --base origin/master --fail-on high
./scripts/ai-review --rebuild-index --index-only
```

`--base REF` reviews `merge-base(REF, HEAD)..HEAD` together with current working-tree changes. `--staged` reads the index version, even when the working tree differs. `--range A..B` reads the two explicit revisions. Binary, generated, and deleted files are reported as omitted; eligible files are never silently limited. `--fail-on high|critical` is the only review-result mode that exits nonzero (code 2); configuration and runtime errors use code 1.

## Private repository index

The first run indexes all eligible Git-tracked text files before review. Later runs hash content, reuse unchanged embeddings, update changed chunks, and remove stale chunks. Chunks retain their source text, path, line range, language, hash, model, dimensions, and timestamps in SQLite. Files larger than 1 MB, dependencies, build output, caches, lock/minified files, binaries/media/archives, and obvious credential/environment files are excluded.

By default the database is in `~/Library/Caches/ai-review` on macOS and `${XDG_CACHE_HOME:-~/.cache}/ai-review` on Linux. Set `AI_REVIEW_INDEX_DIR` to choose another per-user directory. Database names contain a normalized repository name and hash of its absolute path. Delete that one SQLite file to remove the index, or use `--rebuild-index` to recreate it.

Ollama defaults to `http://localhost:11434`, review model `qwen2.5-coder:7b`, and embedding model `qwen3-embedding:0.6b`. Override them with `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_EMBEDDING_MODEL`. Environment values and suspected secrets are never printed; retrieved context logs contain only paths and line ranges.

## Reports and troubleshooting

Reports go to `./ai-review-report/report.md` and `report.json`; `report.docx` is added when `python-docx` is installed. Terminal output includes indexing/reuse, groups, retrieval, character/token counts, model duration, candidates/rejections, verification, classifications, and coverage.

- Connection failure: run `ollama serve` and confirm `curl http://localhost:11434/api/tags` works.
- Missing models: run the exact `ollama pull` commands above.
- Incompatible/corrupt index: retry with `--rebuild-index`.
- Large reviews are processed sequentially in groups of at most three files to bound local memory.
- Model JSON is parsed defensively and retried once with a larger output budget; deterministic findings remain available when a focused model call fails.
