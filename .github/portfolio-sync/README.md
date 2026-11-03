# Portfolio sync

Keeps the pages under `cloud-architecture-portfolio/architectures/` in step
with the project repos they describe. The pages are hand-written summaries,
not copies, so nothing rewrites your prose. Instead:

| Link | What it does | Where it runs |
|---|---|---|
| **watch** | A source file a page summarizes (usually its `README.md`). When the file's content changes after the pinned version, the page is listed for review. | CI + local |
| **block** | One fact inside a page, between `<!-- sync:KEY -->` and `<!-- /sync:KEY -->` (HTML comments, invisible when rendered), extracted from a source file by regex and rewritten automatically. | CI + local |
| **mirror** | Refreshes a **local-only, gitignored** verbatim copy of a private-repo doc. The script refuses to write a mirror to any path that isn't gitignored, and CI skips mirrors because they aren't checked out. | Local only |

Config: `manifest.json`. Pins (the reviewed version of each watched file, as a
blob SHA plus the commit it came from): `pins.json`. Both are committed.

## Commands

```bash
python .github/portfolio-sync/sync.py check      # report; exit 1 if anything is out of date
python .github/portfolio-sync/sync.py sync       # rewrite blocks + local mirrors; report the rest
python .github/portfolio-sync/sync.py ack --page cloud-architecture-portfolio/architectures/serverless/README.md
python .github/portfolio-sync/sync.py ack --all  # after reviewing everything
python .github/portfolio-sync/sync.py baseline   # pin new watch entries to the version current when the page was last committed
```

Locally it authenticates with your `gh` login. In CI it uses `PORTFOLIO_READ_TOKEN`.

## Reviewing a page

1. Open the issue's **compare** link to see what changed in the source.
2. Edit the portfolio page, or decide it still holds.
3. Run `ack --page <path>`, then commit `pins.json` (with the page edit, if any).

The next run closes the issue once nothing is waiting for review.

## Adding a page

Add an entry to `manifest.json`, run `baseline`, and commit both files. To
auto-sync a number, wrap it in markers on the page and add a `blocks` entry.
For example, the Agent 11 test count:

```json
"blocks": { "tests": {
  "file": "docs/TESTING.md",
  "regex": "\\*\\*Result: (\\d+) of (\\d+) pass",
  "format": "**{1} inline contract tests**, {0} passing"
} }
```

## Token setup (one time)

GitHub → Settings → Developer settings → Fine-grained tokens → Generate:

- **Resource owner:** jastek69. **Repository access:** only the private source repos in `manifest.json`.
- **Permissions:** Contents → Read-only. Nothing else.
- Save it in this repo as the Actions secret `PORTFOLIO_READ_TOKEN`:
  `gh secret set PORTFOLIO_READ_TOKEN -R jastek69/jastek69`

## Triggering from source repos (optional)

The workflow runs every Monday and listens for `repository_dispatch` types
`soar-main-pushed` (already sent by SOAR's `notify-dependents.yml`, once this
repo is added to its matrix) and `portfolio-source-pushed`.
