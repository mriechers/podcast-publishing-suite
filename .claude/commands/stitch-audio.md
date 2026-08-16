# /stitch-audio

Assemble a show's segments into one deliverable audio file, before publishing.

Pipeline position: **ingest → [stitch-audio] → transcribe / ghost-import / youtube-export**

## Usage

```
/stitch-audio <show-slug> <episode-slug>
```

Examples the user might type:

- `/stitch-audio in-focus 6INF0123` — assemble episode 123
- `/stitch-audio mccoshen-ross HAN2507MCROSS`
- `/stitch-audio in-focus` — no episode; ask which one

Everything for an episode lives under the show folder, output included:

```
shows/<slug>/episodes/<episode-slug>/audio/
    <episode-slug>.wav     <- the body, from ingest
    <episode-slug>.mp3     <- what this writes
```

So the normal invocation names the episode and nothing else. The script reads
the pieces from that episode's audio directory and writes the deliverable back
beside them. Re-running is safe — the output is excluded from its own input
scan, so it never reads last run's file as a second candidate body.

## What to do

1. **Read the show's slots first** so you know what to look for:

   ```bash
   cat shows/<slug>/config.json
   ```

   The `stitch.segments` array is the show's structure, in playback order.
   Slots with `"source": "asset"` are the show's own files (standing intro,
   outro) and are already on disk. Slots with `"source": "episode"` are what
   the producer supplies this time, located by the slot's `match` pattern.

2. **Put the episode's pieces in its audio directory** if they aren't there
   yet — `shows/<slug>/episodes/<episode-slug>/audio/`. Download only the
   files that episode needs; see the ingest note below.

3. **Always dry-run before writing.** It resolves every slot, reports the
   encode decision and its reasons, and touches nothing:

   ```bash
   python3 scripts/stitch_audio.py --show <slug> --episode <ep> --dry-run
   ```

4. **Show the user the resolved order before running for real.** Order comes
   from the config, not the filesystem — but a mis-declared pattern can still
   pick the wrong file, and only a human knows which take is the good one.

5. **Run it:**

   ```bash
   python3 scripts/stitch_audio.py --show <slug> --episode <ep>
   ```

   Two escape hatches, for one-offs only: `--from <folder>` reads the pieces
   from somewhere else, `--out <file>` writes somewhere else. Prefer neither —
   the default keeps the episode self-contained.

## When resolution fails

The resolver reports every problem at once and refuses to guess — a stitch
with a segment silently dropped or reordered sounds fine for its first minute
and is wrong thereafter. Read the whole list, then:

| Message | Fix |
|---|---|
| `N files matched /pattern/` | Two takes or a `_REV` revision are both present. Pin the right one: `--slot program=<path>` |
| `nothing matched /pattern/` | The body isn't in the folder, or is named unusually. Pin it with `--slot` |
| `matched no slot` | A stray file is in the folder. Remove it, or assign it with `--slot` |
| `file does not exist` | A show asset (intro/outro) is missing from `shows/<slug>/assets/audio/`. Ask the user for it — do not substitute |
| `matched by more than one slot` | The show's patterns overlap. Fix `shows/<slug>/config.json`, don't work around it |

`--slot <id>=<path>` overrides anything — a pattern, or a show asset for a
one-off episode with a special intro. It supersedes the file the pattern would
have taken, so that file stops counting as a stray.

## Where the pieces come from

Production drops episodes on the public ingest server:

| Show | Ingest | Body file |
|---|---|---|
| In Focus | https://mmingest.pbswi.wisc.edu/InFocus/ | `6INF01NN.wav` (revisions carry `_REV<YYYYMMDD>`) |
| McCoshen & Ross | https://mmingest.pbswi.wisc.edu/HereNow/ | `HAN<season><week>MCROSS.wav` |

The Here & Now folder carries every HAN segment, not just the podcast — down-
load only the `MCROSS` files, or the resolver will report the rest as strays.
Take the `.wav`, not the `.mp3`: the bookends are 24-bit masters, so the stitch
re-encodes once at the end rather than twice.

## Notes

- **Never reorder segments yourself.** `sorted()` is not playback order; this
  repo has production manifests that record Wonder Cabinet's parts backwards
  because of exactly that (CLAUDE.md, `scripts/resolve_audio.py`).
- The script verifies the output's duration against the sum of its inputs and
  exits non-zero if they disagree by more than 2s. If that fires, something
  was dropped — report it, don't re-run and hope.
- A show's `config.json` is tracked, but its `assets/` are not. So a fresh
  clone knows the structure and fails cleanly naming the missing audio —
  `shows/README.md` has the rebuild recipes, including the exact sample
  offsets for the McCoshen & Ross bookends.
