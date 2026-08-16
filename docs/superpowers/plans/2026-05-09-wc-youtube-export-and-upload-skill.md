# WC YouTube Export & Upload Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/wc-youtube-export` skill that takes a Wonder Cabinet episode folder ready for video export and produces (a) a 1080p MP4 horizontal episode video, (b) a 1280×720 thumbnail PNG, and (c) an uploaded YouTube draft (with captions + chapters + description), all landing in the episode folder and the user's personal YouTube account.

**Architecture:** The skill is a markdown command at `.claude/commands/wc-youtube-export.md` that orchestrates four already-existing tools plus three new pieces: (1) a precondition validator, (2) a metadata composer that reads `manifest.json` + `chapters.md` + `keywords.md` and outputs YouTube-shaped title/description/tags, and (3) a captions uploader extension to the existing `youtube-upload.ts`. Sequential single-render queue — Mac CPU saturation makes parallel renders counterproductive (per E12 diagnostics). Upload proceeds independently of next render.

**Tech Stack:** Remotion 4 (video + still rendering), Node.js + TypeScript via `tsx`, googleapis (`youtube_v3` for video + thumbnail + captions), bash (skill orchestration), markbot (Slack notifications). YouTube API auth borrows the OAuth2 desktop-app flow already implemented in `audiogram-tools/src/automation/youtube-upload.ts`; PBSWI's `~/Developer/pbswi/pbswi-youtube-analytics/scripts/generate_youtube_token.py` serves as a Python reference for the token-generation step (we'll keep our flow in TypeScript to stay inside the audiogram-tools module).

**Prerequisite (this session, already shipped):**
- `audiogram-tools` PR #7 (dynamic episode duration + production CLI fixes) merged to main
- meta-repo bumps the submodule pointer to that merged commit

---

## Preconditions for invoking the skill

For an episode at `shows/wonder-cabinet/episodes/<slug>/`, the skill expects:

| File | Purpose | Source |
|---|---|---|
| `manifest.json` | episode metadata (number, guest, title, season, ghost.url) | `episode-init` + `ghost-import` |
| `audio/<guest>_full.mp3` (or stitched equivalent) | full audio for video render | PRX feed pull or local stitch |
| `images/<art>.jpg` | branded 3-panel collage art | `wc-episode-art` |
| `captions.srt` | timecoded captions with producer corrections applied | `wc-transcribe` + `wc-transcript-update` (now fixed in PR #71) |
| `chapters.md` | chapter timestamps (Section 3 = "YouTube Video Description Format") | `wc-transcribe` (chapter agent) |
| `keywords.md` | YouTube tags (one per line, no `#`) | `podcast-keywords` skill |

The skill must hard-fail if any of these are missing — list what's present + what's needed and stop.

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `.claude/commands/wc-youtube-export.md` | **create** | Skill orchestration markdown |
| `modules/audiogram-tools/src/automation/youtube-upload.ts` | **modify** | Add `uploadCaptions()` and `composeUploadOptions()` exports; extract OAuth setup into reusable export |
| `modules/audiogram-tools/src/automation/compose-metadata.ts` | **create** | Reads episode folder → returns `UploadOptions` (title, description, tags, etc.) |
| `modules/audiogram-tools/src/automation/render-thumbnail.ts` | **create** | Renders WC thumbnail PNG via Remotion `still` |
| `modules/audiogram-tools/src/Root.tsx` | **modify** | Add `WC-Thumbnail` Composition entry (1280×720) |
| `modules/audiogram-tools/src/components/Thumbnail.tsx` | **modify** | Accept WC template config (cabinet + art + WONDER CABINET wordmark, no waveform/spiral motion) |
| `scripts/wc-youtube-export-validate.sh` | **create** | Standalone bash precondition checker (skill calls this for hard-fail step) |
| `modules/audiogram-tools/.env.example` | **modify** | Document the new `YOUTUBE_DEFAULT_PRIVACY` and `YOUTUBE_DEFAULT_CATEGORY` env vars |
| `modules/audiogram-tools/.gitignore` | **modify** | Add `.youtube-token.json` and `.youtube-credentials.json` (verify it's already there) |

**Test files** — Remotion uses `npm run typecheck` rather than unit tests. Tests for the new TypeScript helpers live as small smoke scripts under `modules/audiogram-tools/scripts/test-*.ts` (run via `npx tsx`).

---

## Task 1: One-time YouTube OAuth credentials setup

**Files:**
- Modify: `modules/audiogram-tools/.env`
- Reference: `modules/audiogram-tools/.env.example`

This is a manual / interactive task — the user provisions Google Cloud credentials once. The skill should detect missing credentials and direct here.

- [ ] **Step 1: Create Google Cloud project for personal YouTube uploads**

In a browser:
1. Visit https://console.cloud.google.com
2. Create new project: `wc-youtube-uploader` (or reuse existing personal project)
3. Enable "YouTube Data API v3" via APIs & Services → Library
4. Create OAuth 2.0 credentials: APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
5. Application type: **Desktop app**, name: `WC Audiogram Uploader`
6. Download the JSON; copy `client_id` and `client_secret`

- [ ] **Step 2: Populate `.env` with the credentials**

```bash
cd modules/audiogram-tools
cp -n .env.example .env
# Edit .env, set:
#   YOUTUBE_CLIENT_ID=<from step 1>
#   YOUTUBE_CLIENT_SECRET=<from step 1>
#   YOUTUBE_REDIRECT_URI=http://localhost:3000/oauth2callback   (default is fine)
```

- [ ] **Step 3: Trigger first-run authorization**

```bash
cd modules/audiogram-tools
npx tsx src/automation/youtube-upload.ts --auth-only
```

Expected: a browser window opens, user signs into the **personal** Google account, grants `youtube.upload` scope, redirects to `localhost:3000/oauth2callback`. Token written to `.youtube-token.json` (gitignored).

If the script doesn't currently support `--auth-only`, Task 4 adds it.

- [ ] **Step 4: Verify token works**

```bash
cd modules/audiogram-tools
npx tsx -e "import { google } from 'googleapis'; import { getAuthenticatedClient } from './src/automation/youtube-upload'; (async () => { const auth = await getAuthenticatedClient(); const yt = google.youtube({ version: 'v3', auth }); const me = await yt.channels.list({ part: ['snippet'], mine: true }); console.log('Authed as:', me.data.items?.[0]?.snippet?.title); })();"
```

Expected: prints the personal YouTube channel name. If auth failed, re-run Step 3.

- [ ] **Step 5: Commit `.env.example` updates if any new vars were added later**

(No commit yet — `.env` is gitignored.)

---

## Task 2: Add WC-Thumbnail composition

**Files:**
- Modify: `modules/audiogram-tools/src/components/Thumbnail.tsx`
- Modify: `modules/audiogram-tools/src/Root.tsx`

The existing `Thumbnail` component handles a generic show layout. We need a WC-specific variant that mirrors the WC-Horizontal video frame (cabinet + art + WONDER/CABINET wordmark + brand-green background) but at 1280×720 (YouTube thumbnail standard) and as a static frame (no animation).

- [ ] **Step 1: Read the current Thumbnail component**

```bash
cat modules/audiogram-tools/src/components/Thumbnail.tsx
```

Note: it currently accepts `guestName`, `episodeTitle`, `episodeNumber`, `showLogo`, `backgroundImage`. It's used by the `SunSalutation-Thumb` composition.

- [ ] **Step 2: Add a WC-aware code path to Thumbnail.tsx**

Add a new prop `templateConfig?: OrientationConfig` (same type as ShowTemplate). When provided, render the WC layered stack (solid bg + spiral at static rotation 0 + cabinet frame + flanking title) at the thumbnail dimensions instead of the generic background+text layout.

```tsx
import { OrientationConfig } from "../template/types";
import { SolidBackground } from "../template/layers/SolidBackground";
import { GalaxySpiral } from "../template/layers/GalaxySpiral";
import { CabinetFrame } from "../template/layers/CabinetFrame";
import { TitleImage } from "../template/layers/TitleImage";

interface ThumbnailProps {
  // ... existing props ...
  templateConfig?: OrientationConfig;
  episodeArtSrc?: string;
}

export const Thumbnail: React.FC<ThumbnailProps> = (props) => {
  if (props.templateConfig) {
    return (
      <AbsoluteFill>
        {props.templateConfig.layers.map((layer, i) => {
          switch (layer.type) {
            case "solid": return <SolidBackground key={i} color={layer.color} grain={layer.grain} />;
            case "spiral": return <GalaxySpiral key={i} asset={layer.asset} rotationSpeed={0} opacity={layer.opacity} />;
            case "cabinet-frame": return <CabinetFrame key={i} asset={layer.asset} artClip={layer.artClip} episodeArtSrc={props.episodeArtSrc} />;
            case "title-image": return <TitleImage key={i} asset={layer.asset} layout={layer.layout} leftAsset={layer.leftAsset} rightAsset={layer.rightAsset} />;
          }
        })}
      </AbsoluteFill>
    );
  }
  // ... existing generic layout below ...
};
```

- [ ] **Step 3: Register `WC-Thumbnail` composition in Root.tsx**

Insert after the `WC-Vertical` composition:

```tsx
<Composition
  id="WC-Thumbnail"
  component={Thumbnail}
  schema={z.object({
    templateConfig: OrientationSchema,
    episodeArtSrc: z.string().optional(),
  })}
  durationInFrames={1}
  fps={30}
  width={1280}
  height={720}
  defaultProps={{
    templateConfig: { ...wcHorizontalConfig, width: 1280, height: 720 },
    episodeArtSrc: "",
  }}
/>
```

- [ ] **Step 4: Verify with a still render**

```bash
cd modules/audiogram-tools
npx remotion still WC-Thumbnail /tmp/wc-thumb-test.png \
  --props='{"episodeArtSrc":"WC_S01_12_Henderson.jpg"}'
```

Expected: a 1280×720 PNG showing the cabinet with Henderson art clipped inside, brand green background, WONDER CABINET wordmarks flanking. Open and visually verify.

- [ ] **Step 5: Typecheck + commit**

```bash
cd modules/audiogram-tools
npx tsc --noEmit
git add src/components/Thumbnail.tsx src/Root.tsx
git commit -m "feat: add WC-Thumbnail composition for YouTube thumbnail rendering"
```

---

## Task 3: Build `render-thumbnail.ts` CLI

**Files:**
- Create: `modules/audiogram-tools/src/automation/render-thumbnail.ts`

A small CLI that wraps the WC-Thumbnail composition for invocation from the skill — handles the same art-copy-into-public dance as `render-trigger.ts`.

- [ ] **Step 1: Create render-thumbnail.ts**

```typescript
import fs from "fs";
import os from "os";
import path from "path";
import { spawn } from "child_process";

interface ThumbnailOptions {
  artPath: string;
  outputPath: string;
}

function parseArgs(): ThumbnailOptions {
  const args = process.argv.slice(2);
  let artPath = "";
  let outputPath = "";
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--art") artPath = args[++i];
    else if (args[i] === "--output") outputPath = args[++i];
  }
  if (!artPath || !outputPath) {
    console.error("Usage: render-thumbnail.ts --art <path> --output <path>");
    process.exit(1);
  }
  return { artPath, outputPath };
}

async function main() {
  const { artPath, outputPath } = parseArgs();

  const resolvedArt = path.resolve(artPath);
  if (!fs.existsSync(resolvedArt)) {
    throw new Error(`Art file not found: ${resolvedArt}`);
  }

  const publicDir = path.join(__dirname, "../../public");
  if (!fs.existsSync(publicDir)) fs.mkdirSync(publicDir, { recursive: true });

  const artFilename = `thumbnail-art-${Date.now()}${path.extname(artPath)}`;
  const artInPublic = path.join(publicDir, artFilename);
  fs.copyFileSync(resolvedArt, artInPublic);

  const propsFile = path.join(os.tmpdir(), `thumb-props-${Date.now()}.json`);
  fs.writeFileSync(propsFile, JSON.stringify({ episodeArtSrc: artFilename }));

  const cleanup = () => {
    try { fs.unlinkSync(propsFile); } catch {}
    try { fs.unlinkSync(artInPublic); } catch {}
  };

  await new Promise<void>((resolve, reject) => {
    const render = spawn("npx", [
      "remotion", "still", "WC-Thumbnail",
      path.resolve(outputPath),
      `--props=${propsFile}`,
    ], { stdio: "inherit" });
    render.on("close", (code) => {
      cleanup();
      if (code === 0) resolve();
      else reject(new Error(`Thumbnail render failed: ${code}`));
    });
    render.on("error", (err) => { cleanup(); reject(err); });
  });

  console.log(`✓ Thumbnail: ${outputPath}`);
}

main().catch((err) => { console.error(err); process.exit(1); });
```

- [ ] **Step 2: Verify**

```bash
cd modules/audiogram-tools
npx tsx src/automation/render-thumbnail.ts \
  --art "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/images/WC_S01_12_Henderson.jpg" \
  --output "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/youtube-thumbnail.png"
```

Expected: 1280×720 PNG written to the episode folder. Visually inspect.

- [ ] **Step 3: Typecheck + commit**

```bash
cd modules/audiogram-tools
npx tsc --noEmit
git add src/automation/render-thumbnail.ts
git commit -m "feat: add render-thumbnail.ts CLI for WC YouTube thumbnails"
```

---

## Task 4: Refactor youtube-upload.ts — export auth client, add `--auth-only`, add captions upload

**Files:**
- Modify: `modules/audiogram-tools/src/automation/youtube-upload.ts`

Three additions: export `getAuthenticatedClient` so other modules can use it, support `--auth-only` flag for first-time setup (Task 1), and add a `uploadCaptions()` function for uploading SRT alongside the video.

- [ ] **Step 1: Export `getAuthenticatedClient`**

In `youtube-upload.ts`, change:
```typescript
async function getAuthenticatedClient() { ... }
```
to:
```typescript
export async function getAuthenticatedClient() { ... }
```

- [ ] **Step 2: Add `uploadCaptions()` function**

Add after `uploadVideo()`:

```typescript
export async function uploadCaptions(opts: {
  videoId: string;
  srtPath: string;
  language?: string;  // BCP-47 (e.g. "en")
  name?: string;       // visible track name
}): Promise<string> {
  const { videoId, srtPath, language = "en", name = "English (auto-generated by WC pipeline)" } = opts;
  if (!fs.existsSync(srtPath)) throw new Error(`Caption file not found: ${srtPath}`);

  const auth = await getAuthenticatedClient();
  const youtube = google.youtube({ version: "v3", auth });

  console.log(`\nUploading captions: ${path.basename(srtPath)}...`);
  const response = await youtube.captions.insert({
    part: ["snippet"],
    requestBody: {
      snippet: {
        videoId,
        language,
        name,
        isDraft: false,
      },
    },
    media: {
      mimeType: "application/octet-stream",
      body: fs.createReadStream(srtPath),
    },
  });

  const captionId = response.data.id!;
  console.log(`✓ Captions uploaded: ${captionId}`);
  return captionId;
}
```

- [ ] **Step 3: Add `--auth-only` flag handling**

Modify the `main()` function (currently invoked when run as a script) to check for `--auth-only`:

```typescript
async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--auth-only")) {
    await getAuthenticatedClient();
    console.log("✓ Authentication complete. Token saved to .youtube-token.json");
    return;
  }
  // ... existing main logic ...
}
```

- [ ] **Step 4: Typecheck + commit**

```bash
cd modules/audiogram-tools
npx tsc --noEmit
git add src/automation/youtube-upload.ts
git commit -m "feat: youtube-upload exports auth + supports captions and --auth-only"
```

---

## Task 5: Build `compose-metadata.ts` — episode folder → YouTube UploadOptions

**Files:**
- Create: `modules/audiogram-tools/src/automation/compose-metadata.ts`

Reads `manifest.json`, `chapters.md`, `keywords.md`, optional `formatted_transcript.md` excerpt, and the show config; returns a single `UploadOptions` object ready to feed into `uploadVideo()`.

- [ ] **Step 1: Create compose-metadata.ts**

```typescript
import fs from "fs";
import path from "path";

export interface ComposedMetadata {
  title: string;
  description: string;
  tags: string[];
  categoryId: string;
  privacyStatus: "private" | "unlisted" | "public";
  thumbnailPath?: string;
}

interface ComposeOpts {
  episodeDir: string;        // shows/wonder-cabinet/episodes/<slug>/
  videoPath: string;
  thumbnailPath?: string;
  privacyStatus?: ComposedMetadata["privacyStatus"];
}

export function composeMetadata(opts: ComposeOpts): ComposedMetadata {
  const { episodeDir, thumbnailPath, privacyStatus = "private" } = opts;

  // 1. Read manifest.json
  const manifestPath = path.join(episodeDir, "manifest.json");
  if (!fs.existsSync(manifestPath)) throw new Error(`No manifest at ${manifestPath}`);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));

  const epNum = manifest.episodeNumber;
  const guest = manifest.guestName;
  const ghostUrl: string | undefined = manifest.ghost?.url;

  // 2. Title — pull from manifest if present, else compose
  // Convention: "<Guest>: <Episode title>" or fall back to manifest.title
  const episodeTitle = manifest.title ?? manifest.ghost?.title ?? "";
  const title = episodeTitle ? `${guest}: ${episodeTitle}` : `${guest} — Wonder Cabinet E${epNum}`;

  // 3. Description — assemble from chapters.md + ghost link + boilerplate
  const chaptersText = extractYouTubeChapters(path.join(episodeDir, "chapters.md"));
  const description = composeDescription({ guest, episodeTitle, chaptersText, ghostUrl });

  // 4. Tags — from keywords.md (one per line, strip blanks/comments)
  const tags = readKeywords(path.join(episodeDir, "keywords.md"));

  return {
    title: title.slice(0, 100),       // YouTube title hard limit
    description: description.slice(0, 5000), // YouTube description hard limit
    tags: tags.slice(0, 30),          // YouTube allows ~500 chars total in tags
    categoryId: "27",                 // Education
    privacyStatus,
    thumbnailPath,
  };
}

function extractYouTubeChapters(chaptersMdPath: string): string {
  if (!fs.existsSync(chaptersMdPath)) return "";
  const text = fs.readFileSync(chaptersMdPath, "utf-8");
  // Find the "## 3. YouTube Video Description Format" code block
  const match = text.match(/##\s*3\.\s*YouTube[^\n]*\n+```[^\n]*\n([\s\S]*?)\n```/);
  if (!match) return "";
  return match[1].trim();
}

function readKeywords(keywordsMdPath: string): string[] {
  if (!fs.existsSync(keywordsMdPath)) return [];
  return fs.readFileSync(keywordsMdPath, "utf-8")
    .split("\n")
    .map(l => l.trim())
    .filter(l => l && !l.startsWith("#") && !l.startsWith("-"))
    .map(l => l.replace(/^[•*]\s*/, ""));
}

function composeDescription(opts: {
  guest: string;
  episodeTitle: string;
  chaptersText: string;
  ghostUrl?: string;
}): string {
  const { guest, episodeTitle, chaptersText, ghostUrl } = opts;
  const parts: string[] = [];
  parts.push(`${guest} on Wonder Cabinet — ${episodeTitle}`);
  parts.push("");
  if (chaptersText) {
    parts.push("Chapters:");
    parts.push(chaptersText);
    parts.push("");
  }
  if (ghostUrl) {
    parts.push(`Full episode notes & transcript: ${ghostUrl}`);
    parts.push("");
  }
  parts.push("Subscribe wherever you get your podcasts. Newsletter: https://wondercabinetproductions.com");
  return parts.join("\n");
}

// CLI entry — print composed metadata to stdout for inspection
if (require.main === module) {
  const epDir = process.argv[2];
  if (!epDir) {
    console.error("Usage: compose-metadata.ts <episode-dir>");
    process.exit(1);
  }
  const md = composeMetadata({ episodeDir: epDir, videoPath: "" });
  console.log(JSON.stringify(md, null, 2));
}
```

- [ ] **Step 2: Verify on E12 Henderson**

```bash
cd modules/audiogram-tools
npx tsx src/automation/compose-metadata.ts \
  "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson"
```

Expected: JSON output with `title`, `description` (containing chapters + Ghost URL), `tags` array, `categoryId: "27"`, `privacyStatus: "private"`. Inspect for sane content.

- [ ] **Step 3: Edge case — when keywords.md is missing**

```bash
cd modules/audiogram-tools
# E12 currently has keywords.md? Check:
ls "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/keywords.md" 2>&1
```

If missing, the composer returns `tags: []` rather than failing — verify by inspection.

- [ ] **Step 4: Typecheck + commit**

```bash
cd modules/audiogram-tools
npx tsc --noEmit
git add src/automation/compose-metadata.ts
git commit -m "feat: compose-metadata reads episode folder → YouTube UploadOptions"
```

---

## Task 6: Build `wc-export-and-upload.ts` — orchestrator the skill calls

**Files:**
- Create: `modules/audiogram-tools/src/automation/wc-export-and-upload.ts`

End-to-end orchestrator. The skill (Task 7) is a thin wrapper around this script — keeps logic in TypeScript where it can be typechecked rather than scattered in bash.

- [ ] **Step 1: Create wc-export-and-upload.ts**

```typescript
import fs from "fs";
import path from "path";
import { spawn } from "child_process";
import { uploadVideo, uploadCaptions } from "./youtube-upload";
import { composeMetadata } from "./compose-metadata";
import "dotenv/config";

interface RunOptions {
  episodeDir: string;
  privacyStatus?: "private" | "unlisted" | "public";
  skipRender?: boolean;     // reuse existing video if present
  skipUpload?: boolean;     // dry run
}

async function runCommand(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, { stdio: "inherit" });
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${cmd} exited ${code}`));
    });
    proc.on("error", reject);
  });
}

function findFirst(dir: string, predicate: (name: string) => boolean): string | null {
  if (!fs.existsSync(dir)) return null;
  for (const name of fs.readdirSync(dir)) {
    if (predicate(name)) return path.join(dir, name);
  }
  return null;
}

async function main() {
  const args = process.argv.slice(2);
  const epDir = path.resolve(args[0]);
  const skipRender = args.includes("--skip-render");
  const skipUpload = args.includes("--skip-upload");
  const privacyArg = args.find((a) => a.startsWith("--privacy="));
  const privacyStatus = (privacyArg?.split("=")[1] || "private") as RunOptions["privacyStatus"];

  if (!epDir || !fs.existsSync(epDir)) {
    console.error("Usage: wc-export-and-upload.ts <episode-dir> [--skip-render] [--skip-upload] [--privacy=private|unlisted|public]");
    process.exit(1);
  }

  // 1. Resolve assets
  const audioPath = findFirst(path.join(epDir, "audio"), (n) => /_full\.mp3$/i.test(n));
  const artPath = findFirst(path.join(epDir, "images"), (n) => /^WC_S01_\d+_.+\.jpg$/.test(n));
  const captionsPath = path.join(epDir, "captions.srt");
  const manifestPath = path.join(epDir, "manifest.json");

  for (const [label, p] of [
    ["audio", audioPath], ["art", artPath], ["captions", captionsPath], ["manifest", manifestPath]
  ] as const) {
    if (!p || !fs.existsSync(p)) throw new Error(`Missing ${label}: ${p ?? "<not found>"}`);
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath!, "utf-8"));
  const slug = manifest.slug;
  const guest = manifest.guestName;
  const epNum = manifest.episodeNumber;

  // 2. Output paths inside the episode folder
  const audiogramDir = path.join(epDir, "audiogram");
  fs.mkdirSync(audiogramDir, { recursive: true });
  const videoPath = path.join(audiogramDir, `${slug}_youtube.mp4`);
  const thumbnailPath = path.join(audiogramDir, `${slug}_thumbnail.png`);

  // 3. Render thumbnail (always re-render — it's cheap)
  console.log("\n=== [1/4] Rendering thumbnail ===");
  await runCommand("npx", [
    "tsx", path.join(__dirname, "render-thumbnail.ts"),
    "--art", artPath!, "--output", thumbnailPath,
  ]);

  // 4. Render video (skippable)
  if (!skipRender || !fs.existsSync(videoPath)) {
    console.log("\n=== [2/4] Rendering full episode video (~80 min for 50 min audio) ===");
    await runCommand("npx", [
      "tsx", path.join(__dirname, "render-trigger.ts"),
      audioPath!, "--episode", "--show", "wonder-cabinet",
      "--art", artPath!, "--guest", guest,
      "--ep", String(epNum), "--title", manifest.title ?? "",
    ]);
    // render-trigger writes to OUTPUT_DIR with its own naming — move into our slot
    const outDir = process.env.OUTPUT_DIR || path.join(__dirname, "../../output");
    const rendered = findFirst(outDir, (n) => n.startsWith(`EP${epNum}_`) && n.endsWith(".mp4"));
    if (!rendered) throw new Error(`render-trigger output not found in ${outDir}`);
    fs.renameSync(rendered, videoPath);
  } else {
    console.log("\n=== [2/4] Reusing existing video (--skip-render) ===");
  }

  // 5. Compose metadata
  console.log("\n=== [3/4] Composing YouTube metadata ===");
  const metadata = composeMetadata({
    episodeDir: epDir, videoPath, thumbnailPath, privacyStatus,
  });
  console.log(`  Title: ${metadata.title}`);
  console.log(`  Tags:  ${metadata.tags.length}`);
  console.log(`  Privacy: ${metadata.privacyStatus}`);

  if (skipUpload) {
    console.log("\n=== [4/4] Skipping upload (--skip-upload) ===");
    console.log(JSON.stringify(metadata, null, 2));
    return;
  }

  // 6. Upload video + thumbnail
  console.log("\n=== [4/4] Uploading to YouTube as draft ===");
  const result = await uploadVideo({
    videoPath, ...metadata,
  });

  // 7. Upload captions
  await uploadCaptions({ videoId: result.videoId, srtPath: captionsPath });

  // 8. Update manifest with YouTube draft URL
  manifest.youtube = {
    videoId: result.videoId,
    url: result.videoUrl,
    uploadedAt: new Date().toISOString(),
    privacyStatus: metadata.privacyStatus,
  };
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

  console.log(`\n✓ Done. Draft: ${result.videoUrl}`);
  console.log(`  manifest.json updated.`);
}

main().catch((err) => { console.error(err); process.exit(1); });
```

- [ ] **Step 2: Dry-run end-to-end on E12 (skip render — already exists, skip upload)**

```bash
cd modules/audiogram-tools
npx tsx src/automation/wc-export-and-upload.ts \
  "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson" \
  --skip-render --skip-upload
```

Expected: thumbnail rendered to `audiogram/WC_S01_12_Rebecca_Henderson_thumbnail.png`; metadata JSON printed; no YouTube call. Verify thumbnail visually + metadata content.

- [ ] **Step 3: Typecheck + commit**

```bash
cd modules/audiogram-tools
npx tsc --noEmit
git add src/automation/wc-export-and-upload.ts
git commit -m "feat: wc-export-and-upload orchestrator (thumbnail + render + upload + manifest)"
```

---

## Task 7: Write the `/wc-youtube-export` skill

**Files:**
- Create: `.claude/commands/wc-youtube-export.md` (in meta-repo)

The skill is a thin markdown wrapper. It validates preconditions, calls the orchestrator, and reports.

- [ ] **Step 1: Create the skill markdown**

```markdown
Export and upload a Wonder Cabinet episode to YouTube as a draft. Renders the horizontal video, generates a thumbnail, composes title/description/tags, and uploads everything via the YouTube Data API to the personal account configured in `modules/audiogram-tools/.env`.

**Episode argument:** $ARGUMENTS — either an episode slug (e.g. `WC_S01_12_Rebecca_Henderson`) or a full path to an episode folder.

## Step 1: Resolve episode folder

If $ARGUMENTS looks like a slug (starts with `WC_S01_`), resolve to:
`shows/wonder-cabinet/episodes/$ARGUMENTS/`

Otherwise treat as a path. Verify the directory exists; if not, list available episodes:
```bash
ls shows/wonder-cabinet/episodes/
```

## Step 2: Precondition check

Verify all required files exist in the episode folder. Hard-fail with a clear list if any are missing:

| File | Purpose | If missing, run |
|---|---|---|
| `manifest.json` | metadata source | `/episode-init` |
| `audio/*_full.mp3` | full audio | check PRX feed pull |
| `images/WC_S01_*.jpg` | collage art | `/wc-episode-art` |
| `captions.srt` | corrected captions | `/wc-transcript-update` |
| `chapters.md` | chapter timestamps | `/wc-transcribe` |
| `keywords.md` | YouTube tags | `/podcast-keywords` |

```bash
EP_DIR="shows/wonder-cabinet/episodes/<slug>"
for f in manifest.json captions.srt chapters.md keywords.md; do
  [ -f "$EP_DIR/$f" ] || echo "MISSING: $EP_DIR/$f"
done
[ -n "$(find "$EP_DIR/audio" -maxdepth 1 -name '*_full.mp3' -print -quit 2>/dev/null)" ] || echo "MISSING: full audio in $EP_DIR/audio/"
[ -n "$(find "$EP_DIR/images" -maxdepth 1 -name 'WC_S01_*.jpg' -print -quit 2>/dev/null)" ] || echo "MISSING: collage art in $EP_DIR/images/"
```

If any line prints `MISSING:`, STOP and report to user. Do not continue.

## Step 3: Verify YouTube credentials present

```bash
[ -f modules/audiogram-tools/.env ] || { echo "Set up YouTube credentials first — see docs/superpowers/plans/2026-05-09-wc-youtube-export-and-upload-skill.md Task 1"; exit 1; }
[ -f modules/audiogram-tools/.youtube-token.json ] || { echo "Run: cd modules/audiogram-tools && npx tsx src/automation/youtube-upload.ts --auth-only"; exit 1; }
```

## Step 4: Confirm with user

Show the user:
- Episode folder path
- Audio file + duration (run `ffprobe -v error -show_entries format=duration`)
- Estimated render time = audio_duration × 1.66 (per E12 diagnostics)
- Default privacy = `private` (uploads as draft)

Ask: "Proceed with render + upload? (yes/no, or specify privacy: private/unlisted/public)"

If user declines, stop. If user specifies privacy, pass through to next step.

## Step 5: Run the orchestrator

```bash
cd modules/audiogram-tools
OUTPUT_DIR="../../shows/wonder-cabinet/episodes/<slug>/audiogram" \
  npx tsx src/automation/wc-export-and-upload.ts \
    "../../shows/wonder-cabinet/episodes/<slug>" \
    --privacy=<chosen privacy>
```

Stream output to user as it runs. Render alone takes ~80 minutes for a typical 50-min episode; upload another ~15 minutes for a 5GB MP4.

If the user wants to do something else during the render, suggest running it in the background — `cd modules/audiogram-tools && nohup npx tsx ... &> /path/to/log.txt &` and they can come back.

## Step 6: Verify and report

After completion:
- Read `manifest.json` — should now have `youtube.url`
- Notify via markbot:
  ```bash
  cd modules/markbot && python -m markbot post --channel "#wonder-cabinet" --message "📺 E$EPNUM ($GUEST) uploaded to YouTube as $PRIVACY draft: $YOUTUBE_URL"
  ```
  (Use the existing markbot post command — ref CLAUDE.md for exact form.)
- Surface the YouTube draft URL to the user with a one-line summary.
```

- [ ] **Step 2: Wire the skill into the meta-repo**

```bash
cd "/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite"
# verify skill is recognized by listing it
ls -la .claude/commands/wc-youtube-export.md
```

(The skill is auto-discovered from `.claude/commands/`.)

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/wc-youtube-export.md
git commit -m "feat: add /wc-youtube-export skill"
```

---

## Task 8: End-to-end test on E12 Henderson

**Files:** None — this is verification.

E12 already has all preconditions present and the full video render exists. Use this as the smoke test.

- [ ] **Step 1: Run with --skip-render --skip-upload (sanity)**

```bash
cd /Volumes/Mark*/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/audiogram-tools
npx tsx src/automation/wc-export-and-upload.ts \
  "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson" \
  --skip-render --skip-upload
```

Expected: thumbnail rendered, metadata JSON printed. No upload attempted.

- [ ] **Step 2: Run with --skip-render only (real upload, but reuse existing video)**

```bash
npx tsx src/automation/wc-export-and-upload.ts \
  "../../shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson" \
  --skip-render --privacy=private
```

Expected: existing E12 video uploaded to YouTube as a private draft, thumbnail set, captions uploaded. Manifest updated with `youtube.url`. Should take ~15 minutes (upload-bound).

- [ ] **Step 3: Verify in browser**

Open the YouTube URL printed in the output. Confirm:
- Video plays correctly with audio
- Thumbnail visible (cabinet + Henderson art + WONDER CABINET wordmarks)
- Description shows the chapter timestamps + Ghost link
- Captions track present (will need a few minutes for YouTube to process the SRT)
- Status: Draft (private)
- Tags visible in video details

- [ ] **Step 4: Run via the skill**

```bash
# In Claude Code:
/wc-youtube-export WC_S01_12_Rebecca_Henderson
```

Expected: skill prompts for privacy choice, then orchestrates. Smoke test that the skill itself works (not just the underlying CLI).

---

## Open follow-ups (NOT in this plan)

These are explicit non-goals — file as separate work after this lands:

- **Vertical (9:16) version for Shorts/Reels** — needs Task 7-equivalent for `WC-Vertical` composition + separate skill
- **Auto-publish at scheduled time** — `youtube-upload.ts` already supports `scheduledStartTime`; surface in skill as `--schedule=<ISO datetime>`
- **Batch mode** — render multiple episodes back-to-back from a queue file
- **Resumable upload on failure** — current upload is single-shot; for unstable connections add retry with `googleapis` resumable upload media
- **Caption track translation** — auto-trigger YouTube's auto-translate after caption upload
- **Drive cleanup of old SRTs** — orthogonal to YouTube workflow but related; the wc-transcript-update skill could do this
- **Cost tracking** — log YouTube API quota costs per upload (each upload ~1600 units; 10K daily quota = ~6 episodes/day max)

## Self-review notes

- **Spec coverage:** Render ✓ (Task 6), thumbnail ✓ (Task 2-3), upload to YouTube ✓ (Task 4-6), borrows from PBSWI YouTube tooling ✓ (referenced in Tech Stack), personal YouTube account ✓ (Task 1)
- **Placeholder scan:** Each step has concrete code or commands; no "TBD" or "implement appropriate error handling" left
- **Type consistency:** `ComposedMetadata` (Task 5) feeds into `uploadVideo()` (existing in youtube-upload.ts) — fields align (title, description, tags, categoryId, privacyStatus, thumbnailPath). `getAuthenticatedClient` exported in Task 4 used in Task 1 verification — name matches.
