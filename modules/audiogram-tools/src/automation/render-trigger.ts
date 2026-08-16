/**
 * Render Trigger - Main Orchestration Script
 *
 * Provides a simple interface to render videos from audio files.
 * Can be used standalone or integrated with the watch folder system.
 *
 * Usage:
 *   npx ts-node render-trigger.ts <audio-file> [options]
 *
 * Options:
 *   --episode       Render as full episode (16:9)
 *   --clip          Render as social clip (9:16)
 *   --guest <name>  Guest name
 *   --ep <number>   Episode number
 *   --title <text>  Episode title
 *   --hook <text>   Hook text for clips
 *   --upload        Upload to YouTube after render
 *   --queue         Add to queue instead of rendering immediately
 */

import fs from "fs";
import os from "os";
import path from "path";
import { spawn } from "child_process";
import { addJob, processQueue } from "./render-queue";
import "dotenv/config";

const OUTPUT_DIR = process.env.OUTPUT_DIR || "./output";

interface RenderOptions {
  audioPath: string;
  type: "episode" | "clip";
  guestName: string;
  episodeNumber?: number;
  episodeTitle?: string;
  hookText?: string;
  colorScheme?: "dark" | "green" | "warm";
  waveformStyle?: "mirror" | "bars" | "circle" | "line";
  uploadToYouTube?: boolean;
  addToQueue?: boolean;
  showSlug?: string;
  episodeArtPath?: string;
}

/**
 * Get audio duration using ffprobe
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
        resolve(parseFloat(output.trim()));
      } else {
        reject(new Error(`ffprobe exited with code ${code}`));
      }
    });

    ffprobe.on("error", reject);
  });
}

/**
 * Maps show slugs to their Remotion composition ID prefix.
 * Must match the composition IDs registered in Root.tsx.
 */
const SHOW_COMPOSITION_PREFIX: Record<string, string> = {
  "wonder-cabinet": "WC",
};

/**
 * Get the Remotion composition ID based on render options.
 * When --show is provided, looks up the composition prefix for the slug
 * and appends -Horizontal or -Vertical.
 */
function getCompositionId(options: RenderOptions): string {
  if (options.showSlug) {
    const prefix = SHOW_COMPOSITION_PREFIX[options.showSlug];
    if (!prefix) {
      throw new Error(
        `Unknown show slug "${options.showSlug}". Known shows: ${Object.keys(SHOW_COMPOSITION_PREFIX).join(", ")}`
      );
    }
    return options.type === "episode"
      ? `${prefix}-Horizontal`
      : `${prefix}-Vertical`;
  }
  return options.type === "episode" ? "FullEpisode" : "SocialClip";
}

/**
 * Render video directly (not using queue)
 */
async function renderDirect(
  options: RenderOptions,
  durationSeconds: number
): Promise<string> {
  const fps = 30;
  const durationInFrames = Math.ceil(durationSeconds * fps);

  const composition = getCompositionId(options);
  const timestamp = new Date().toISOString().slice(0, 10);
  const safeName = options.guestName.replace(/[^a-zA-Z0-9]/g, "-");

  let outputFilename: string;
  if (options.type === "episode" && options.episodeNumber) {
    outputFilename = `EP${options.episodeNumber}_${safeName}_${timestamp}.mp4`;
  } else if (options.type === "episode") {
    outputFilename = `Episode_${safeName}_${timestamp}.mp4`;
  } else {
    outputFilename = `Clip_${safeName}_${timestamp}.mp4`;
  }

  const outputPath = path.join(OUTPUT_DIR, outputFilename);

  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const publicDir = path.join(__dirname, "../../public");
  if (!fs.existsSync(publicDir)) {
    fs.mkdirSync(publicDir, { recursive: true });
  }

  // Track files copied into public/ so we can clean them up after render.
  const publicCopies: string[] = [];

  // Audio: Remotion <Audio src={...}> needs a staticFile()-resolvable filename.
  // Copy (or hardlink-fallback to copy) the source audio into public/.
  const resolvedAudio = path.resolve(options.audioPath);
  const audioFilename = `episode-audio-${Date.now()}${path.extname(options.audioPath)}`;
  const audioInPublic = path.join(publicDir, audioFilename);
  fs.copyFileSync(resolvedAudio, audioInPublic);
  publicCopies.push(audioInPublic);

  // Build props. durationInFrames is passed so the WC-Horizontal/Vertical
  // compositions can override their default 60s duration via calculateMetadata.
  const props: Record<string, unknown> = {
    audioSrc: audioFilename,
    guestName: options.guestName,
    durationInFrames,
  };

  if (options.episodeNumber) props.episodeNumber = options.episodeNumber;
  if (options.episodeTitle) props.episodeTitle = options.episodeTitle;
  if (options.hookText) props.hookText = options.hookText;
  if (options.colorScheme) props.colorScheme = options.colorScheme;
  if (options.waveformStyle) props.waveformStyle = options.waveformStyle;
  if (options.episodeArtPath) {
    // Validate art file exists before copying
    const resolvedArt = path.resolve(options.episodeArtPath);
    if (!fs.existsSync(resolvedArt)) {
      throw new Error(`Episode art file not found: ${resolvedArt} (from --art flag)`);
    }
    // Copy to public/ so Remotion can serve it via staticFile()
    const artFilename = `episode-art-${Date.now()}${path.extname(options.episodeArtPath)}`;
    const artInPublic = path.join(publicDir, artFilename);
    fs.copyFileSync(resolvedArt, artInPublic);
    publicCopies.push(artInPublic);
    props.episodeArtSrc = artFilename;
  }

  console.log("\n" + "═".repeat(60));
  console.log("Audiogram Tools - Video Render");
  console.log("═".repeat(60));
  console.log(`Composition: ${composition}`);
  console.log(`Audio: ${options.audioPath}`);
  console.log(`Duration: ${Math.floor(durationSeconds / 60)}m ${Math.floor(durationSeconds % 60)}s`);
  console.log(`Output: ${outputPath}`);
  console.log("═".repeat(60));

  // Write props to a temp JSON file rather than passing as a CLI string.
  // shell-tokenization mangles JSON quotes/braces; --props=<file> avoids it.
  const propsFile = path.join(os.tmpdir(), `remotion-props-${Date.now()}.json`);
  fs.writeFileSync(propsFile, JSON.stringify(props));

  return new Promise((resolve, reject) => {
    const args = [
      "remotion",
      "render",
      composition,
      outputPath,
      `--props=${propsFile}`,
    ];

    if (process.env.REMOTION_CONCURRENCY) {
      args.push(`--concurrency=${process.env.REMOTION_CONCURRENCY}`);
    }
    if (process.env.REMOTION_TIMEOUT) {
      args.push(`--timeout=${process.env.REMOTION_TIMEOUT}`);
    }

    const render = spawn("npx", args, {
      stdio: "inherit",
    });

    const cleanup = () => {
      try { fs.unlinkSync(propsFile); } catch {}
      for (const f of publicCopies) {
        try { fs.unlinkSync(f); } catch {}
      }
    };

    render.on("close", (code) => {
      cleanup();
      if (code === 0) {
        resolve(outputPath);
      } else {
        reject(new Error(`Render failed with code ${code}`));
      }
    });

    render.on("error", (err) => {
      cleanup();
      reject(err);
    });
  });
}

/**
 * Parse command line arguments
 */
function parseArgs(): RenderOptions {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    console.log(`
Audiogram Tools - Video Render

Usage:
  npx ts-node render-trigger.ts <audio-file> [options]

Options:
  --episode         Render as full episode (16:9) [default]
  --clip            Render as social clip (9:16)
  --guest <name>    Guest name [required]
  --ep <number>     Episode number
  --title <text>    Episode title
  --hook <text>     Hook text (for clips)
  --scheme <name>   Color scheme: dark, green, warm [default: dark]
  --waveform <type> Waveform style: mirror, bars, circle, line
  --upload          Upload to YouTube after render
  --queue           Add to queue instead of immediate render
  --show <slug>     Use show-specific template (e.g. wonder-cabinet)
  --art <path>      Episode art image path (for template compositions)

Examples:
  npx ts-node render-trigger.ts audio.mp3 --guest "Jane Doe" --ep 42 --title "The Big Idea"
  npx ts-node render-trigger.ts clip.mp3 --clip --guest "Jane Doe" --hook "This changed everything"
  npx ts-node render-trigger.ts audio.mp3 --guest "Jane Doe" --queue --upload
`);
    process.exit(0);
  }

  const audioPath = args[0];

  if (!fs.existsSync(audioPath)) {
    console.error(`Error: Audio file not found: ${audioPath}`);
    process.exit(1);
  }

  const options: RenderOptions = {
    audioPath,
    type: "episode",
    guestName: "Guest",
  };

  for (let i = 1; i < args.length; i++) {
    const arg = args[i];

    switch (arg) {
      case "--episode":
        options.type = "episode";
        break;
      case "--clip":
        options.type = "clip";
        break;
      case "--guest":
        options.guestName = args[++i];
        break;
      case "--ep":
        options.episodeNumber = parseInt(args[++i], 10);
        break;
      case "--title":
        options.episodeTitle = args[++i];
        break;
      case "--hook":
        options.hookText = args[++i];
        break;
      case "--scheme":
        options.colorScheme = args[++i] as "dark" | "green" | "warm";
        break;
      case "--waveform":
        options.waveformStyle = args[++i] as "mirror" | "bars" | "circle" | "line";
        break;
      case "--upload":
        options.uploadToYouTube = true;
        break;
      case "--queue":
        options.addToQueue = true;
        break;
      case "--show":
        if (!args[i + 1] || args[i + 1].startsWith("--")) {
          console.error("Error: --show requires a show slug (e.g. --show wonder-cabinet)");
          process.exit(1);
        }
        options.showSlug = args[++i];
        break;
      case "--art":
        if (!args[i + 1] || args[i + 1].startsWith("--")) {
          console.error("Error: --art requires a file path (e.g. --art episode-art.jpg)");
          process.exit(1);
        }
        options.episodeArtPath = args[++i];
        break;
    }
  }

  return options;
}

/**
 * Main entry point
 */
async function main(): Promise<void> {
  const options = parseArgs();

  try {
    // Get audio duration
    console.log("Analyzing audio...");
    const duration = await getAudioDuration(options.audioPath);
    console.log(`Duration: ${duration.toFixed(2)} seconds`);

    // Build props object
    const props: Record<string, unknown> = {
      guestName: options.guestName,
    };

    if (options.episodeNumber) props.episodeNumber = options.episodeNumber;
    if (options.episodeTitle) props.episodeTitle = options.episodeTitle;
    if (options.hookText) props.hookText = options.hookText;
    if (options.colorScheme) props.colorScheme = options.colorScheme;
    if (options.waveformStyle) props.waveformStyle = options.waveformStyle;

    if (options.addToQueue) {
      // Add to queue for later processing
      const job = addJob({
        audioPath: options.audioPath,
        composition: getCompositionId(options),
        props,
        durationSeconds: duration,
        uploadToYouTube: options.uploadToYouTube,
      });

      console.log(`\n✓ Job added to queue: ${job.id}`);
      console.log("Run 'npm run render:all' to process the queue.");
    } else {
      // Render immediately
      const outputPath = await renderDirect(options, duration);
      console.log(`\n✓ Render complete: ${outputPath}`);

      // Upload if requested
      if (options.uploadToYouTube) {
        console.log("\nUpload to YouTube requested but not implemented in direct mode.");
        console.log("Use --queue flag for YouTube upload support.");
      }
    }
  } catch (error) {
    console.error("Error:", error);
    process.exit(1);
  }
}

// Run if executed directly
main();
