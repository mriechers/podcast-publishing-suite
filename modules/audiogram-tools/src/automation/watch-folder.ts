/**
 * Watch Folder Automation
 *
 * Monitors a directory for new audio files and triggers video rendering.
 *
 * File naming convention:
 * - Full episodes: EP{number}_{guest-name}_{title}.mp3
 *   Example: EP42_Dr-Jane-Doe_Journey-Into-Wonder.mp3
 *
 * - Social clips: CLIP_{guest-name}_{hook-text}.mp3
 *   Example: CLIP_Dr-Jane-Doe_This-changed-everything.mp3
 *
 * Metadata can also be provided via JSON sidecar file:
 * - EP42_Dr-Jane-Doe.json alongside EP42_Dr-Jane-Doe.mp3
 */

import chokidar from "chokidar";
import path from "path";
import fs from "fs";
import { spawn } from "child_process";
import "dotenv/config";

// Configuration
const WATCH_DIR = process.env.WATCH_DIR || "./input";
const OUTPUT_DIR = process.env.OUTPUT_DIR || "./output";
const SUPPORTED_FORMATS = [".mp3", ".wav", ".m4a", ".aac", ".ogg"];

interface EpisodeMetadata {
  type: "episode" | "clip";
  episodeNumber?: number;
  guestName: string;
  title?: string;
  hookText?: string;
  colorScheme?: "dark" | "green" | "warm";
  waveformStyle?: "mirror" | "bars" | "circle" | "line";
}

/**
 * Parse metadata from filename convention
 */
function parseFilename(filename: string): EpisodeMetadata | null {
  const basename = path.basename(filename, path.extname(filename));

  // Full episode pattern: EP{number}_{guest}_{title}
  const episodeMatch = basename.match(/^EP(\d+)_([^_]+)_?(.*)$/i);
  if (episodeMatch) {
    return {
      type: "episode",
      episodeNumber: parseInt(episodeMatch[1], 10),
      guestName: episodeMatch[2].replace(/-/g, " "),
      title: episodeMatch[3]?.replace(/-/g, " ") || undefined,
    };
  }

  // Social clip pattern: CLIP_{guest}_{hook}
  const clipMatch = basename.match(/^CLIP_([^_]+)_?(.*)$/i);
  if (clipMatch) {
    return {
      type: "clip",
      guestName: clipMatch[1].replace(/-/g, " "),
      hookText: clipMatch[2]?.replace(/-/g, " ") || undefined,
    };
  }

  console.warn(`Could not parse filename: ${filename}`);
  return null;
}

/**
 * Load metadata from JSON sidecar file if it exists
 */
function loadSidecarMetadata(audioPath: string): Partial<EpisodeMetadata> | null {
  const jsonPath = audioPath.replace(path.extname(audioPath), ".json");

  if (fs.existsSync(jsonPath)) {
    try {
      const content = fs.readFileSync(jsonPath, "utf-8");
      return JSON.parse(content);
    } catch (error) {
      console.error(`Error reading sidecar JSON: ${jsonPath}`, error);
    }
  }

  return null;
}

/**
 * Get audio duration using ffprobe (requires ffmpeg installed)
 */
async function getAudioDuration(audioPath: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const ffprobe = spawn("ffprobe", [
      "-v",
      "error",
      "-show_entries",
      "format=duration",
      "-of",
      "default=noprint_wrappers=1:nokey=1",
      audioPath,
    ]);

    let output = "";
    ffprobe.stdout.on("data", (data) => {
      output += data.toString();
    });

    ffprobe.on("close", (code) => {
      if (code === 0) {
        const duration = parseFloat(output.trim());
        resolve(duration);
      } else {
        reject(new Error(`ffprobe exited with code ${code}`));
      }
    });

    ffprobe.on("error", reject);
  });
}

/**
 * Render video using Remotion CLI
 */
async function renderVideo(
  audioPath: string,
  metadata: EpisodeMetadata,
  durationSeconds: number
): Promise<string> {
  const fps = 30;
  const durationInFrames = Math.ceil(durationSeconds * fps);

  // Determine composition and output filename
  const composition = metadata.type === "episode" ? "FullEpisode" : "SocialClip";
  const timestamp = new Date().toISOString().slice(0, 10);
  const safeName = metadata.guestName.replace(/[^a-zA-Z0-9]/g, "-");

  let outputFilename: string;
  if (metadata.type === "episode" && metadata.episodeNumber) {
    outputFilename = `EP${metadata.episodeNumber}_${safeName}_${timestamp}.mp4`;
  } else {
    outputFilename = `CLIP_${safeName}_${timestamp}.mp4`;
  }

  const outputPath = path.join(OUTPUT_DIR, outputFilename);

  // Build props object
  const props: Record<string, unknown> = {
    audioSrc: path.resolve(audioPath),
    guestName: metadata.guestName,
  };

  if (metadata.episodeNumber) props.episodeNumber = metadata.episodeNumber;
  if (metadata.title) props.episodeTitle = metadata.title;
  if (metadata.hookText) props.hookText = metadata.hookText;
  if (metadata.colorScheme) props.colorScheme = metadata.colorScheme;
  if (metadata.waveformStyle) props.waveformStyle = metadata.waveformStyle;

  console.log(`\nRendering ${composition}...`);
  console.log(`  Audio: ${audioPath}`);
  console.log(`  Duration: ${Math.floor(durationSeconds / 60)}m ${Math.floor(durationSeconds % 60)}s`);
  console.log(`  Output: ${outputPath}`);

  return new Promise((resolve, reject) => {
    const args = [
      "remotion",
      "render",
      composition,
      outputPath,
      `--props=${JSON.stringify(props)}`,
      `--frames=0-${durationInFrames - 1}`,
    ];

    const render = spawn("npx", args, {
      stdio: "inherit",
      shell: true,
    });

    render.on("close", (code) => {
      if (code === 0) {
        resolve(outputPath);
      } else {
        reject(new Error(`Render failed with code ${code}`));
      }
    });

    render.on("error", reject);
  });
}

/**
 * Process a new audio file
 */
async function processAudioFile(filepath: string): Promise<void> {
  console.log(`\n${"═".repeat(60)}`);
  console.log(`Processing: ${path.basename(filepath)}`);
  console.log("═".repeat(60));

  // Parse metadata from filename
  let metadata = parseFilename(filepath);
  if (!metadata) {
    console.error("Could not determine metadata from filename. Skipping.");
    return;
  }

  // Override with sidecar JSON if available
  const sidecarData = loadSidecarMetadata(filepath);
  if (sidecarData) {
    console.log("Found sidecar JSON, merging metadata...");
    metadata = { ...metadata, ...sidecarData };
  }

  console.log("Metadata:", JSON.stringify(metadata, null, 2));

  try {
    // Get audio duration
    const duration = await getAudioDuration(filepath);
    console.log(`Audio duration: ${duration.toFixed(2)} seconds`);

    // Ensure output directory exists
    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    // Render the video
    const outputPath = await renderVideo(filepath, metadata, duration);
    console.log(`\n✓ Render complete: ${outputPath}`);

    // Move processed audio to 'processed' subfolder
    const processedDir = path.join(WATCH_DIR, "processed");
    if (!fs.existsSync(processedDir)) {
      fs.mkdirSync(processedDir, { recursive: true });
    }

    const processedPath = path.join(processedDir, path.basename(filepath));
    fs.renameSync(filepath, processedPath);
    console.log(`✓ Moved audio to: ${processedPath}`);

    // Also move sidecar JSON if it exists
    const jsonPath = filepath.replace(path.extname(filepath), ".json");
    if (fs.existsSync(jsonPath)) {
      const processedJsonPath = path.join(processedDir, path.basename(jsonPath));
      fs.renameSync(jsonPath, processedJsonPath);
    }
  } catch (error) {
    console.error("Error processing file:", error);
  }
}

/**
 * Main entry point
 */
function main(): void {
  console.log("═".repeat(60));
  console.log("Audiogram Tools - Watch Folder");
  console.log("═".repeat(60));
  console.log(`Watching: ${path.resolve(WATCH_DIR)}`);
  console.log(`Output:   ${path.resolve(OUTPUT_DIR)}`);
  console.log(`Formats:  ${SUPPORTED_FORMATS.join(", ")}`);
  console.log("═".repeat(60));

  // Ensure watch directory exists
  if (!fs.existsSync(WATCH_DIR)) {
    fs.mkdirSync(WATCH_DIR, { recursive: true });
    console.log(`Created watch directory: ${WATCH_DIR}`);
  }

  // Initialize watcher
  const watcher = chokidar.watch(WATCH_DIR, {
    ignored: [
      /(^|[\/\\])\../, // Ignore dotfiles
      /processed/, // Ignore processed folder
      /\.json$/, // Ignore JSON files (handled with audio)
    ],
    persistent: true,
    ignoreInitial: false, // Process existing files on startup
    awaitWriteFinish: {
      stabilityThreshold: 2000, // Wait for file to finish writing
      pollInterval: 100,
    },
  });

  watcher.on("add", (filepath) => {
    const ext = path.extname(filepath).toLowerCase();
    if (SUPPORTED_FORMATS.includes(ext)) {
      processAudioFile(filepath);
    }
  });

  watcher.on("error", (error) => {
    console.error("Watcher error:", error);
  });

  console.log("\nWaiting for audio files...");
  console.log("Press Ctrl+C to stop.\n");
}

// Run if executed directly
main();
