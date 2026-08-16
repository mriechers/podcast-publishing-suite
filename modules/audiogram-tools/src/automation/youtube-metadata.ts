/**
 * youtube-metadata.ts
 *
 * Composes rich YouTube video metadata (title, description, tags, thumbnail
 * source) from a Wonder Cabinet episode's canonical artifacts:
 *
 *   - manifest.json         — guest, episode number, slug, drive IDs
 *   - chapters.md           — timestamps for YouTube auto-chapter detection
 *   - keywords.md           — SEO keywords + producer-curated description
 *   - formatted_transcript.md — fallback description source
 *   - images/WC_S01_*.jpg   — collage art (thumbnail candidate)
 *   - shows/<slug>/config.json — show-level YouTube settings (playlist, etc.)
 *
 * The composition pipeline mirrors prx-to-ghost-publisher's content_builder.py
 * but inverts every "strip boilerplate" rule — YouTube viewers WANT the
 * subscribe/newsletter/website CTAs that get stripped for Ghost RSS clients.
 *
 * See planning/wc_youtube_metadata_design.md for the full design rationale.
 */

import * as fs from "fs";
import * as path from "path";

// ─── Public Types ──────────────────────────────────────────────────────────

export interface ShowYouTubeConfig {
  channelHandle?: string;
  playlistId?: string;
  categoryId?: string;
  defaultPrivacy?: "private" | "unlisted" | "public";
  siteUrl?: string;
}

export interface ShowConfig {
  name: string;
  slug: string;
  ghost?: { siteUrl?: string; route?: string };
  youtube?: ShowYouTubeConfig;
  prx?: { feedUrl?: string };
}

export interface EpisodeManifest {
  slug: string;
  guestName?: string;
  episodeNumber?: number;
  season?: number;
  google_drive?: {
    episode_folder_id?: string;
    formatted_transcript_file_id?: string;
    chapters_file_id?: string;
    captions_file_id?: string;
  };
  youtube?: { videoId?: string; url?: string; title?: string };
}

export interface ChapterEntry {
  startSeconds: number;
  title: string;
}

export interface KeywordsBundle {
  primary: string[];
  longTail: string[];
  peopleAndOrgs: Array<{ name: string; description: string }>;
  topicTags: string[];
  suggestedDescription: string;
}

export interface YouTubeMetadata {
  title: string;
  description: string;
  tags: string[];
  categoryId: string;
  privacyStatus: "private" | "unlisted" | "public";
  thumbnailPath?: string;
  playlistId?: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────

const MAX_TITLE_LEN = 100;
const MAX_DESC_LEN = 5000;
const MAX_TAG_LEN = 30;
const MAX_TAGS_TOTAL_LEN = 500;

// ─── Source Loaders ────────────────────────────────────────────────────────

export function loadManifest(epDir: string): EpisodeManifest {
  const p = path.join(epDir, "manifest.json");
  if (!fs.existsSync(p)) {
    throw new Error(`manifest.json not found in ${epDir}`);
  }
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

/**
 * Parse the YouTube-formatted chapters section (section 3) from chapters.md.
 * Falls back to parsing the Apple Podcasts section (section 1, HH:MM:SS)
 * if section 3 is absent.
 */
export function parseChapters(chaptersMdPath: string): ChapterEntry[] {
  if (!fs.existsSync(chaptersMdPath)) return [];
  const text = fs.readFileSync(chaptersMdPath, "utf8");

  // Try YouTube section first — under "## 3. YouTube Description Format"
  const ytSection = text.match(/##\s*3\.[^\n]*YouTube[\s\S]*?```[^\n]*\n([\s\S]*?)```/i);
  if (ytSection) {
    return parseChapterLines(ytSection[1]);
  }

  // Fall back to Episode Description Timestamps (HH:MM:SS)
  const descSection = text.match(/##\s*1\.[^\n]*Episode Description[\s\S]*?```[^\n]*\n([\s\S]*?)```/i);
  if (descSection) {
    return parseChapterLines(descSection[1]);
  }

  return [];
}

function parseChapterLines(block: string): ChapterEntry[] {
  const out: ChapterEntry[] = [];
  for (const line of block.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const match = trimmed.match(/^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$/);
    if (!match) continue;
    out.push({ startSeconds: parseTimestamp(match[1]), title: match[2].trim() });
  }
  return out;
}

function parseTimestamp(ts: string): number {
  const parts = ts.split(":").map(Number);
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return 0;
}

/**
 * Parse keywords.md into structured sections. The format is producer-curated
 * via /wc-transcribe's keyword-extractor agent — see the prompt template
 * in modules/podcast-whisper-transcription/.claude/agents/keyword-extractor.md.
 */
export function parseKeywords(keywordsMdPath: string): KeywordsBundle {
  const empty: KeywordsBundle = {
    primary: [],
    longTail: [],
    peopleAndOrgs: [],
    topicTags: [],
    suggestedDescription: "",
  };
  if (!fs.existsSync(keywordsMdPath)) return empty;

  const text = fs.readFileSync(keywordsMdPath, "utf8");

  return {
    primary: extractListSection(text, /##\s*Primary Keywords/i),
    longTail: extractListSection(text, /##\s*Long-tail Phrases/i),
    peopleAndOrgs: extractListSection(text, /##\s*People\s*[&y]?\s*Organizations/i).map(parsePersonLine),
    topicTags: extractInlineTags(text, /##\s*Topic Tags/i),
    suggestedDescription: extractParagraph(text, /##\s*Suggested Episode Description/i),
  };
}

/**
 * Slice a Markdown file by `## ` section headers. Returns the body of the
 * section matching `headerPattern` (everything after the header line, up to
 * the next `## ` or end of file).
 */
function extractSectionBody(text: string, headerPattern: RegExp): string {
  const lines = text.split("\n");
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (headerPattern.test(lines[i])) {
      start = i + 1;
      break;
    }
  }
  if (start === -1) return "";

  let end = lines.length;
  for (let i = start; i < lines.length; i++) {
    if (/^##\s/.test(lines[i])) {
      end = i;
      break;
    }
  }
  return lines.slice(start, end).join("\n");
}

function extractListSection(text: string, headerPattern: RegExp): string[] {
  const body = extractSectionBody(text, headerPattern);
  return body
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("- "))
    .map((l) => l.slice(2).trim());
}

function extractInlineTags(text: string, headerPattern: RegExp): string[] {
  const body = extractSectionBody(text, headerPattern);
  const line = body.split("\n").map((l) => l.trim()).find((l) => l.length > 0 && !l.startsWith("- "));
  if (!line) return [];
  return line.split(",").map((s) => s.trim()).filter(Boolean);
}

function extractParagraph(text: string, headerPattern: RegExp): string {
  return extractSectionBody(text, headerPattern).trim();
}

function parsePersonLine(line: string): { name: string; description: string } {
  // Format: "Name — description text"
  const match = line.match(/^(.+?)\s*[—-]\s*(.+)$/);
  if (match) return { name: match[1].trim(), description: match[2].trim() };
  return { name: line, description: "" };
}

// ─── Composition Pipeline ──────────────────────────────────────────────────

export interface ComposeContext {
  epDir: string;
  showConfig: ShowConfig;
  manifest: EpisodeManifest;
  chapters: ChapterEntry[];
  keywords: KeywordsBundle;
  /** Optional override for the title */
  titleOverride?: string;
  /** URL to the editable Google Doc transcript (if available) */
  transcriptDocUrl?: string;
  /** Privacy override (default: showConfig.youtube.defaultPrivacy ?? "private") */
  privacy?: "private" | "unlisted" | "public";
}

export function composeTitle(ctx: ComposeContext): string {
  let title = ctx.titleOverride
    || ctx.manifest.youtube?.title
    || defaultTitleFromContext(ctx);

  // Trim to fit YouTube's 100-char limit at a word boundary if possible.
  if (title.length > MAX_TITLE_LEN) {
    const trimmed = title.slice(0, MAX_TITLE_LEN - 1);
    const lastSpace = trimmed.lastIndexOf(" ");
    title = (lastSpace > MAX_TITLE_LEN * 0.7 ? trimmed.slice(0, lastSpace) : trimmed) + "…";
  }

  return title;
}

function defaultTitleFromContext(ctx: ComposeContext): string {
  const guest = ctx.manifest.guestName || "Guest";
  const showName = ctx.showConfig.name;
  // Use the first non-"Introduction" chapter as a topic hook if available.
  const topicHook = ctx.chapters.find(
    (c) => !/^introduction|^intro/i.test(c.title)
  )?.title;
  if (topicHook) {
    return `${guest} on ${topicHook} | ${showName}`;
  }
  return `${guest} | ${showName}`;
}

export function composeDescription(ctx: ComposeContext): string {
  const lines: string[] = [];

  // [1] Hook — producer-curated suggested description from keywords.md
  if (ctx.keywords.suggestedDescription) {
    lines.push(ctx.keywords.suggestedDescription);
    lines.push("");
  }

  // [2] Chapters — promoted to top so YouTube parses them into video chapters.
  // Format MUST be `M:SS Title` or `H:MM:SS Title` per YouTube's spec.
  if (ctx.chapters.length > 0) {
    lines.push("📍 Chapters");
    for (const ch of ctx.chapters) {
      lines.push(`${formatYouTubeTimestamp(ch.startSeconds)} ${ch.title}`);
    }
    lines.push("");
  }

  // [3] Guest section — bio + ticker of people/orgs referenced
  const guest = ctx.manifest.guestName;
  if (guest) {
    const guestEntry = ctx.keywords.peopleAndOrgs.find((p) =>
      p.name.toLowerCase().includes(guest.split(" ").pop()!.toLowerCase())
    );
    lines.push(`👤 Guest`);
    if (guestEntry?.description) {
      lines.push(`${guestEntry.name} — ${guestEntry.description}`);
    } else {
      lines.push(guest);
    }
    lines.push("");
  }

  // [4] Referenced people & organizations (skip the guest, already shown)
  const others = ctx.keywords.peopleAndOrgs.filter((p) => {
    if (!guest) return true;
    return !p.name.toLowerCase().includes(guest.split(" ").pop()!.toLowerCase());
  });
  if (others.length > 0) {
    lines.push("📚 References in this episode");
    for (const ref of others.slice(0, 12)) {
      lines.push(`• ${ref.name}${ref.description ? ` — ${ref.description}` : ""}`);
    }
    lines.push("");
  }

  // [5] Links section
  lines.push("🔗 Links");
  if (ctx.transcriptDocUrl) {
    lines.push(`📝 Full transcript: ${ctx.transcriptDocUrl}`);
  }
  const ghostUrl = ctx.showConfig.ghost?.siteUrl;
  const ghostRoute = ctx.showConfig.ghost?.route || "";
  if (ghostUrl) {
    lines.push(`🌐 Show notes & full episode archive: ${ghostUrl}${ghostRoute}`);
    lines.push(`📨 Subscribe to the newsletter: ${ghostUrl}/#/portal/signup`);
  }
  if (ctx.showConfig.prx?.feedUrl) {
    lines.push(`🎙️ Subscribe to the podcast (RSS): ${ctx.showConfig.prx.feedUrl}`);
  }
  lines.push("");

  // [6] Show identity block
  lines.push("─".repeat(40));
  lines.push("");
  lines.push(ctx.showConfig.name);
  // Show tagline could come from brand.ts; keep it lean here.
  lines.push("");

  // [7] Hashtags — YouTube treats trailing #tags as additional metadata
  const hashtagPool = [
    ctx.showConfig.slug.replace(/-/g, ""),
    "podcast",
    ...ctx.keywords.primary.slice(0, 3).map((t) => t.replace(/[^a-zA-Z0-9]/g, "")),
  ].filter(Boolean);
  if (hashtagPool.length > 0) {
    lines.push(hashtagPool.map((t) => `#${t}`).join(" "));
  }

  let description = lines.join("\n").trim();

  // Enforce 5000-char cap by truncating the People & References section first.
  if (description.length > MAX_DESC_LEN) {
    description = description.slice(0, MAX_DESC_LEN - 1) + "…";
  }

  return description;
}

function formatYouTubeTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function composeTags(ctx: ComposeContext): string[] {
  // Priority order: primary keywords, topic tags, show-level defaults.
  const candidates = [
    ctx.showConfig.name.toLowerCase(),
    "podcast",
    ...ctx.keywords.primary,
    ...ctx.keywords.topicTags,
  ];

  // Normalize + dedupe (case-insensitive) + filter by YouTube's constraints.
  const seen = new Set<string>();
  const tags: string[] = [];
  let totalLen = 0;

  for (const raw of candidates) {
    const tag = raw.toLowerCase().trim();
    if (!tag) continue;
    if (seen.has(tag)) continue;
    if (tag.length > MAX_TAG_LEN) continue;
    if (/[<>]/.test(tag)) continue;
    // YouTube counts the comma between tags + the tag itself
    const lenContribution = tag.length + (tags.length > 0 ? 1 : 0);
    if (totalLen + lenContribution > MAX_TAGS_TOTAL_LEN) break;

    seen.add(tag);
    tags.push(tag);
    totalLen += lenContribution;
  }

  return tags;
}

/**
 * Compose the full YouTube metadata bundle from a canonical episode dir.
 * This is the top-level entry point.
 */
export function composeYouTubeMetadata(opts: {
  epDir: string;
  showConfig: ShowConfig;
  titleOverride?: string;
  transcriptDocUrl?: string;
  privacy?: "private" | "unlisted" | "public";
}): YouTubeMetadata {
  const manifest = loadManifest(opts.epDir);
  const chapters = parseChapters(path.join(opts.epDir, "chapters.md"));
  const keywords = parseKeywords(path.join(opts.epDir, "keywords.md"));

  const ctx: ComposeContext = {
    epDir: opts.epDir,
    showConfig: opts.showConfig,
    manifest,
    chapters,
    keywords,
    titleOverride: opts.titleOverride,
    transcriptDocUrl: opts.transcriptDocUrl
      || resolveTranscriptDocUrl(manifest),
    privacy: opts.privacy,
  };

  const title = composeTitle(ctx);
  const description = composeDescription(ctx);
  const tags = composeTags(ctx);
  const categoryId = opts.showConfig.youtube?.categoryId || "27";
  const privacyStatus = opts.privacy
    || opts.showConfig.youtube?.defaultPrivacy
    || "private";
  const thumbnailPath = resolveThumbnailPath(opts.epDir);

  return {
    title,
    description,
    tags,
    categoryId,
    privacyStatus,
    thumbnailPath,
    playlistId: opts.showConfig.youtube?.playlistId,
  };
}

function resolveTranscriptDocUrl(manifest: EpisodeManifest): string | undefined {
  const id = manifest.google_drive?.formatted_transcript_file_id;
  if (!id) return undefined;
  return `https://drive.google.com/file/d/${id}/view`;
}

function resolveThumbnailPath(epDir: string): string | undefined {
  const imagesDir = path.join(epDir, "images");
  if (!fs.existsSync(imagesDir)) return undefined;
  // Prefer canonical-named files: WC_S01_*.jpg
  const files = fs.readdirSync(imagesDir);
  const canonical = files.find((f) => /^WC_S\d{2}_.*\.(jpg|jpeg|png)$/i.test(f));
  if (canonical) return path.join(imagesDir, canonical);
  // Last-ditch: any image at top level (not the originals subdir)
  const any = files.find((f) => /\.(jpg|jpeg|png)$/i.test(f));
  return any ? path.join(imagesDir, any) : undefined;
}

// ─── CLI for testing / dry-run ──────────────────────────────────────────────

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0 || args.includes("--help")) {
    console.log("Usage: npx tsx youtube-metadata.ts <episode-dir> [show-slug]");
    console.log("");
    console.log("Composes and prints YouTube metadata for the given episode dir.");
    console.log("Does not upload — for testing/inspection only.");
    process.exit(args.includes("--help") ? 0 : 1);
  }
  const epDir = path.resolve(args[0]);
  const showSlug = args[1] || "wonder-cabinet";

  // Resolve show config — assume we're inside a podcast-publishing-suite checkout
  const repoRoot = findRepoRoot(epDir);
  const showConfigPath = path.join(repoRoot, "shows", showSlug, "config.json");
  if (!fs.existsSync(showConfigPath)) {
    console.error(`Show config not found: ${showConfigPath}`);
    process.exit(1);
  }
  const showConfig: ShowConfig = JSON.parse(fs.readFileSync(showConfigPath, "utf8"));

  const metadata = composeYouTubeMetadata({ epDir, showConfig });

  console.log(JSON.stringify(metadata, null, 2));
  console.log("\n─── Stats ───");
  console.log(`title:       ${metadata.title.length} chars (limit ${MAX_TITLE_LEN})`);
  console.log(`description: ${metadata.description.length} chars (limit ${MAX_DESC_LEN})`);
  console.log(`tags:        ${metadata.tags.length} tags, ${metadata.tags.join(",").length} total chars (limit ${MAX_TAGS_TOTAL_LEN})`);
  console.log(`thumbnail:   ${metadata.thumbnailPath || "(none — YouTube will auto-generate)"}`);
}

function findRepoRoot(start: string): string {
  let cur = start;
  while (cur !== "/") {
    if (fs.existsSync(path.join(cur, "shows")) && fs.existsSync(path.join(cur, "modules"))) {
      return cur;
    }
    cur = path.dirname(cur);
  }
  throw new Error("Could not locate podcast-publishing-suite root from " + start);
}

if (require.main === module) {
  main();
}
