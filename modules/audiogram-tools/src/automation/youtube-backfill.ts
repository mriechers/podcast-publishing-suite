/**
 * youtube-backfill.ts
 *
 * Batch YouTube uploads for episodes whose video has already been rendered.
 * Audits a show's episode directory, classifies each folder, presents a plan
 * to the operator, and uploads each eligible episode using the same flow as
 * wc-export-and-upload.ts.
 *
 * Modes:
 *   --audit          Audit only. Print the plan. No uploads.
 *   --filter X       Process specific episodes: "1-6,10,12" or "10".
 *   --limit N        Stop after N successful uploads.
 *   --dry-run        Compose all metadata, print plans, don't upload.
 *   --privacy=...    Override default privacy for all uploads.
 *   --force          Re-upload episodes that already have manifest.youtube.videoId.
 *
 * Usage:
 *   # Audit only:
 *   npx tsx src/automation/youtube-backfill.ts --show wonder-cabinet --audit
 *
 *   # Backfill all eligible:
 *   npx tsx src/automation/youtube-backfill.ts --show wonder-cabinet
 *
 *   # Backfill specific episodes:
 *   npx tsx src/automation/youtube-backfill.ts --show wonder-cabinet --filter 7-10
 */

import * as fs from "fs";
import * as path from "path";
import { spawn } from "child_process";
import {
  composeYouTubeMetadata,
  loadManifest,
  ShowConfig,
  EpisodeManifest,
} from "./youtube-metadata";

type EpisodeStatus =
  | "uploaded"
  | "ready"
  | "needs_render"
  | "needs_metadata"
  | "broken"
  | "ignored";

interface EpisodeAudit {
  dir: string;
  slug: string;
  episodeNumber?: number;
  guestName?: string;
  status: EpisodeStatus;
  reason?: string;
  mp4Path?: string;
  mp4SizeMb?: number;
  hasMetadata: boolean;
  videoId?: string;
}

interface CliOpts {
  show: string;
  audit: boolean;
  filter?: string;
  limit?: number;
  dryRun: boolean;
  privacy?: "private" | "unlisted" | "public";
  force: boolean;
}

function parseArgs(argv: string[]): CliOpts {
  const args = argv.slice(2);
  if (args.includes("--help") || args.includes("-h") || args.length === 0) {
    printHelp();
    process.exit(args.length === 0 ? 1 : 0);
  }

  const opts: CliOpts = {
    show: "wonder-cabinet",
    audit: false,
    dryRun: false,
    force: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--audit") opts.audit = true;
    else if (arg === "--dry-run") opts.dryRun = true;
    else if (arg === "--force") opts.force = true;
    else if (arg === "--show") opts.show = args[++i];
    else if (arg.startsWith("--show=")) opts.show = arg.split("=")[1];
    else if (arg === "--filter") opts.filter = args[++i];
    else if (arg.startsWith("--filter=")) opts.filter = arg.split("=")[1];
    else if (arg === "--limit") opts.limit = parseInt(args[++i], 10);
    else if (arg.startsWith("--limit=")) opts.limit = parseInt(arg.split("=")[1], 10);
    else if (arg === "--privacy") opts.privacy = args[++i] as any;
    else if (arg.startsWith("--privacy=")) opts.privacy = arg.split("=")[1] as any;
  }

  return opts;
}

function printHelp() {
  console.log(`Usage: npx tsx youtube-backfill.ts [options]

Options:
  --show <slug>        Show to backfill (default: wonder-cabinet)
  --audit              Audit only — print the plan, no uploads
  --filter <range>     Episodes to process: "1-6,10,12" or "10"
  --limit N            Stop after N successful uploads
  --dry-run            Compose + print plan for each, no upload
  --privacy <level>    private | unlisted | public (default: show config)
  --force              Re-upload even if manifest.youtube.videoId exists

Examples:
  # See what's eligible:
  npx tsx youtube-backfill.ts --show wonder-cabinet --audit

  # Upload everything eligible as drafts:
  npx tsx youtube-backfill.ts --show wonder-cabinet

  # Upload just E7-E10:
  npx tsx youtube-backfill.ts --show wonder-cabinet --filter 7-10
`);
}

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

function findEpisodeMp4(epDir: string, epNum: number | undefined): { path: string; sizeMb: number } | null {
  const audiogramDir = path.join(epDir, "audiogram");
  if (!fs.existsSync(audiogramDir)) return null;

  const candidates = fs.readdirSync(audiogramDir).filter((f) => f.toLowerCase().endsWith(".mp4"));

  // Priority order: _youtube.mp4, EP{N}_, E{N}-, anything >100MB
  const youtubeFile = candidates.find((f) => /_youtube\.mp4$/i.test(f));
  if (youtubeFile) {
    const p = path.join(audiogramDir, youtubeFile);
    return { path: p, sizeMb: fs.statSync(p).size / (1024 * 1024) };
  }

  if (epNum !== undefined) {
    const canonical = candidates.find((f) => new RegExp(`^EP${epNum}[_-]`, "i").test(f));
    if (canonical) {
      const p = path.join(audiogramDir, canonical);
      return { path: p, sizeMb: fs.statSync(p).size / (1024 * 1024) };
    }
    const eFallback = candidates.find((f) => new RegExp(`^E${epNum}[_-]`, "i").test(f));
    if (eFallback) {
      const p = path.join(audiogramDir, eFallback);
      return { path: p, sizeMb: fs.statSync(p).size / (1024 * 1024) };
    }
  }

  // Last ditch: any non-test mp4 over 100MB
  const big = candidates.find((f) => {
    if (/test|smoke|sample/i.test(f)) return false;
    return fs.statSync(path.join(audiogramDir, f)).size > 100 * 1024 * 1024;
  });
  if (big) {
    const p = path.join(audiogramDir, big);
    return { path: p, sizeMb: fs.statSync(p).size / (1024 * 1024) };
  }

  return null;
}

function auditEpisode(epDir: string): EpisodeAudit {
  const slug = path.basename(epDir);

  // Ignore archived/duplicate prefixes
  if (slug.startsWith("_") || /bonus/i.test(slug)) {
    return {
      dir: epDir,
      slug,
      status: "ignored",
      reason: "archive/non-episode prefix",
      hasMetadata: false,
    };
  }

  const manifestPath = path.join(epDir, "manifest.json");
  if (!fs.existsSync(manifestPath)) {
    // No manifest — check if there's a rendered MP4 anyway (E1-E6 cohort)
    const mp4 = findEpisodeMp4(epDir, undefined);
    if (mp4) {
      // Try to extract episode number from MP4 filename
      const epNumMatch = path.basename(mp4.path).match(/EP?(\d+)/i);
      const epNum = epNumMatch ? parseInt(epNumMatch[1], 10) : undefined;
      const guestMatch = path.basename(mp4.path).match(/EP?\d+[_-]([A-Za-z][\w-]+?)(?:_|\.)/);
      const guest = guestMatch ? guestMatch[1].replace(/-/g, " ") : undefined;
      return {
        dir: epDir,
        slug,
        episodeNumber: epNum,
        guestName: guest,
        status: "needs_metadata",
        reason: "no manifest.json — backfill will use PRX + filename heuristic",
        mp4Path: mp4.path,
        mp4SizeMb: mp4.sizeMb,
        hasMetadata: false,
      };
    }
    return {
      dir: epDir,
      slug,
      status: "broken",
      reason: "no manifest.json and no rendered MP4",
      hasMetadata: false,
    };
  }

  let manifest: EpisodeManifest;
  try {
    manifest = loadManifest(epDir);
  } catch (err: any) {
    return {
      dir: epDir,
      slug,
      status: "broken",
      reason: `manifest parse error: ${err.message}`,
      hasMetadata: false,
    };
  }

  const audit: EpisodeAudit = {
    dir: epDir,
    slug,
    episodeNumber: manifest.episodeNumber,
    guestName: manifest.guestName,
    status: "ready",
    hasMetadata: true,
  };

  if (manifest.youtube?.videoId) {
    audit.status = "uploaded";
    audit.videoId = manifest.youtube.videoId;
    audit.reason = `already on YouTube: ${manifest.youtube.url}`;
    return audit;
  }

  const mp4 = findEpisodeMp4(epDir, manifest.episodeNumber);
  if (!mp4) {
    audit.status = "needs_render";
    audit.reason = "no rendered MP4 in audiogram/";
    return audit;
  }

  audit.mp4Path = mp4.path;
  audit.mp4SizeMb = mp4.sizeMb;
  return audit;
}

function parseFilter(filter: string): Set<number> {
  const out = new Set<number>();
  for (const part of filter.split(",")) {
    const trimmed = part.trim();
    const range = trimmed.match(/^(\d+)-(\d+)$/);
    if (range) {
      const [_, lo, hi] = range;
      for (let n = parseInt(lo, 10); n <= parseInt(hi, 10); n++) out.add(n);
    } else {
      out.add(parseInt(trimmed, 10));
    }
  }
  return out;
}

function printAudit(audits: EpisodeAudit[]) {
  const byStatus: Record<EpisodeStatus, EpisodeAudit[]> = {
    uploaded: [],
    ready: [],
    needs_metadata: [],
    needs_render: [],
    broken: [],
    ignored: [],
  };
  for (const a of audits) byStatus[a.status].push(a);

  console.log("\n" + "═".repeat(60));
  console.log("YouTube backfill audit");
  console.log("═".repeat(60));

  if (byStatus.uploaded.length > 0) {
    console.log(`\n✓ Already on YouTube (${byStatus.uploaded.length}):`);
    for (const a of byStatus.uploaded) {
      console.log(`   E${a.episodeNumber || "?"} ${a.guestName || a.slug}`);
      console.log(`        ${a.reason}`);
    }
  }

  if (byStatus.ready.length > 0) {
    console.log(`\n📤 Ready to upload (${byStatus.ready.length}):`);
    for (const a of byStatus.ready) {
      const sizeStr = a.mp4SizeMb ? `${a.mp4SizeMb.toFixed(0)} MB` : "?";
      console.log(`   E${String(a.episodeNumber || "?").padStart(2)} ${(a.guestName || a.slug).padEnd(28)} ${path.basename(a.mp4Path || "")} (${sizeStr})`);
    }
  }

  if (byStatus.needs_metadata.length > 0) {
    console.log(`\n⚠ Needs metadata fallback (${byStatus.needs_metadata.length}):`);
    for (const a of byStatus.needs_metadata) {
      console.log(`   E${a.episodeNumber || "?"} ${a.guestName || a.slug}  ${a.reason}`);
    }
  }

  if (byStatus.needs_render.length > 0) {
    console.log(`\n🎬 Needs render first (${byStatus.needs_render.length}):`);
    for (const a of byStatus.needs_render) {
      console.log(`   E${a.episodeNumber || "?"} ${a.guestName || a.slug}  ${a.reason}`);
      console.log(`        run: /wc-youtube-export <ep ${a.episodeNumber}>`);
    }
  }

  if (byStatus.broken.length > 0) {
    console.log(`\n✗ Broken / incomplete (${byStatus.broken.length}):`);
    for (const a of byStatus.broken) {
      console.log(`   ${a.slug}  ${a.reason}`);
    }
  }

  if (byStatus.ignored.length > 0) {
    console.log(`\n⊘ Ignored (${byStatus.ignored.length}):`);
    for (const a of byStatus.ignored) {
      console.log(`   ${a.slug}  ${a.reason}`);
    }
  }

  console.log("\n" + "═".repeat(60));
}

function runUpload(epDir: string, opts: { privacy?: string; dryRun: boolean; force: boolean }): Promise<{ ok: boolean; output: string }> {
  return new Promise((resolve) => {
    const args = ["tsx", path.join(__dirname, "wc-export-and-upload.ts"), epDir];
    if (opts.privacy) args.push(`--privacy=${opts.privacy}`);
    if (opts.dryRun) args.push("--dry-run");

    const child = spawn("npx", args, { stdio: "inherit" });
    child.on("close", (code) => {
      resolve({ ok: code === 0, output: "" });
    });
  });
}

async function main() {
  const opts = parseArgs(process.argv);
  const repoRoot = findRepoRoot(process.cwd());
  const episodesDir = path.join(repoRoot, "shows", opts.show, "episodes");

  if (!fs.existsSync(episodesDir)) {
    console.error(`Episodes dir not found: ${episodesDir}`);
    process.exit(1);
  }

  // Discover + audit
  const epDirs = fs.readdirSync(episodesDir)
    .map((name) => path.join(episodesDir, name))
    .filter((p) => fs.statSync(p).isDirectory());

  let audits = epDirs.map(auditEpisode).sort((a, b) => (a.episodeNumber || 99) - (b.episodeNumber || 99));

  // Apply --filter
  if (opts.filter) {
    const allowed = parseFilter(opts.filter);
    audits = audits.map((a) => {
      if (a.episodeNumber !== undefined && !allowed.has(a.episodeNumber)) {
        return { ...a, status: "ignored" as const, reason: `excluded by --filter ${opts.filter}` };
      }
      return a;
    });
  }

  printAudit(audits);

  if (opts.audit) {
    console.log("\nAudit only mode — exiting without uploads.\n");
    return;
  }

  // Determine what to upload
  const eligible = audits.filter((a) => {
    if (a.status === "ready") return true;
    if (a.status === "uploaded" && opts.force) return true;
    return false;
  });

  if (eligible.length === 0) {
    console.log("\nNothing to upload. (Use --force to re-upload already-uploaded episodes.)\n");
    return;
  }

  console.log(`\n→ Will ${opts.dryRun ? "dry-run" : "upload"} ${eligible.length} episode(s)`);
  if (opts.limit && opts.limit < eligible.length) {
    console.log(`  Stopping after first ${opts.limit} per --limit`);
  }

  // Process sequentially — uploads are large, parallel won't help and may rate-limit
  let success = 0;
  let fail = 0;
  const target = opts.limit ? Math.min(opts.limit, eligible.length) : eligible.length;

  for (let i = 0; i < target; i++) {
    const audit = eligible[i];
    console.log(`\n[${i + 1}/${target}] E${audit.episodeNumber}: ${audit.guestName || audit.slug}`);
    const result = await runUpload(audit.dir, { privacy: opts.privacy, dryRun: opts.dryRun, force: opts.force });
    if (result.ok) success++;
    else fail++;
  }

  console.log(`\n${success} succeeded, ${fail} failed.`);
}

main().catch((err) => {
  console.error("\n✗ Error:", err.message || err);
  process.exit(1);
});
