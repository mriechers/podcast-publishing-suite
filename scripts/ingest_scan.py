#!/usr/bin/env python3
"""Find new episodes on the PBS Wisconsin ingest server and pull their pieces.

Production drops finished episodes on a public Apache index. A show declares
where its episodes land and which artifacts matter, in the `ingest` block of
`shows/<slug>/config.json`; this script turns that into two answers:

    discover  -- what is on the server, what is already local, what is new
    fetch     -- download one episode's declared artifacts into its folder

Deliberately stdlib-only (urllib, re) so it runs under plain `python3` with no
virtualenv, the same call the transcription pipeline makes for
`apply_glossary.py`. It also owns its own scanning rather than depending on
Cardigan's mmingest MCP index: that index is a separate product's internal
service, it keys on the strict 8-character Media ID grammar and so misses
McCoshen & Ross entirely, and a publishing pipeline should not break when
another repo's server changes.

Usage:
    python3 scripts/ingest_scan.py discover --show in-focus
    python3 scripts/ingest_scan.py discover --show in-focus --all
    python3 scripts/ingest_scan.py fetch --show in-focus --episode 6INF0123
    python3 scripts/ingest_scan.py fetch --show in-focus --episode 6INF0123 --dry-run
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stitch_audio import episode_dirs, load_show_config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# Apache FancyIndexing rows: name cell, then right-aligned modified and size.
ROW = re.compile(
    r'<a href="(?P<href>[^"?/][^"]*)">[^<]*</a>\s*</td>\s*'
    r'<td[^>]*>\s*(?P<modified>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*</td>\s*'
    r'<td[^>]*>\s*(?P<size>[^<]*?)\s*</td>',
    re.IGNORECASE,
)

REVISION_SUFFIX = re.compile(r"_REV\d{8}$", re.IGNORECASE)

TIMEOUT_S = 60
DOWNLOAD_TIMEOUT_S = 1800
CHUNK = 1 << 20  # 1 MiB


class IngestConfigError(Exception):
    """The show's `ingest` block is malformed."""


@dataclass(frozen=True)
class ListingEntry:
    name: str
    modified: str
    size: str


@dataclass(frozen=True)
class Artifact:
    ext: str
    dest: str
    required: bool


@dataclass(frozen=True)
class IngestSpec:
    url: str
    pattern: re.Pattern
    artifacts: dict


@dataclass(frozen=True)
class Episode:
    key: str
    base: str
    files: dict = field(default_factory=dict)

    @property
    def is_revision(self) -> bool:
        return self.key != self.base

    @property
    def latest_modified(self) -> str:
        return max((e.modified for e in self.files.values()), default="")


@dataclass(frozen=True)
class FetchItem:
    ext: str
    url: str
    dest: Path
    size: str


# --- config ------------------------------------------------------------


def load_ingest_spec(config: dict) -> IngestSpec:
    block = config.get("ingest")
    if not isinstance(block, dict):
        raise IngestConfigError(
            "show config has no `ingest` block -- add one to declare where "
            "this show's episodes arrive (see shows/README.md)"
        )

    problems = []

    url = block.get("url")
    if not isinstance(url, str) or not url.strip():
        problems.append("  ingest.url must be the listing URL for this show")
        url = ""
    elif not url.endswith("/"):
        url += "/"

    pattern = None
    raw = block.get("episodePattern")
    if not isinstance(raw, str) or not raw.strip():
        problems.append("  ingest.episodePattern must be a regex matching an episode's filename stem")
    else:
        try:
            pattern = re.compile(raw)
        except re.error as exc:
            problems.append(f"  ingest.episodePattern is not a valid regex ({exc})")

    artifacts = {}
    raw_artifacts = block.get("artifacts")
    if not isinstance(raw_artifacts, dict) or not raw_artifacts:
        problems.append("  ingest.artifacts must be a non-empty map of extension -> options")
    else:
        for ext, options in raw_artifacts.items():
            if not isinstance(ext, str) or not ext.startswith("."):
                problems.append(f"  ingest.artifacts key {ext!r} must start with a dot, e.g. '.wav'")
                continue
            options = options or {}
            if not isinstance(options, dict):
                problems.append(f"  ingest.artifacts['{ext}'] must be an object")
                continue
            artifacts[ext.lower()] = Artifact(
                ext=ext.lower(),
                dest=options.get("dest", ""),
                required=bool(options.get("required", False)),
            )

    if problems:
        raise IngestConfigError("Invalid `ingest` block:\n" + "\n".join(problems))

    return IngestSpec(url=url, pattern=pattern, artifacts=artifacts)


# --- pure parsing / grouping -------------------------------------------


def parse_listing(html: str) -> list:
    """Files in an Apache index. Directories and the parent link are dropped."""
    return [
        ListingEntry(
            name=urllib.parse.unquote(m.group("href")),
            modified=m.group("modified"),
            size=m.group("size").strip(),
        )
        for m in ROW.finditer(html)
        if not m.group("href").endswith("/")
    ]


def split_stem(name: str) -> tuple:
    dot = name.rfind(".")
    if dot <= 0:
        return name, ""
    return name[:dot], name[dot:]


def base_key(key: str) -> str:
    """An episode's identity without its revision stamp.

    `6INF0121` and `6INF0121_REV20260409` are separate deliverables and stay
    separate episodes -- conflating them risks stitching the superseded cut --
    but they share a base so a revision can be reported as such.
    """
    return REVISION_SUFFIX.sub("", key)


def group_episodes(entries: list, spec: IngestSpec) -> list:
    """Episodes on the server, newest first, carrying only declared artifacts."""
    collected: dict = {}
    for entry in entries:
        stem, ext = split_stem(entry.name)
        if ext.lower() not in spec.artifacts or not spec.pattern.search(stem):
            continue
        collected.setdefault(stem, {})[ext.lower()] = entry

    episodes = [
        Episode(key=key, base=base_key(key), files=files)
        for key, files in collected.items()
    ]
    return sorted(episodes, key=lambda e: (e.latest_modified, e.key), reverse=True)


def local_episode_keys(episodes_dir: Path) -> set:
    if not episodes_dir.is_dir():
        return set()
    return {p.name for p in episodes_dir.iterdir() if p.is_dir() and not p.name.startswith(".")}


def plan_fetch(episode: Episode, spec: IngestSpec, episode_dir: Path) -> tuple:
    """What to download, and which required artifacts are simply not there.

    Anything already on disk is skipped -- and counts as satisfied, so a
    re-run after a partial pull does not report the body as missing.
    """
    items = []
    missing = []
    for ext, artifact in spec.artifacts.items():
        dest = episode_dir / artifact.dest / f"{episode.key}{ext}" if artifact.dest \
            else episode_dir / f"{episode.key}{ext}"
        entry = episode.files.get(ext)
        if entry is None:
            if artifact.required and not dest.exists():
                missing.append(ext)
            continue
        if dest.exists():
            continue
        items.append(
            FetchItem(
                ext=ext,
                url=urllib.parse.urljoin(spec.url, urllib.parse.quote(entry.name)),
                dest=dest,
                size=entry.size,
            )
        )
    return items, missing


# --- network -----------------------------------------------------------


def fetch_listing(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        sys.exit(f"Ingest listing returned HTTP {exc.code} for {url}")
    except urllib.error.URLError as exc:
        sys.exit(
            f"Could not reach the ingest server at {url}\n  {exc.reason}\n"
            "This server is on the PBS Wisconsin network -- check VPN."
        )


def download(item: FetchItem) -> None:
    """Stream to a .part file, then rename.

    The rename is what makes `plan_fetch`'s skip-if-exists safe: an interrupted
    download leaves a .part behind, never a truncated file that looks complete.
    """
    item.dest.parent.mkdir(parents=True, exist_ok=True)
    partial = item.dest.with_suffix(item.dest.suffix + ".part")
    # Carriage-return progress only makes sense on a terminal. Piped -- which
    # is how an agent runs this -- it turns one line into hundreds.
    show_progress = sys.stdout.isatty()
    try:
        with urllib.request.urlopen(item.url, timeout=DOWNLOAD_TIMEOUT_S) as response:
            expected = response.headers.get("Content-Length")
            expected = int(expected) if expected and expected.isdigit() else None
            written = 0
            with open(partial, "wb") as handle:
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
                    if expected and show_progress:
                        print(f"\r    {written / expected:6.1%}  "
                              f"{written / 1e6:8.1f} MB", end="", flush=True)
            if show_progress:
                print("\r" + " " * 32 + "\r", end="")
    except urllib.error.URLError as exc:
        partial.unlink(missing_ok=True)
        sys.exit(f"Download failed for {item.url}\n  {exc}")

    if expected is not None and written != expected:
        partial.unlink(missing_ok=True)
        sys.exit(
            f"Download was truncated: got {written} bytes, expected {expected}\n"
            f"  {item.url}\nNothing was written; re-run to retry."
        )
    partial.replace(item.dest)


# --- CLI ---------------------------------------------------------------


def show_context(slug: str):
    config, _ = load_show_config(slug)
    try:
        spec = load_ingest_spec(config)
    except IngestConfigError as exc:
        sys.exit(f"shows/{slug}/config.json: {exc}")
    episodes_root = episode_dirs(config, slug, "_", REPO_ROOT)[0].parent
    return config, spec, episodes_root


def cmd_discover(args) -> None:
    config, spec, episodes_root = show_context(args.show)
    episodes = group_episodes(parse_listing(fetch_listing(spec.url)), spec)
    known = local_episode_keys(episodes_root)

    new = [e for e in episodes if e.key not in known]
    shown = episodes if args.all else new

    print(f"Show:   {config.get('name', args.show)}")
    print(f"Ingest: {spec.url}")
    print(f"Local:  {episodes_root}  ({len(known)} episode folder"
          f"{'' if len(known) == 1 else 's'})\n")

    if not shown:
        print("No new episodes. Re-run with --all to list everything on the server.")
        return

    label = "All episodes" if args.all else "New episodes"
    print(f"{label} (newest first):")
    for episode in shown:
        marks = []
        if episode.key in known:
            marks.append("local")
        if episode.is_revision:
            marks.append(f"revision of {episode.base}")
        missing = [
            ext for ext, a in spec.artifacts.items()
            if a.required and ext not in episode.files
        ]
        if missing:
            marks.append(f"MISSING {', '.join(missing)}")
        suffix = f"   [{'; '.join(marks)}]" if marks else ""
        have = " ".join(sorted(episode.files))
        print(f"  {episode.key:<26} {episode.latest_modified}   {have}{suffix}")

    if not args.all:
        print(f"\nPull one with:\n  python3 scripts/ingest_scan.py fetch "
              f"--show {args.show} --episode <key>")


def cmd_fetch(args) -> None:
    config, spec, episodes_root = show_context(args.show)
    episodes = {e.key: e for e in group_episodes(parse_listing(fetch_listing(spec.url)), spec)}

    episode = episodes.get(args.episode)
    if episode is None:
        available = ", ".join(list(episodes)[:8]) or "(none)"
        sys.exit(
            f"No episode '{args.episode}' on {spec.url}\n"
            f"Most recent: {available}\n"
            "Run `discover --all` to see everything."
        )

    episode_dir, _ = episode_dirs(config, args.show, episode.key, REPO_ROOT)
    items, missing = plan_fetch(episode, spec, episode_dir)

    print(f"Show:    {config.get('name', args.show)}")
    print(f"Episode: {episode.key}"
          + (f"   (revision of {episode.base})" if episode.is_revision else ""))
    print(f"Into:    {episode_dir}\n")

    if missing:
        sys.exit(
            "Required artifacts are not on the server yet: "
            f"{', '.join(missing)}\n"
            "Production has not finished delivering this episode. Try again later."
        )

    if not items:
        print("Everything is already downloaded. Nothing to do.")
        return

    for item in items:
        print(f"  {item.ext:<6} {item.size:>6}  -> {item.dest.relative_to(episode_dir)}")

    if args.dry_run:
        print("\n[DRY RUN] Nothing downloaded.")
        return

    print()
    for item in items:
        print(f"  {item.dest.name} ({item.size})")
        download(item)
    print(f"\nDownloaded {len(items)} file{'' if len(items) == 1 else 's'} into {episode_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="List episodes on the ingest server")
    discover.add_argument("--show", required=True)
    discover.add_argument("--all", action="store_true",
                          help="Include episodes already present locally")
    discover.set_defaults(func=cmd_discover)

    fetch = sub.add_parser("fetch", help="Download one episode's artifacts")
    fetch.add_argument("--show", required=True)
    fetch.add_argument("--episode", required=True)
    fetch.add_argument("--dry-run", action="store_true", help="Report the plan, download nothing")
    fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
