# /new-episode

Take a new episode from the ingest server to a verified stitch plan.

Pipeline position: **[new-episode] → /stitch-audio → transcribe / ghost-import / youtube-export**

## Usage

```
/new-episode <show> [episode-key]
```

The user will usually say it in words — "there's a new episode of In Focus."
That is this command. Resolve the show name to a slug yourself:

| They say | Slug |
|---|---|
| In Focus, In Focus with Murv Seymour, Murv | `in-focus` |
| McCoshen & Ross, McCoshen and Ross, McRoss | `mccoshen-ross` |
| Wonder Cabinet | `wonder-cabinet` |
| Luminous | `luminous` |

If it matches nothing, list the directories under `shows/` and ask — don't guess.

## What to do

**1. Discover.**

```bash
python3 scripts/ingest_scan.py discover --show <slug>
```

This lists what is on the ingest server that isn't already a local episode
folder, newest first, with the artifacts present for each. Everything it knows
comes from the show's own `ingest` block in `shows/<slug>/config.json` — the
listing URL, which filenames count as an episode, and which artifacts to pull.

Read the annotations:

| Annotation | Meaning |
|---|---|
| `MISSING .wav` | Production hasn't delivered the body, or it has aged off the server. **Not pullable.** Don't offer it |
| `revision of X` | A `_REV<date>` recut. It supersedes `X` — prefer it, and say so |
| `local` | Already has an episode folder (only shown with `--all`) |

**2. Confirm which episode.** Do not assume the newest is the one they mean —
production often drops several between sessions, and a revision may sit below
its original in the list. Show the top few candidates with their dates and
artifacts, and ask. If they named a key explicitly, skip ahead.

Say the episode's title if you can get it — the `.txt` transcript's opening
lines or the `.srt` usually name the guest. That's what makes "6INF0123"
mean something to a human.

**3. Fetch.**

```bash
python3 scripts/ingest_scan.py fetch --show <slug> --episode <key> --dry-run
python3 scripts/ingest_scan.py fetch --show <slug> --episode <key>
```

Dry-run first and show the user the sizes — In Focus bodies are 600–800MB.
Files already on disk are skipped, so re-running after an interrupted pull is
safe and cheap.

**4. Dry-run the stitch, then stop.**

```bash
python3 scripts/stitch_audio.py --show <slug> --episode <key> --dry-run
```

Report the resolved slot order, the durations, and the encode plan. **Stop
here and hand back to the user.** Rendering is their call — the whole point of
stopping is that they get to see the body resolved correctly before spending
the encode. Tell them the exact command:

```bash
python3 scripts/stitch_audio.py --show <slug> --episode <key>
```

or that `/stitch-audio <slug> <key>` does the same.

## Failure surfaces

Both scripts fail loudly and report every problem at once — read the whole
message before acting.

| Message | Meaning |
|---|---|
| `Could not reach the ingest server` | The server is on the PBS Wisconsin network. Check VPN before anything else |
| `Required artifacts are not on the server yet` | Production is still delivering. Wait; don't substitute the `.mp3` |
| `No episode '<key>' on <url>` | Wrong key, or it's in a `<season> season/` archive subfolder rather than at the root |
| `file does not exist` from the stitcher | A show bookend asset is missing. `shows/README.md` has the rebuild recipes — including exact sample offsets for the McCoshen & Ross intro/outro. **Never substitute another file** |
| `N files matched` | An episode and its `_REV` are both staged. Pin one: `--slot program=<path>` |

## Notes

- **Everything lands under the show folder** — `shows/<slug>/episodes/<key>/`,
  with `audio/` and `captions/` subdirectories. Nothing goes to a scratch dir.
- **`.mp4` and production's own `.mp3` are on the server and are not pulled.**
  The `.wav` is the stitch source; re-encoding production's MP3 would be a
  second lossy generation.
- **Only `config.json` is version-controlled**; the audio is gitignored. A
  fresh clone knows the structure and will name exactly what's missing.
- **AirTable is not wired up in this repo.** The production base has entries
  for these episodes, but `AIRTABLE_API_KEY` is not registered in Infisical and
  exists only in the keychain, which agent processes cannot read. See CLAUDE.md
  for the enable steps and `.mcp.json.disabled` for the config. **Ask the user
  for episode titles and air dates** rather than trying a lookup — and don't
  trust `get-secret.sh`'s "not found" here, it misreports a locked item
  (the-lodge#707).
