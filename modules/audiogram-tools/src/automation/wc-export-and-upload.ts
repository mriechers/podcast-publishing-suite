/**
 * wc-export-and-upload.ts
 *
 * Single-episode orchestrator: takes a canonical Wonder Cabinet episode dir,
 * composes rich YouTube metadata, uploads the rendered MP4 as a YouTube draft,
 * sets the thumbnail, adds to the configured playlist, and writes the result
 * back to manifest.json.
 *
 * Does NOT render — assumes audiogram/EP{N}_*.mp4 already exists (via
 * render-trigger.ts or a prior run). For fresh exports that need to render
 * first, see /wc-youtube-export skill which chains render + this script.
 *
 * Used by both:
 *   - /wc-youtube-export (after the render phase)
 *   - youtube-backfill.ts (batch mode, --skip-render-check)
 *
 * Usage:
 *   npx tsx src/automation/wc-export-and-upload.ts \
 *     ../../shows/wonder-cabinet/episodes/WC_S01_15_D._Graham_Burnett \
 *     [--privacy=private|unlisted|public] \
 *     [--title="Custom Title Override"] \
 *     [--dry-run] \
 *     [--skip-upload]
 */

import * as fs from "fs";
import * as path from "path";
import {
  composeYouTubeMetadata,
  ShowConfig,
  YouTubeMetadata,
  loadManifest,
} from "./youtube-metadata";
import { uploadVideo, addToPlaylist } from "./youtube-upload";

interface CliOpts {
  epDir: string;
  privacy?: "private" | "unlisted" | "public";
  titleOverride?: string;
  dryRun: boolean;
  skipUpload: boolean;
}

function parseArgs(argv: string[]): CliOpts {
  const args = argv.slice(2);
  if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
    printHelp();
    process.exit(args.includes("--help") || args.includes("-h") ? 0 : 1);
  }

  const opts: CliOpts = {
    epDir: path.resolve(args[0]),
    dryRun: false,
    skipUpload: false,
  };

  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--dry-run") {
      opts.dryRun = true;
    } else if (arg === "--skip-upload") {
      opts.skipUpload = true;
    } else if (arg.startsWith("--privacy=")) {
      opts.privacy = arg.split("=")[1] as CliOpts["privacy"];
    } else if (arg === "--privacy") {
      opts.privacy = args[++i] as CliOpts["privacy"];
    } else if (arg.startsWith("--title=")) {
      opts.titleOverride = arg.split("=")[1];
    } else if (arg === "--title") {
      opts.titleOverride = args[++i];
    }
  }

  return opts;
}

function printHelp() {
  console.log(`Usage: npx tsx wc-export-and-upload.ts <episode-dir> [options]

Required:
  <episode-dir>        Path to canonical episode directory

Options:
  --privacy=<level>    private | unlisted | public (default: from show config)
  --title=<text>       Override the auto-generated title
  --dry-run            Compose metadata + print plan; do not upload
  --skip-upload        Same as --dry-run but still validates everything

Example:
  npx tsx wc-export-and-upload.ts \\
    ../../shows/wonder-cabinet/episodes/WC_S01_15_D._Graham_Burnett \\
    --privacy=private
`);
}

/**
 * Walk up from start to find the podcast-publishing-suite repo root
 * (the directory containing both 'shows/' and 'modules/').
 */
function findRepoRoot(start: string): string {
  let cur = start;
  while (cur !== "/") {
    if (
      fs.existsSync(path.join(cur, "shows")) &&
      fs.existsSync(path.join(cur, "modules"))
    ) {
      return cur;
    }
    cur = path.dirname(cur);
  }
  throw new Error("Could not locate publishing-suite root from " + start);
}

/**
 * Find the canonical MP4 for an episode. Resolves in priority order:
 *   1. audiogram/<slug>_youtube.mp4 (explicit YouTube-encoded target — symlink or file)
 *   2. audiogram/EP{N}_*.mp4 (canonical naming)
 *   3. audiogram/E{N}-*.mp4 or E{N}_*.mp4 (off-convention but plausible)
 */
function findEpisodeMp4(epDir: string, slug: string, epNum: number | undefined): string | null {
  const audiogramDir = path.join(epDir, "audiogram");
  if (!fs.existsSync(audiogramDir)) return null;

  const candidates = fs.readdirSync(audiogramDir)
    .filter((f) => f.toLowerCase().endsWith(".mp4"));

  // Priority 1: youtube-suffix symlink/file
  const youtubeFile = candidates.find((f) => /_youtube\.mp4$/i.test(f));
  if (youtubeFile) return path.join(audiogramDir, youtubeFile);

  // Priority 2: EP{N}_*.mp4 canonical
  if (epNum) {
    const canonical = candidates.find((f) => new RegExp(`^EP${epNum}[_-]`, "i").test(f));
    if (canonical) return path.join(audiogramDir, canonical);
  }

  // Priority 3: E{N}-*.mp4 or anything else
  if (epNum) {
    const fallback = candidates.find((f) => new RegExp(`^E${epNum}[_-]`, "i").test(f));
    if (fallback) return path.join(audiogramDir, fallback);
  }

  // Last ditch: any non-test mp4 over 100MB
  const big = candidates.find((f) => {
    if (/test|smoke|sample/i.test(f)) return false;
    const stat = fs.statSync(path.join(audiogramDir, f));
    return stat.size > 100 * 1024 * 1024;
  });
  return big ? path.join(audiogramDir, big) : null;
}

function loadShowConfig(repoRoot: string, showSlug: string): ShowConfig {
  const configPath = path.join(repoRoot, "shows", showSlug, "config.json");
  if (!fs.existsSync(configPath)) {
    throw new Error(`Show config not found: ${configPath}`);
  }
  return JSON.parse(fs.readFileSync(configPath, "utf8"));
}

function printPlan(metadata: YouTubeMetadata, mp4Path: string, dryRun: boolean) {
  const mp4Size = fs.statSync(mp4Path).size;
  const mp4Mb = (mp4Size / (1024 * 1024)).toFixed(1);

  console.log("\n" + "═".repeat(60));
  console.log("YouTube upload plan" + (dryRun ? "  (DRY RUN)" : ""));
  console.log("═".repeat(60));
  console.log(`Video:       ${path.basename(mp4Path)} (${mp4Mb} MB)`);
  console.log(`Title:       ${metadata.title}`);
  console.log(`Privacy:     ${metadata.privacyStatus}`);
  console.log(`Category:    ${metadata.categoryId}`);
  console.log(`Playlist:    ${metadata.playlistId || "(none)"}`);
  console.log(`Tags:        ${metadata.tags.length} tags, ${metadata.tags.join(",").length}/500 chars`);
  console.log(`Description: ${metadata.description.length}/5000 chars`);
  console.log(`Thumbnail:   ${metadata.thumbnailPath ? path.basename(metadata.thumbnailPath) : "(none — auto-generate)"}`);
  console.log("─".repeat(60));
  console.log("Description preview:");
  const preview = metadata.description.split("\n").slice(0, 8).join("\n");
  console.log(preview + (metadata.description.split("\n").length > 8 ? "\n…" : ""));
  console.log("═".repeat(60));
}

async function main() {
  const opts = parseArgs(process.argv);

  // Validate episode dir
  if (!fs.existsSync(opts.epDir)) {
    console.error(`Episode dir not found: ${opts.epDir}`);
    process.exit(1);
  }

  const manifest = loadManifest(opts.epDir);
  const repoRoot = findRepoRoot(opts.epDir);

  // Show slug is in manifest.show — fall back to extracting from path
  const showSlug = (manifest as any).show || "wonder-cabinet";
  const showConfig = loadShowConfig(repoRoot, showSlug);

  // Idempotency check
  if (manifest.youtube?.videoId && !opts.skipUpload && !opts.dryRun) {
    console.error(`\n⚠ This episode already has a YouTube videoId: ${manifest.youtube.videoId}`);
    console.error(`  URL: ${manifest.youtube.url}`);
    console.error(`  Skipping. Delete .youtube.videoId from manifest.json to re-upload.`);
    process.exit(0);
  }

  // Find the rendered MP4
  const mp4Path = findEpisodeMp4(opts.epDir, manifest.slug, manifest.episodeNumber);
  if (!mp4Path) {
    console.error(`\n✗ No rendered MP4 found in ${opts.epDir}/audiogram/`);
    console.error(`  Run /wc-youtube-export first to render the video.`);
    process.exit(1);
  }

  // Compose metadata
  const metadata = composeYouTubeMetadata({
    epDir: opts.epDir,
    showConfig,
    titleOverride: opts.titleOverride,
    privacy: opts.privacy,
  });

  printPlan(metadata, mp4Path, opts.dryRun || opts.skipUpload);

  if (opts.dryRun || opts.skipUpload) {
    console.log("\nDry run complete. No upload performed.");
    return;
  }

  // Upload
  console.log("\nStarting upload...");
  const result = await uploadVideo({
    videoPath: mp4Path,
    title: metadata.title,
    description: metadata.description,
    tags: metadata.tags,
    categoryId: metadata.categoryId,
    privacyStatus: metadata.privacyStatus,
    thumbnailPath: metadata.thumbnailPath,
  });

  // Add to playlist (if configured)
  if (metadata.playlistId) {
    try {
      console.log(`\nAdding to playlist ${metadata.playlistId}...`);
      await addToPlaylist(result.videoId, metadata.playlistId);
    } catch (err: any) {
      // Don't fail the whole flow on a playlist error — surface it
      console.error(`⚠ Playlist add failed: ${err.message || err}`);
      console.error("  Video uploaded successfully. Add to playlist manually if needed.");
    }
  }

  // Record in manifest
  const updatedManifest = {
    ...manifest,
    youtube: {
      ...(manifest.youtube || {}),
      videoId: result.videoId,
      url: result.videoUrl,
      title: metadata.title,
      privacyStatus: metadata.privacyStatus,
      uploadedAt: new Date().toISOString(),
      playlistId: metadata.playlistId,
    },
    timestamps: {
      ...((manifest as any).timestamps || {}),
      uploaded_to_youtube: new Date().toISOString(),
    },
  };
  fs.writeFileSync(
    path.join(opts.epDir, "manifest.json"),
    JSON.stringify(updatedManifest, null, 2) + "\n"
  );

  console.log("\n" + "═".repeat(60));
  console.log("✓ Upload complete");
  console.log("═".repeat(60));
  console.log(`Video ID:    ${result.videoId}`);
  console.log(`URL:         ${result.videoUrl}`);
  console.log(`Privacy:     ${metadata.privacyStatus}`);
  console.log(`Manifest:    updated with youtube.videoId + youtube.url`);
  console.log("═".repeat(60));
}

main().catch((err) => {
  console.error("\n✗ Error:", err.message || err);
  if (err.stack) console.error(err.stack);
  process.exit(1);
});
