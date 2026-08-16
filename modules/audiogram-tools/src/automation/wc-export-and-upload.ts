/**
 * wc-export-and-upload.ts — End-to-end YouTube export orchestrator.
 *
 * Steps:
 *   1. Validate episode assets (audio, art, captions, manifest)
 *   2. Render thumbnail (always — it's fast)
 *   3. Render full episode video (skippable via --skip-render if file exists)
 *   4. Compose YouTube metadata (title, description, tags, privacy)
 *   5. Upload video + thumbnail to YouTube as a draft
 *   6. Upload SRT captions
 *   7. Write YouTube URL + video ID back to manifest.json
 *
 * Usage:
 *   npx tsx src/automation/wc-export-and-upload.ts <episode-dir> \
 *     [--skip-render] [--skip-upload] [--privacy=private|unlisted|public]
 *
 * The skill wrapper (Task 7) is a thin bash shim around this script so that
 * all logic lives here where TypeScript can typecheck it.
 */

import fs from "fs";
import path from "path";
import { spawn } from "child_process";
import { uploadVideo, uploadCaptions, getAuthenticatedClient } from "./youtube-upload";
import { composeMetadata } from "./compose-metadata";
import "dotenv/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PrivacyStatus = "private" | "unlisted" | "public";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Spawn a subprocess and inherit stdio. Resolves when exit code is 0,
 * rejects on non-zero exit or spawn error.
 */
function runCommand(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, { stdio: "inherit" });
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${cmd} ${args[0]} exited with code ${code}`));
    });
    proc.on("error", reject);
  });
}

/**
 * Return the first filename in `dir` that satisfies `predicate`, or null.
 * Returns null without throwing if the directory doesn't exist.
 */
function findFirst(dir: string, predicate: (name: string) => boolean): string | null {
  if (!fs.existsSync(dir)) return null;
  for (const name of fs.readdirSync(dir)) {
    if (predicate(name)) return path.join(dir, name);
  }
  return null;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  // --- Parse CLI args ---
  const rawArgs = process.argv.slice(2);
  const epDirArg = rawArgs.find((a) => !a.startsWith("--"));

  if (!epDirArg) {
    console.error(
      "Usage: wc-export-and-upload.ts <episode-dir> " +
      "[--skip-render] [--skip-upload] [--privacy=private|unlisted|public]"
    );
    process.exit(1);
  }

  const epDir = path.resolve(epDirArg);
  const skipRender = rawArgs.includes("--skip-render");
  const skipUpload = rawArgs.includes("--skip-upload");
  const privacyArg = rawArgs.find((a) => a.startsWith("--privacy="));
  const privacyStatus: PrivacyStatus =
    (privacyArg?.split("=")[1] as PrivacyStatus | undefined) ?? "private";

  if (!fs.existsSync(epDir)) {
    throw new Error(`Episode directory not found: ${epDir}`);
  }

  // --- Step 1: Resolve and validate required assets ---
  console.log("\n=== Validating episode assets ===");

  const audioPath = findFirst(
    path.join(epDir, "audio"),
    (n) => /_full\.mp3$/i.test(n)
  );
  const artPath = findFirst(
    path.join(epDir, "images"),
    (n) => /^WC_S01_\d+_.+\.jpg$/.test(n)
  );
  const captionsPath = path.join(epDir, "captions.srt");
  const manifestPath = path.join(epDir, "manifest.json");

  const checks: [string, string | null][] = [
    ["audio (*_full.mp3)", audioPath],
    ["art (WC_S01_*.jpg)", artPath],
    ["captions (captions.srt)", fs.existsSync(captionsPath) ? captionsPath : null],
    ["manifest (manifest.json)", fs.existsSync(manifestPath) ? manifestPath : null],
  ];

  let validationFailed = false;
  for (const [label, resolved] of checks) {
    if (!resolved) {
      console.error(`  MISSING ${label}`);
      validationFailed = true;
    } else {
      console.log(`  OK  ${label}: ${path.basename(resolved)}`);
    }
  }
  if (validationFailed) {
    throw new Error("One or more required episode assets are missing. Aborting.");
  }

  // Non-null assertions are safe: validation above would have thrown otherwise.
  const audio = audioPath!;
  const art = artPath!;

  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  const slug: string = manifest.slug;
  const epNum: number | string = manifest.episodeNumber;
  const guest: string = manifest.guestName;

  console.log(`  Slug: ${slug}  |  Episode: ${epNum}  |  Guest: ${guest}`);

  // --- Output paths (all inside episode folder) ---
  const audiogramDir = path.join(epDir, "audiogram");
  fs.mkdirSync(audiogramDir, { recursive: true });

  const videoPath = path.join(audiogramDir, `${slug}_youtube.mp4`);
  const thumbnailPath = path.join(audiogramDir, `${slug}_thumbnail.png`);

  // The __dirname for this file is src/automation/ inside audiogram-tools.
  const automationDir = __dirname;

  // --- Step 2: Render thumbnail (always — cheap, ~10s) ---
  console.log("\n=== [1/4] Rendering thumbnail ===");
  await runCommand("npx", [
    "tsx",
    path.join(automationDir, "render-thumbnail.ts"),
    "--art", art,
    "--output", thumbnailPath,
  ]);
  if (!fs.existsSync(thumbnailPath) || fs.statSync(thumbnailPath).size === 0) {
    throw new Error(
      `Thumbnail render reported success but file is missing or empty: ${thumbnailPath}`
    );
  }
  console.log(`  Thumbnail: ${thumbnailPath}`);

  // --- Step 3: Render full episode video ---
  const videoExists = fs.existsSync(videoPath) && fs.statSync(videoPath).size > 0;

  if (skipRender && videoExists) {
    console.log("\n=== [2/4] Reusing existing video (--skip-render) ===");
    console.log(`  ${videoPath}`);
  } else {
    if (skipRender && !videoExists) {
      console.log(
        "\n=== [2/4] --skip-render set but no existing video found; rendering anyway ==="
      );
    } else {
      console.log("\n=== [2/4] Rendering full episode video (~80 min for 50 min audio) ===");
    }

    // render-trigger.ts writes to OUTPUT_DIR (env) or ./output (default).
    // We override OUTPUT_DIR to the audiogram dir so the file lands there
    // directly — no rename dance needed.
    const env = {
      ...process.env,
      OUTPUT_DIR: audiogramDir,
    };

    // Snapshot pre-existing EP{n}_*.mp4 files before spawning so we can
    // identify the new render by diff rather than readdir order. Without this,
    // a stale file from a prior run could be picked up instead of today's.
    const preExistingEpFiles = new Set(
      fs.existsSync(audiogramDir)
        ? fs.readdirSync(audiogramDir).filter(
            (n) => n.startsWith(`EP${epNum}_`) && n.endsWith(".mp4")
          )
        : []
    );

    await new Promise<void>((resolve, reject) => {
      const proc = spawn(
        "npx",
        [
          "tsx",
          path.join(automationDir, "render-trigger.ts"),
          audio,
          "--episode",
          "--show", "wonder-cabinet",
          "--art", art,
          "--guest", guest,
          "--ep", String(epNum),
          "--title", manifest.title ?? "",
        ],
        { stdio: "inherit", env }
      );
      proc.on("close", (code) => {
        if (code === 0) resolve();
        else reject(new Error(`render-trigger exited with code ${code}`));
      });
      proc.on("error", reject);
    });

    // Diff against pre-render snapshot to find the file render-trigger just
    // produced. Using a set diff avoids the readdir-order ambiguity that could
    // cause a stale EP{n}_*.mp4 from a prior run to be picked up.
    const postRenderFiles = fs.readdirSync(audiogramDir).filter(
      (n) => n.startsWith(`EP${epNum}_`) && n.endsWith(".mp4")
    );
    const newFiles = postRenderFiles.filter((n) => !preExistingEpFiles.has(n));

    if (newFiles.length === 0) {
      throw new Error(
        `render-trigger output not found in ${audiogramDir}. ` +
        "Check OUTPUT_DIR is being respected by render-trigger."
      );
    }
    if (newFiles.length > 1) {
      throw new Error(
        `Multiple new render outputs found (ambiguous): ${newFiles.join(", ")}. ` +
        "Clean the audiogram folder and re-run."
      );
    }
    const rendered = path.join(audiogramDir, newFiles[0]);

    if (rendered !== videoPath) {
      fs.renameSync(rendered, videoPath);
    }
    console.log(`  Video: ${videoPath}`);
  }

  // --- Step 4: Compose YouTube metadata ---
  console.log("\n=== [3/4] Composing YouTube metadata ===");
  const metadata = composeMetadata({
    episodeDir: epDir,
    thumbnailPath,
    privacyStatus,
  });
  console.log(`  Title:   ${metadata.title}`);
  console.log(`  Tags:    ${metadata.tags.length} tag(s)`);
  console.log(`  Privacy: ${metadata.privacyStatus}`);

  if (skipUpload) {
    console.log("\n=== [4/4] Skipping upload (--skip-upload) ===");
    console.log(JSON.stringify(metadata, null, 2));
    return;
  }

  // --- Steps 5+6: Upload video (includes thumbnail) and captions ---
  console.log("\n=== [4/4] Uploading to YouTube as draft ===");
  // Pre-warm auth so any credential issues fail fast (before the upload starts)
  // AND so the same client is reused for both uploads — avoids the stale-closure
  // race in the token refresh handler when refresh happens during a long upload.
  const auth = await getAuthenticatedClient();
  const result = await uploadVideo({
    videoPath,
    auth,
    ...metadata,
  });

  await uploadCaptions({
    videoId: result.videoId,
    srtPath: captionsPath,
    auth,
  });

  // --- Step 7: Write YouTube URL back to manifest ---
  manifest.youtube = {
    videoId: result.videoId,
    url: result.videoUrl,
    uploadedAt: new Date().toISOString(),
    privacyStatus: metadata.privacyStatus,
  };
  // Atomic write: temp file + rename. Same filesystem (episode folder is on
  // repo SSD), so rename is a single atomic syscall. Prevents stale manifest
  // if process is killed between upload completion and disk flush.
  const manifestTmp = manifestPath + ".tmp";
  fs.writeFileSync(manifestTmp, JSON.stringify(manifest, null, 2));
  fs.renameSync(manifestTmp, manifestPath);

  console.log(`\nDone. Draft: ${result.videoUrl}`);
  console.log(`  manifest.json updated with youtube.videoId + youtube.url`);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
