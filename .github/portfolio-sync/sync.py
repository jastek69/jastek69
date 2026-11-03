#!/usr/bin/env python3
"""Keep portfolio pages in step with the project repos they describe.

Three kinds of link, declared in manifest.json:

  mirror   A LOCAL-ONLY verbatim copy of a source file, kept for reference.
           Mirrors of private repos must never be published, so the target
           must be gitignored (the script refuses otherwise) and entries
           whose file is absent (as in CI) are skipped.
           `sync` overwrites the local copy with the source's current text.
  block    A small fact inside a hand-written page, between
           <!-- sync:KEY --> and <!-- /sync:KEY --> markers, extracted
           from a source file by regex. `sync` rewrites only the marked span.
  watch    A source file a hand-written page summarizes. Nothing is rewritten:
           when its content changes after the pinned version, the page is
           reported for human review. `ack` re-pins after you've reviewed it.

Commands:
  check      Report drift; exit 1 if anything is out of date.
  sync       Apply mirror and block updates; report watch drift; exit 0
             (2 on errors).
  ack        Pin watched sources to their current version
             (--all, or --page PATH ...).
  baseline   Pin any unpinned watched source to the version that existed when
             the portfolio page was last committed.

Auth: PORTFOLIO_READ_TOKEN, then GH_TOKEN / GITHUB_TOKEN, then `gh auth token`.
Most source repos are private and this portfolio repo is public, so reports
name only paths and short SHAs, never commit messages or diffs.

Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
MANIFEST = HERE / "manifest.json"
PINS = HERE / "pins.json"
API = "https://api.github.com"


# --------------------------------------------------------------------------- #
# GitHub access
# --------------------------------------------------------------------------- #
def _token() -> str | None:
    for name in ("PORTFOLIO_READ_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True,
                             text=True, check=True)
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


TOKEN = _token()


class FetchError(Exception):
    pass


def _get(url: str, attempts: int = 3) -> object:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "portfolio-sync",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code >= 500 and attempt < attempts:
                time.sleep(2 * attempt)
                continue
            # 404 is also what GitHub returns for a private repo the token can't read.
            raise FetchError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            if attempt < attempts:
                time.sleep(2 * attempt)
                continue
            raise FetchError(str(exc.reason)) from exc
    raise FetchError("unreachable")


def fetch_file(owner: str, repo: str, path: str, ref: str | None = None) -> tuple[str, str]:
    """Return (text, blob_sha). Text is normalized to LF line endings."""
    q = f"?ref={urllib.parse.quote(ref)}" if ref else ""
    data = _get(f"{API}/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}{q}")
    if not isinstance(data, dict) or data.get("type") != "file":
        raise FetchError("not a file")
    if data.get("encoding") == "base64" and data.get("content"):
        raw = base64.b64decode(data["content"])
    else:  # files over 1 MB come back without inline content
        raw = base64.b64decode(_get(data["git_url"])["content"])
    return raw.decode("utf-8").replace("\r\n", "\n"), data["sha"]


def latest_commit(owner: str, repo: str, path: str, until: str | None = None) -> str | None:
    q = {"path": path, "per_page": "1"}
    if until:
        q["until"] = until
    data = _get(f"{API}/repos/{owner}/{repo}/commits?{urllib.parse.urlencode(q)}")
    return data[0]["sha"] if data else None


# --------------------------------------------------------------------------- #
# Manifest, pins, reporting
# --------------------------------------------------------------------------- #
def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_pins(pins: dict) -> None:
    PINS.write_text(json.dumps(dict(sorted(pins.items())), indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def read_page(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def write_page(rel: str, text: str) -> None:
    """Write LF-normalized text, keeping the file's existing line-ending style."""
    path = REPO_ROOT / rel
    crlf = path.exists() and b"\r\n" in path.read_bytes()
    path.write_text(text, encoding="utf-8", newline="\r\n" if crlf else "\n")


def is_gitignored(rel: str) -> bool:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--", rel])
    return out.returncode == 0


def pin_key(repo: str, path: str) -> str:
    return f"{repo}:{path}"


@dataclass
class Report:
    mirrors: list[str] = field(default_factory=list)   # stale (check) / updated (sync)
    blocks: list[str] = field(default_factory=list)
    review: list[str] = field(default_factory=list)    # watch drift, human needed
    errors: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.mirrors or self.blocks or self.review or self.errors)

    def markdown(self, applied: bool) -> str:
        verb = "Updated" if applied else "Out of date"
        out = ["## Portfolio sync report", ""]
        if self.clean:
            return "\n".join(out + ["Every page matches its sources. Nothing to do.", ""])
        for title, items in (
            (f"{verb}: local-only reference copies (gitignored, never pushed)", self.mirrors),
            (f"{verb}: synced facts", self.blocks),
            ("Needs human review: hand-written pages whose sources changed", self.review),
            ("Errors", self.errors),
        ):
            if items:
                out += [f"### {title}", "", *[f"- {i}" for i in items], ""]
        if self.review:
            out += ["After reviewing a page (edit it, or decide it still holds), acknowledge it:",
                    "", "```bash",
                    "python .github/portfolio-sync/sync.py ack --page <portfolio page path>",
                    "```", ""]
        return "\n".join(out)


def _short(sha: str | None) -> str:
    return sha[:7] if sha else "?"


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def run(apply: bool) -> Report:
    manifest = load_json(MANIFEST, None)
    if manifest is None:
        sys.exit(f"missing {MANIFEST}")
    owner = manifest["owner"]
    pins = load_json(PINS, {})
    rep = Report()

    for entry in manifest["pages"]:
        page, repo = entry["page"], entry["repo"]

        # ---- mirror (local-only) -------------------------------------------
        if entry.get("mode") == "mirror":
            if not is_gitignored(page):
                rep.errors.append(f"`{page}`: mirror target is not gitignored; refusing to "
                                  "sync a verbatim private-repo copy into a published path")
                continue
            if not (REPO_ROOT / page).exists():
                continue  # local-only copy absent (e.g. in CI): nothing to refresh
            src = entry["source"]
            try:
                text, _ = fetch_file(owner, repo, src)
            except FetchError as exc:
                rep.errors.append(f"`{page}`: cannot read `{repo}/{src}` ({exc})")
                continue
            if read_page(page) != text:
                rep.mirrors.append(f"`{page}` ← `{repo}/{src}`")
                if apply:
                    write_page(page, text)
            continue

        if not (REPO_ROOT / page).exists():
            rep.errors.append(f"`{page}`: page file not found in this repo")
            continue

        # ---- blocks --------------------------------------------------------
        page_text = read_page(page)
        new_text = page_text
        for key, spec in entry.get("blocks", {}).items():
            try:
                src_text, _ = fetch_file(owner, repo, spec["file"])
            except FetchError as exc:
                rep.errors.append(f"`{page}` [{key}]: cannot read `{repo}/{spec['file']}` ({exc})")
                continue
            m = re.search(spec["regex"], src_text)
            if not m:
                rep.errors.append(f"`{page}` [{key}]: pattern not found in `{repo}/{spec['file']}`")
                continue
            value = spec["format"].format(*m.groups())
            marker = re.compile(rf"(<!-- sync:{re.escape(key)} -->)(.*?)(<!-- /sync:{re.escape(key)} -->)",
                                re.S)
            mm = marker.search(new_text)
            if not mm:
                rep.errors.append(f"`{page}` [{key}]: no `<!-- sync:{key} -->` markers in page")
                continue
            if mm.group(2) != value:
                rep.blocks.append(f"`{page}` [{key}]: `{mm.group(2)}` → `{value}`")
                new_text = new_text[:mm.start(2)] + value + new_text[mm.end(2):]
        if apply and new_text != page_text:
            write_page(page, new_text)

        # ---- watch ---------------------------------------------------------
        for src in entry.get("watch", []):
            k = pin_key(repo, src)
            pin = pins.get(k)
            if not pin:
                rep.errors.append(f"`{page}`: `{repo}/{src}` has no pin (run `baseline` or `ack`)")
                continue
            try:
                _, blob = fetch_file(owner, repo, src)
            except FetchError as exc:
                rep.errors.append(f"`{page}`: cannot read `{repo}/{src}` ({exc})")
                continue
            if blob != pin["blob"]:
                try:
                    head = latest_commit(owner, repo, src)
                except FetchError:
                    head = None
                link = (f"https://github.com/{owner}/{repo}/compare/{pin['commit']}...{head}"
                        if head and pin.get("commit") else f"https://github.com/{owner}/{repo}")
                rep.review.append(f"`{page}`: `{repo}/{src}` changed "
                                  f"({_short(pin.get('commit'))} → {_short(head)}, [compare]({link}))")
    return rep


def pin_current(entries: list[dict], owner: str, pins: dict, until_from_git: bool) -> list[str]:
    done = []
    for entry in entries:
        for src in entry.get("watch", []):
            k = pin_key(entry["repo"], src)
            if until_from_git and k in pins:
                continue
            until = None
            if until_from_git:
                out = subprocess.run(["git", "-C", str(REPO_ROOT), "log", "-1", "--format=%cI",
                                      "--", entry["page"]], capture_output=True, text=True)
                until = out.stdout.strip() or None
            commit = latest_commit(owner, entry["repo"], src, until=until)
            if not commit:
                done.append(f"{k}: no commit found{' before ' + until if until else ''}; skipped")
                continue
            _, blob = fetch_file(owner, entry["repo"], src, ref=commit)
            pins[k] = {"blob": blob, "commit": commit}
            done.append(f"{k}: pinned {commit[:7]}" + (f" (as of {until})" if until else ""))
    return done


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "sync"):
        p = sub.add_parser(name)
        p.add_argument("--report", help="write the markdown report to this file")
    p = sub.add_parser("ack")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--page", action="append", help="portfolio page path (repeatable)")
    sub.add_parser("baseline")
    args = ap.parse_args()

    if args.cmd in ("check", "sync"):
        rep = run(apply=args.cmd == "sync")
        md = rep.markdown(applied=args.cmd == "sync")
        print(md)
        if args.report:
            Path(args.report).write_text(md, encoding="utf-8")
        if rep.errors:
            return 2
        return 0 if (args.cmd == "sync" or rep.clean) else 1

    manifest = load_json(MANIFEST, None)
    pins = load_json(PINS, {})
    if args.cmd == "ack":
        entries = manifest["pages"] if args.all else [
            e for e in manifest["pages"] if e["page"] in set(args.page)]
        if not args.all and len(entries) != len(set(args.page)):
            known = {e["page"] for e in manifest["pages"]}
            sys.exit(f"not in manifest: {sorted(set(args.page) - known)}")
        lines = pin_current(entries, manifest["owner"], pins, until_from_git=False)
    else:
        lines = pin_current(manifest["pages"], manifest["owner"], pins, until_from_git=True)
    save_pins(pins)
    print("\n".join(lines) or "nothing to pin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
