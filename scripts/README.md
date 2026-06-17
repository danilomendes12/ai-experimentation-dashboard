# scripts/

Utilities to build a content-only Markdown corpus for testing the vector
storage / RAG pipeline. Output goes to `data/` (gitignored), so re-run the
scripts to regenerate it on any machine.

## Corpus builders

| Script | Source | Output |
|---|---|---|
| `fetch_k8s_docs.py` | kubernetes/website → `content/en/docs/{concepts,tutorials}` | `data/k8s_docs/` |
| `fetch_postgres_docs.py` | postgres/postgres → `doc/src/sgml` (DocBook) | `data/postgres_docs/` |

```bash
uv run python scripts/fetch_k8s_docs.py
uv run python scripts/fetch_postgres_docs.py
```

Both scripts sparse + shallow clone their repo into `data/_src/<repo>` (reused
on later runs) and rebuild the output directory from scratch each time.

### What gets stripped

- **Kubernetes** (Hugo Markdown): YAML frontmatter, HTML comments, and Hugo
  shortcodes. `glossary_tooltip` is collapsed to its display text, `heading`
  shortcodes become real `##` headings, callout markers (`note`/`caution`/…)
  are unwrapped, and any other shortcode is dropped. The frontmatter `title`
  is promoted to an `# H1` so each file keeps its topic.
- **PostgreSQL** (DocBook SGML): custom/include entities (`&version;`,
  `&xtypes;`, …) are neutralized so `pandoc` can parse each file standalone;
  named character entities (`&mdash;`, `&sect;`, …) map to Unicode; conversion
  is `pandoc -f docbook -t gfm`; unresolved cross-references (`[???](#…)`) are
  removed.

### Requirements

- `git` (sparse-checkout, `--filter=blob:none`)
- `pandoc` — Postgres only (`brew install pandoc`)

### Notes / known residue

- Postgres output keeps `&lt; &gt; &amp; &quot;` — these are pandoc's
  GFM-safe encodings and render correctly as `< > & "`.
- Files that are pure include manifests (`filelist.sgml`, `*/allfiles.sgml`,
  section landing stubs) are skipped; output is content only.
