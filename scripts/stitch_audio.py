#!/usr/bin/env python3
"""Assemble a show's segments into one deliverable audio file.

A show declares its structure once, in `shows/<slug>/config.json`, as an
ordered list of slots. Each slot is either an `asset` (a fixed file the show
owns -- the standing intro, the outro) or an `episode` file the producer
supplies this time. Any agent handed a folder of pieces can then assemble
them without knowing anything show-specific:

    python3 scripts/stitch_audio.py --show in-focus --from ./raw/ --out ep.mp3

Two invariants, both learned the hard way elsewhere in this repo:

1. Order comes from the config, never from the filesystem. `sorted()` is not
   playback order -- "mid" sorts before "mix", which is why the E10-E18
   manifests all record Wonder Cabinet's parts backwards. See
   `scripts/resolve_audio.py` and CLAUDE.md.
2. Resolution fails loudly and completely. A stitch that silently drops or
   reorders a segment produces a file that sounds fine for its first minute
   and is wrong thereafter -- the kind of error that reaches air. Every
   problem is reported at once, so one run tells you everything.

Everything for an episode lives under its show folder, the stitched
deliverable included: `--episode <slug>` reads the pieces from that episode's
audio directory and writes the result back beside them. `--from` and `--out`
override either half for one-offs.

Usage:
    # The normal case: pieces in the episode folder, output back into it
    python3 scripts/stitch_audio.py --show in-focus --episode 6INF0123

    # Pieces from somewhere else, output still in the episode folder
    python3 scripts/stitch_audio.py --show in-focus --episode 6INF0123 \
        --from ~/Downloads/ingest/

    # Pin a slot the patterns can't resolve (also overrides an asset slot)
    python3 scripts/stitch_audio.py --show in-focus --episode 6INF0123 \
        --slot program=~/Downloads/0815_cut.mp3

    # Report the plan, touching nothing
    python3 scripts/stitch_audio.py --show mccoshen-ross --from ./raw/ --dry-run
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff"}

# Codecs a container will accept without re-encoding. Stream-copying a
# 24-bit WAV into an .mp3 is not a thing, and the archive this was built
# against is entirely 24-bit/48k WAV, so this check is load-bearing.
CONTAINER_CODECS = {
    ".mp3": {"mp3"},
    ".wav": {"pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le"},
    ".aif": {"pcm_s16be", "pcm_s24be"},
    ".aiff": {"pcm_s16be", "pcm_s24be"},
    ".m4a": {"aac", "alac"},
    ".aac": {"aac"},
    ".flac": {"flac"},
    ".ogg": {"vorbis", "opus"},
    ".opus": {"opus"},
}

ENCODERS = {
    ".mp3": "libmp3lame",
    ".m4a": "aac",
    ".aac": "aac",
    ".flac": "flac",
    ".ogg": "libvorbis",
    ".opus": "libopus",
    ".wav": "pcm_s24le",
    ".aif": "pcm_s24be",
    ".aiff": "pcm_s24be",
}

LOSSLESS_CODECS = {
    "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le",
    "pcm_s16be", "pcm_s24be", "flac", "alac",
}

DEFAULT_OUTPUT_TEMPLATE = "{episode}.mp3"

DEFAULT_LOSSY_BITRATE = "192k"  # what In Focus and McCoshen & Ross ship today
MAX_LOSSY_BITRATE_KBPS = 320

# A 192k MP3 reports ~196 kbps once container overhead is counted, so a derived
# rate has to be snapped back onto the ladder or every re-encode drifts upward
# into a non-standard value.
STANDARD_BITRATES_KBPS = (64, 80, 96, 112, 128, 160, 192, 224, 256, 320)

# A stitch that comes out meaningfully shorter than its inputs has dropped
# something. Mirrors the shortfall guard in the correction-review tooling.
DURATION_MARGIN_S = 2.0

FFMPEG_TIMEOUT_S = 1800


class StitchConfigError(Exception):
    """The show's `stitch` block is malformed."""


class StitchResolutionError(Exception):
    """The supplied files do not map onto the show's slots.

    Always reports every problem at once. Fixing one thing, re-running, and
    discovering the next is how a producer ends up guessing.
    """


@dataclass(frozen=True)
class Segment:
    id: str
    source: str  # "asset" | "episode"
    file: str | None
    match: re.Pattern | None
    required: bool
    fade_in_ms: int
    fade_out_ms: int


@dataclass(frozen=True)
class StitchSpec:
    segments: tuple[Segment, ...]
    bitrate: str | None
    sample_rate: int | None
    output: str


@dataclass(frozen=True)
class EpisodePaths:
    episode_dir: Path
    audio_dir: Path
    out_path: Path


@dataclass(frozen=True)
class ResolvedSegment:
    id: str
    path: Path
    fade_in_ms: int
    fade_out_ms: int


@dataclass(frozen=True)
class Probe:
    codec: str
    sample_rate: int
    channels: int
    duration: float
    bitrate: int | None


@dataclass(frozen=True)
class EncodePlan:
    mode: str  # "copy" | "reencode"
    reasons: tuple[str, ...]
    bitrate: str | None
    sample_rate: int
    channels: int
    total_duration: float
    encoder: str | None


# --- config ------------------------------------------------------------


def load_stitch_spec(config: dict) -> StitchSpec:
    """Validate and normalise a show config's `stitch` block."""
    block = config.get("stitch")
    if not isinstance(block, dict):
        raise StitchConfigError(
            "show config has no `stitch` block -- add one to declare the "
            "show's segment structure (see shows/README.md)"
        )

    raw_segments = block.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise StitchConfigError("`stitch.segments` must be a non-empty list")

    problems: list[str] = []
    segments: list[Segment] = []
    seen: set[str] = set()

    for index, raw in enumerate(raw_segments):
        where = f"segments[{index}]"
        if not isinstance(raw, dict):
            problems.append(f"  {where}: not an object")
            continue

        slot_id = raw.get("id")
        if not isinstance(slot_id, str) or not slot_id.strip():
            problems.append(f"  {where}: missing a non-empty `id`")
            slot_id = where
        else:
            where = f"segments[{index}] ({slot_id})"
            if slot_id in seen:
                problems.append(f"  {where}: duplicate id")
            seen.add(slot_id)

        source = raw.get("source")
        if source not in ("asset", "episode"):
            problems.append(
                f"  {where}: source is {source!r}, expected 'asset' or 'episode'"
            )
            source = "episode"

        file_ref = raw.get("file")
        if source == "asset" and not file_ref:
            problems.append(f"  {where}: an asset slot needs a `file` path")

        pattern = None
        raw_match = raw.get("match")
        if raw_match is not None:
            try:
                pattern = re.compile(raw_match, re.IGNORECASE)
            except re.error as exc:
                problems.append(f"  {where}: `match` is not a valid regex ({exc})")

        fades = {}
        for key, field in (("fadeInMs", "fade_in_ms"), ("fadeOutMs", "fade_out_ms")):
            value = raw.get(key, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                problems.append(f"  {where}: `{key}` must be a non-negative integer")
                value = 0
            fades[field] = value

        required = raw.get("required", True)
        if not isinstance(required, bool):
            problems.append(f"  {where}: `required` must be true or false")
            required = True

        segments.append(
            Segment(
                id=slot_id,
                source=source,
                file=file_ref,
                match=pattern,
                required=required,
                **fades,
            )
        )

    encode = block.get("encode") or {}
    bitrate = encode.get("bitrate")
    if bitrate is not None and not isinstance(bitrate, str):
        problems.append("  encode.bitrate must be a string like \"192k\", or null")
        bitrate = None

    sample_rate = encode.get("sampleRate")
    if sample_rate is not None and (
        not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0
    ):
        problems.append("  encode.sampleRate must be a positive integer like 44100, or null")
        sample_rate = None

    output = block.get("output", DEFAULT_OUTPUT_TEMPLATE)
    if not isinstance(output, str) or not output.strip():
        problems.append("  stitch.output must be a filename template string")
        output = DEFAULT_OUTPUT_TEMPLATE
    else:
        try:
            output.format(episode="x", show="y")
        except (KeyError, IndexError) as exc:
            problems.append(
                f"  stitch.output has an unknown placeholder {exc}; "
                "only {episode} and {show} are available"
            )
            output = DEFAULT_OUTPUT_TEMPLATE

    if problems:
        raise StitchConfigError("Invalid `stitch` block:\n" + "\n".join(problems))

    return StitchSpec(
        segments=tuple(segments),
        bitrate=bitrate,
        sample_rate=sample_rate,
        output=output,
    )


def episode_dirs(
    config: dict, show_slug: str, episode_slug: str, repo_root: Path = REPO_ROOT
) -> tuple[Path, Path]:
    """(episode_dir, audio_dir) for one episode.

    Reads the same `episodes.localPath` and `episodes.subdirs.audio` keys that
    `scripts/episode-init.py` writes. `scripts/ingest_scan.py` imports this
    rather than reimplementing it -- two copies of this path math is how the
    downloader and the stitcher would quietly stop agreeing on where an
    episode lives.

    An absolute `localPath` is honoured as-is: that is the seam for moving a
    show's episodes off the repo without a code change.
    """
    episodes = config.get("episodes") or {}
    local_path = episodes.get("localPath") or f"shows/{show_slug}/episodes"
    audio_subdir = (episodes.get("subdirs") or {}).get("audio", "audio")

    root = Path(local_path)
    if not root.is_absolute():
        root = repo_root / root

    episode_dir = root / episode_slug
    return episode_dir, episode_dir / audio_subdir


def episode_paths(
    config: dict, spec: StitchSpec, show_slug: str, episode_slug: str,
    repo_root: Path = REPO_ROOT,
) -> EpisodePaths:
    """Where an episode's working files and its stitched deliverable live.

    Everything for an episode lands under the show folder, so the output is
    derived rather than passed in.
    """
    episode_dir, audio_dir = episode_dirs(config, show_slug, episode_slug, repo_root)
    filename = spec.output.format(episode=episode_slug, show=show_slug)
    return EpisodePaths(
        episode_dir=episode_dir, audio_dir=audio_dir, out_path=audio_dir / filename
    )


def load_show_config(slug: str, repo_root: Path = REPO_ROOT) -> tuple[dict, Path]:
    """Read `shows/<slug>/config.json`. brand.json is deliberately not required."""
    show_dir = repo_root / "shows" / slug
    config_path = show_dir / "config.json"
    if not config_path.exists():
        available = sorted(
            p.name for p in (repo_root / "shows").iterdir()
            if p.is_dir() and (p / "config.json").exists()
        ) if (repo_root / "shows").exists() else []
        sys.exit(
            f"No show config at {config_path}\n"
            f"Shows with a config: {', '.join(available) or '(none)'}"
        )
    try:
        return json.loads(config_path.read_text()), show_dir
    except json.JSONDecodeError as exc:
        sys.exit(f"{config_path} is not valid JSON: {exc}")


# --- slot resolution ---------------------------------------------------


def resolve_slots(
    spec: StitchSpec,
    show_dir: Path,
    candidates,
    overrides: dict,
    exists=None,
) -> list[ResolvedSegment]:
    """Map the supplied files onto the show's slots, in declared order.

    Precedence per slot: an explicit `--slot` override, then the slot's
    `match` pattern against the candidates, then an asset slot's `file`.
    """
    if exists is None:
        def exists(path):
            return Path(path).exists()

    candidate_paths = [Path(c) for c in candidates]
    by_id = {segment.id: segment for segment in spec.segments}

    problems: list[str] = []
    for slot_id in overrides:
        if slot_id not in by_id:
            problems.append(
                f"  --slot {slot_id}=... names no slot in this show; "
                f"slots are: {', '.join(by_id)}"
            )

    # Which slots does each candidate satisfy? Overridden slots still record
    # their claim, so that a file the pattern *would* have picked reads as
    # superseded by an explicit --slot rather than as an orphan.
    claims: dict[Path, list[str]] = {
        path: [
            segment.id for segment in spec.segments
            if segment.match is not None and segment.match.search(path.name)
        ]
        for path in candidate_paths
    }

    # A file claimed by two live slots is as ambiguous as a slot claimed by two
    # files, and just as unsafe to guess -- without this check both slots
    # silently resolve to the same file.
    for path in candidate_paths:
        live = [slot_id for slot_id in claims[path] if slot_id not in overrides]
        if len(live) > 1:
            problems.append(
                f"  {path.name}: matched by more than one slot "
                f"({', '.join(live)}); tighten the patterns or use --slot"
            )

    consumed: set[Path] = set()
    resolved: list[ResolvedSegment] = []

    for segment in spec.segments:
        path = None

        if segment.id in overrides:
            path = Path(overrides[segment.id])
        elif segment.match is not None:
            hits = [
                p for p in candidate_paths
                if segment.id in claims[p]
                and not any(other in overrides for other in claims[p])
            ]
            if len(hits) == 1:
                path = hits[0]
            elif len(hits) > 1:
                problems.append(
                    f"  slot '{segment.id}': {len(hits)} files matched "
                    f"/{segment.match.pattern}/ -> {[p.name for p in hits]}; "
                    f"pin one with --slot {segment.id}=<path>"
                )
                continue
            elif segment.source == "asset":
                path = show_dir / segment.file
            elif segment.required:
                problems.append(
                    f"  slot '{segment.id}': nothing matched "
                    f"/{segment.match.pattern}/; supply it with "
                    f"--slot {segment.id}=<path>"
                )
                continue
            else:
                continue  # optional and absent -- legitimately dropped
        elif segment.source == "asset":
            path = show_dir / segment.file
        elif segment.required:
            problems.append(
                f"  slot '{segment.id}': no `match` pattern in the show config "
                f"and no override; supply it with --slot {segment.id}=<path>"
            )
            continue
        else:
            continue

        if path is None:
            continue
        if not exists(path):
            problems.append(f"  slot '{segment.id}': file does not exist -> {path}")
            continue

        consumed.add(path)
        resolved.append(
            ResolvedSegment(
                id=segment.id,
                path=path,
                fade_in_ms=segment.fade_in_ms,
                fade_out_ms=segment.fade_out_ms,
            )
        )

    for path in candidate_paths:
        # Any claim at all means this file is accounted for: it was used, it
        # lost to an explicit --slot, or it is part of an ambiguity already
        # reported above. Only a file no slot wanted is an orphan.
        if path in consumed or claims[path]:
            continue
        problems.append(
            f"  {path.name}: matched no slot; remove it from the input "
            f"folder or assign it with --slot <id>={path}"
        )

    if problems:
        raise StitchResolutionError(
            "Could not map the supplied audio onto this show's slots:\n"
            + "\n".join(problems)
            + f"\nSlots (playback order): {', '.join(by_id)}"
        )

    return resolved


def scan_candidates(folder: Path, exclude: Path | None = None) -> list[Path]:
    """Audio files directly inside `folder`. Not recursive, deliberately.

    The agent points this at a folder it prepared; walking into subfolders
    would sweep up stray takes and turn a clean run into an ambiguity error.

    `exclude` drops the stitch's own output. It lands in the episode's audio
    directory alongside the parts it was made from, so without this a second
    run would see last run's deliverable as another candidate body -- for
    McCoshen & Ross the output `HAN2507MCROSS.mp3` matches the same `mcross`
    pattern as its own input.
    """
    if not folder.is_dir():
        sys.exit(f"--from is not a directory: {folder}")
    resolved_exclude = exclude.resolve() if exclude else None
    return sorted(
        p for p in folder.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in AUDIO_SUFFIXES
        and p.resolve() != resolved_exclude
    )


# --- encode planning ---------------------------------------------------


def plan_encoding(
    resolved: list[ResolvedSegment],
    probes: list[Probe],
    bitrate: str | None = None,
    out_suffix: str = ".mp3",
    sample_rate: int | None = None,
) -> EncodePlan:
    """Decide between a stream copy and a re-encode, and say why.

    Stream copy is only correct when nothing needs processing AND every input
    already agrees AND the container will take that codec unchanged. Both
    prior concatenations in this repo skip the last two checks and can emit a
    file with drifting timing.
    """
    suffix = out_suffix.lower()
    reasons: list[str] = []

    for segment in resolved:
        if segment.fade_in_ms or segment.fade_out_ms:
            reasons.append(f"fade requested on '{segment.id}'")

    codecs = {p.codec for p in probes}
    rates = {p.sample_rate for p in probes}
    channels = {p.channels for p in probes}

    if len(codecs) > 1:
        reasons.append(f"codec differs across inputs: {sorted(codecs)}")
    if len(rates) > 1:
        reasons.append(f"sample rate differs across inputs: {sorted(rates)}")
    if len(channels) > 1:
        reasons.append(f"channel count differs across inputs: {sorted(channels)}")

    acceptable = CONTAINER_CODECS.get(suffix)
    if acceptable is None:
        reasons.append(f"unrecognised output container '{suffix}'")
    elif not codecs <= acceptable:
        reasons.append(
            f"{sorted(codecs)} cannot be stream-copied into a {suffix} file"
        )

    target_rate = sample_rate or (max(rates) if rates else 48000)
    if sample_rate and rates - {sample_rate}:
        # The archive ships 44.1k while the Pro Tools masters are 48k; pinning
        # the rate keeps a stitched episode consistent with the back catalogue.
        reasons.append(f"resampling {sorted(rates)} -> {sample_rate} Hz per show config")
    target_channels = max(channels) if channels else 2
    total = sum(p.duration for p in probes)

    if not reasons:
        return EncodePlan(
            mode="copy",
            reasons=(),
            bitrate=None,
            sample_rate=target_rate,
            channels=target_channels,
            total_duration=total,
            encoder=None,
        )

    encoder = ENCODERS.get(suffix)
    if encoder is None:
        sys.exit(f"Don't know how to encode a {suffix} file. Use .mp3, .wav, .m4a or .flac.")

    resolved_bitrate = None
    if encoder not in ("flac", "pcm_s24le", "pcm_s24be"):
        if bitrate:
            resolved_bitrate = bitrate
        else:
            lossy = [
                p.bitrate for p in probes
                if p.bitrate and p.codec not in LOSSLESS_CODECS
            ]
            # A 24-bit WAV reports ~2300 kbps; carrying that into an MP3
            # target would be nonsense, so lossless inputs fall back to the
            # rate these shows already ship at.
            resolved_bitrate = (
                f"{snap_bitrate(max(lossy))}k" if lossy else DEFAULT_LOSSY_BITRATE
            )

    return EncodePlan(
        mode="reencode",
        reasons=tuple(reasons),
        bitrate=resolved_bitrate,
        sample_rate=target_rate,
        channels=target_channels,
        total_duration=total,
        encoder=encoder,
    )


def snap_bitrate(bits_per_second: int) -> int:
    """Nearest standard rate at or below the measured one, in kbps.

    Rounding down rather than to-nearest: a 192k source measuring 196k should
    come back out at 192k, not be promoted to 224k.
    """
    kbps = min(bits_per_second // 1000, MAX_LOSSY_BITRATE_KBPS)
    eligible = [rate for rate in STANDARD_BITRATES_KBPS if rate <= kbps]
    return eligible[-1] if eligible else STANDARD_BITRATES_KBPS[0]


def build_filter_graph(
    resolved: list[ResolvedSegment], probes: list[Probe], plan: EncodePlan
) -> str:
    """Per-input normalise + fade chains, then a single concat.

    Every input is run through `aformat` even when it already matches: the
    concat filter requires identical rate and layout on all inputs, and
    normalising unconditionally keeps the graph the same shape in every case.
    """
    layout = "mono" if plan.channels == 1 else "stereo"
    chains = []
    for index, (segment, probe) in enumerate(zip(resolved, probes)):
        filters = [f"aformat=sample_rates={plan.sample_rate}:channel_layouts={layout}"]
        if segment.fade_in_ms:
            seconds = min(segment.fade_in_ms / 1000, probe.duration)
            filters.append(f"afade=t=in:st=0.000:d={seconds:.3f}")
        if segment.fade_out_ms:
            seconds = min(segment.fade_out_ms / 1000, probe.duration)
            start = max(probe.duration - seconds, 0.0)
            filters.append(f"afade=t=out:st={start:.3f}:d={seconds:.3f}")
        chains.append(f"[{index}:a]{','.join(filters)}[a{index}]")

    labels = "".join(f"[a{i}]" for i in range(len(resolved)))
    chains.append(f"{labels}concat=n={len(resolved)}:v=0:a=1[out]")
    return ";".join(chains)


def concat_list_text(paths) -> str:
    """A concat-demuxer list. Single quotes inside a path are escaped.

    Both existing concat-list writers in this repo interpolate the path raw,
    which breaks on any filename containing an apostrophe -- and this archive
    has files like `Murv's cut.mp3`.
    """
    lines = []
    for path in paths:
        lines.append("file '" + str(path).replace("'", "'\\''") + "'")
    return "\n".join(lines) + "\n"


# --- ffmpeg I/O --------------------------------------------------------


def require_binaries() -> None:
    missing = [
        name for name in ("ffmpeg", "ffprobe")
        if subprocess.run(["which", name], capture_output=True).returncode != 0
    ]
    if missing:
        sys.exit(
            f"{' and '.join(missing)} not found on PATH. "
            "Install with: brew install ffmpeg"
        )


def probe(path: Path) -> Probe:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name,sample_rate,channels:format=duration,bit_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ffprobe could not read {path}:\n{result.stderr.strip()}")

    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    if not streams:
        sys.exit(f"{path} contains no audio stream.")
    stream, fmt = streams[0], payload.get("format", {})

    bitrate = fmt.get("bit_rate")
    return Probe(
        codec=stream.get("codec_name", "unknown"),
        sample_rate=int(stream.get("sample_rate", 0)),
        channels=int(stream.get("channels", 0)),
        duration=float(fmt.get("duration", 0.0)),
        bitrate=int(bitrate) if bitrate and bitrate.isdigit() else None,
    )


def build_command(resolved, probes, plan, out_path, list_path) -> list[str]:
    if plan.mode == "copy":
        return [
            "ffmpeg", "-y", "-v", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c", "copy", str(out_path),
        ]

    command = ["ffmpeg", "-y", "-v", "error"]
    for segment in resolved:
        command += ["-i", str(segment.path)]
    command += [
        "-filter_complex", build_filter_graph(resolved, probes, plan),
        "-map", "[out]", "-c:a", plan.encoder,
    ]
    if plan.bitrate:
        command += ["-b:a", plan.bitrate]
    command.append(str(out_path))
    return command


def run_stitch(resolved, probes, plan, out_path: Path, verbose: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stitch_") as tmp:
        list_path = Path(tmp) / "concat.txt"
        list_path.write_text(
            concat_list_text([s.path.resolve() for s in resolved])
        )
        command = build_command(resolved, probes, plan, out_path, list_path)
        if verbose:
            print("  " + " ".join(command))
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S
        )
    if result.returncode != 0:
        sys.exit(
            f"ffmpeg failed (exit {result.returncode}):\n"
            + (result.stderr.strip()[-1500:] or "(no stderr)")
        )


def verify_output(out_path: Path, expected: float) -> float:
    """Length check. A short file means a segment went missing."""
    measured = probe(out_path).duration
    drift = measured - expected
    print(f"\nWrote {out_path}")
    print(f"  expected {expected:7.1f}s   measured {measured:7.1f}s   drift {drift:+.1f}s")
    if abs(drift) > DURATION_MARGIN_S:
        print(
            f"\nWARNING: the output is {abs(drift):.1f}s "
            f"{'shorter' if drift < 0 else 'longer'} than its inputs, past the "
            f"{DURATION_MARGIN_S}s tolerance. A segment may be missing or "
            f"truncated. The file was kept at {out_path} for inspection.",
            file=sys.stderr,
        )
        sys.exit(1)
    return measured


# --- CLI ---------------------------------------------------------------


def parse_overrides(pairs) -> dict:
    overrides = {}
    for pair in pairs or []:
        if "=" not in pair:
            sys.exit(f"--slot expects <id>=<path>, got: {pair}")
        slot_id, path = pair.split("=", 1)
        if not slot_id or not path:
            sys.exit(f"--slot expects <id>=<path>, got: {pair}")
        overrides[slot_id] = path
    return overrides


def print_plan(resolved, probes, plan, out_path) -> None:
    print("Segments (playback order):")
    for segment, measured in zip(resolved, probes):
        fades = ""
        if segment.fade_in_ms or segment.fade_out_ms:
            fades = f"  fade {segment.fade_in_ms}/{segment.fade_out_ms} ms"
        print(f"  {segment.id:<12} {measured.duration:8.1f}s  {segment.path}{fades}")

    print(f"\nTotal: {plan.total_duration:.1f}s -> {out_path}")
    if plan.mode == "copy":
        print("Mode:  stream copy (no re-encode)")
    else:
        detail = f"{plan.encoder}" + (f" @ {plan.bitrate}" if plan.bitrate else "")
        print(f"Mode:  re-encode ({detail}, {plan.sample_rate} Hz, "
              f"{'mono' if plan.channels == 1 else 'stereo'})")
        for reason in plan.reasons:
            print(f"       - {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--show", required=True, help="Show slug under shows/")
    parser.add_argument("--episode", help="Episode slug; output lands in the show's episode folder")
    parser.add_argument("--from", dest="source", help="Folder of episode audio to match against")
    parser.add_argument("--slot", action="append", metavar="ID=PATH",
                        help="Pin one slot; repeatable. Overrides patterns and assets")
    parser.add_argument("--out", help="Write somewhere else instead; its extension picks the format")
    parser.add_argument("--dry-run", action="store_true", help="Report the plan, write nothing")
    parser.add_argument("--verbose", action="store_true", help="Echo the ffmpeg command")
    args = parser.parse_args()

    require_binaries()

    config, show_dir = load_show_config(args.show)
    try:
        spec = load_stitch_spec(config)
    except StitchConfigError as exc:
        sys.exit(f"{show_dir / 'config.json'}: {exc}")

    if args.episode and args.out:
        sys.exit(
            "--episode and --out are alternatives: --episode derives the path "
            "inside the show folder, --out overrides it. Pass one."
        )
    if not args.episode and not args.out and not args.dry_run:
        sys.exit("--episode is required (or --out to write elsewhere), unless --dry-run")

    paths = None
    if args.episode:
        paths = episode_paths(config, spec, args.show, args.episode)
        out_path = paths.out_path
    elif args.out:
        out_path = Path(args.out)
    else:
        out_path = None

    overrides = parse_overrides(args.slot)

    # An episode's pieces live in its own audio directory unless told otherwise.
    source = Path(args.source) if args.source else (paths.audio_dir if paths else None)

    if source is None:
        unpinned = [
            s.id for s in spec.segments
            if s.source == "episode" and s.id not in overrides and s.required
        ]
        if unpinned:
            sys.exit(
                "Nowhere to look for the episode's pieces. Pass --episode, or "
                "--from <folder>, or pin every episode slot with --slot. "
                f"Unpinned: {', '.join(unpinned)}"
            )
        candidates = []
    elif not source.is_dir() and paths is not None:
        sys.exit(
            f"No audio directory for episode '{args.episode}':\n  {source}\n"
            "Create it and put the episode's pieces there, or pass --from."
        )
    else:
        candidates = scan_candidates(source, exclude=out_path)

    try:
        resolved = resolve_slots(spec, show_dir, candidates, overrides)
    except StitchResolutionError as exc:
        sys.exit(str(exc))

    probes = [probe(segment.path) for segment in resolved]
    suffix = out_path.suffix.lower() if out_path else ".mp3"
    plan = plan_encoding(resolved, probes, spec.bitrate, suffix, spec.sample_rate)

    print(f"Show:  {config.get('name', args.show)}")
    print_plan(resolved, probes, plan, out_path or f"(dry run, assuming {suffix})")

    if args.dry_run:
        print("\n[DRY RUN] Nothing written.")
        return

    run_stitch(resolved, probes, plan, out_path, args.verbose)
    verify_output(out_path, plan.total_duration)


if __name__ == "__main__":
    main()
