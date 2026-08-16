/**
 * Render Queue for Batch Processing
 *
 * Manages a queue of render jobs for overnight batch processing.
 * Designed to render hour-long episodes efficiently without blocking.
 *
 * Features:
 * - Queue persistence (survives restarts)
 * - Concurrent render limiting
 * - Progress tracking
 * - Error recovery
 * - Optional YouTube upload after render
 */

import fs from "fs";
import path from "path";
import { spawn, ChildProcess } from "child_process";
import { uploadVideo, generateDescription } from "./youtube-upload";
import { brand } from "../brand";
import "dotenv/config";

// Configuration
const QUEUE_FILE = ".render-queue.json";
const MAX_CONCURRENT = parseInt(process.env.MAX_CONCURRENT_RENDERS || "1", 10);
const OUTPUT_DIR = process.env.OUTPUT_DIR || "./output";

type JobStatus = "pending" | "rendering" | "uploading" | "completed" | "failed";

interface RenderJob {
  id: string;
  audioPath: string;
  outputPath: string;
  composition: string;
  props: Record<string, unknown>;
  durationInFrames: number;
  status: JobStatus;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  uploadToYouTube?: boolean;
  youtubeVideoId?: string;
}

interface QueueState {
  jobs: RenderJob[];
  lastUpdated: string;
}

/**
 * Load queue state from disk
 */
function loadQueue(): QueueState {
  if (fs.existsSync(QUEUE_FILE)) {
    const content = fs.readFileSync(QUEUE_FILE, "utf-8");
    return JSON.parse(content);
  }
  return { jobs: [], lastUpdated: new Date().toISOString() };
}

/**
 * Save queue state to disk
 */
function saveQueue(state: QueueState): void {
  state.lastUpdated = new Date().toISOString();
  fs.writeFileSync(QUEUE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Generate unique job ID
 */
function generateJobId(): string {
  return `job_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
}

/**
 * Add a new job to the queue
 */
export function addJob(options: {
  audioPath: string;
  composition: string;
  props: Record<string, unknown>;
  durationSeconds: number;
  uploadToYouTube?: boolean;
}): RenderJob {
  const state = loadQueue();

  const fps = 30;
  const durationInFrames = Math.ceil(options.durationSeconds * fps);

  // Generate output filename
  const guestName = (options.props.guestName as string) || "Unknown";
  const safeName = guestName.replace(/[^a-zA-Z0-9]/g, "-");
  const timestamp = new Date().toISOString().slice(0, 10);
  const isEpisode = options.composition === "FullEpisode" || options.composition.endsWith("-Horizontal");
  const episodeNum = options.props.episodeNumber;

  let outputFilename: string;
  if (isEpisode && episodeNum) {
    outputFilename = `EP${episodeNum}_${safeName}_${timestamp}.mp4`;
  } else if (isEpisode) {
    outputFilename = `Episode_${safeName}_${timestamp}.mp4`;
  } else {
    outputFilename = `Clip_${safeName}_${timestamp}.mp4`;
  }

  const job: RenderJob = {
    id: generateJobId(),
    audioPath: path.resolve(options.audioPath),
    outputPath: path.join(OUTPUT_DIR, outputFilename),
    composition: options.composition,
    props: options.props,
    durationInFrames,
    status: "pending",
    createdAt: new Date().toISOString(),
    uploadToYouTube: options.uploadToYouTube,
  };

  state.jobs.push(job);
  saveQueue(state);

  console.log(`Added job to queue: ${job.id}`);
  console.log(`  Composition: ${job.composition}`);
  console.log(`  Duration: ${Math.floor(options.durationSeconds / 60)}m ${Math.floor(options.durationSeconds % 60)}s`);
  console.log(`  Output: ${job.outputPath}`);

  return job;
}

/**
 * Get queue status
 */
export function getQueueStatus(): {
  pending: number;
  rendering: number;
  completed: number;
  failed: number;
  jobs: RenderJob[];
} {
  const state = loadQueue();
  return {
    pending: state.jobs.filter((j) => j.status === "pending").length,
    rendering: state.jobs.filter((j) => j.status === "rendering").length,
    completed: state.jobs.filter((j) => j.status === "completed").length,
    failed: state.jobs.filter((j) => j.status === "failed").length,
    jobs: state.jobs,
  };
}

/**
 * Clear completed and failed jobs from queue
 */
export function clearFinishedJobs(): number {
  const state = loadQueue();
  const initialCount = state.jobs.length;
  state.jobs = state.jobs.filter(
    (j) => j.status !== "completed" && j.status !== "failed"
  );
  saveQueue(state);
  return initialCount - state.jobs.length;
}

/**
 * Update job status
 */
function updateJobStatus(
  jobId: string,
  updates: Partial<RenderJob>
): void {
  const state = loadQueue();
  const job = state.jobs.find((j) => j.id === jobId);
  if (job) {
    Object.assign(job, updates);
    saveQueue(state);
  }
}

/**
 * Render a single job
 */
async function renderJob(job: RenderJob): Promise<void> {
  console.log(`\n${"═".repeat(60)}`);
  console.log(`Starting render: ${job.id}`);
  console.log("═".repeat(60));

  updateJobStatus(job.id, {
    status: "rendering",
    startedAt: new Date().toISOString(),
  });

  // Ensure output directory exists
  const outputDir = path.dirname(job.outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Prepare props with audio source
  const props = {
    ...job.props,
    audioSrc: job.audioPath,
  };

  return new Promise((resolve, reject) => {
    const args = [
      "remotion",
      "render",
      job.composition,
      job.outputPath,
      `--props=${JSON.stringify(props)}`,
      `--frames=0-${job.durationInFrames - 1}`,
      "--log=verbose",
    ];

    console.log(`Running: npx ${args.join(" ")}`);

    const render = spawn("npx", args, {
      stdio: "inherit",
      shell: true,
    });

    render.on("close", async (code) => {
      if (code === 0) {
        console.log(`\n✓ Render complete: ${job.outputPath}`);

        // Upload to YouTube if requested
        if (job.uploadToYouTube) {
          updateJobStatus(job.id, { status: "uploading" });

          try {
            const guestName = (job.props.guestName as string) || "Unknown";
            const episodeNum = job.props.episodeNumber;
            const title = job.props.episodeTitle as string | undefined;

            let videoTitle: string;
            if (episodeNum && title) {
              videoTitle = `Episode ${episodeNum}: ${title} | ${brand.show.name}`;
            } else if (episodeNum) {
              videoTitle = `Episode ${episodeNum}: ${guestName} | ${brand.show.name}`;
            } else {
              videoTitle = `${guestName} | ${brand.show.name}`;
            }

            const result = await uploadVideo({
              videoPath: job.outputPath,
              title: videoTitle,
              description: generateDescription({
                guestName,
                episodeNumber: episodeNum as number | undefined,
                title,
              }),
              tags: [brand.show.name, "podcast"],
              privacyStatus: "private",
            });

            updateJobStatus(job.id, {
              status: "completed",
              completedAt: new Date().toISOString(),
              youtubeVideoId: result.videoId,
            });

            console.log(`✓ Uploaded to YouTube: ${result.videoUrl}`);
          } catch (uploadError) {
            console.error("YouTube upload failed:", uploadError);
            // Still mark as completed since render succeeded
            updateJobStatus(job.id, {
              status: "completed",
              completedAt: new Date().toISOString(),
              error: `Upload failed: ${uploadError}`,
            });
          }
        } else {
          updateJobStatus(job.id, {
            status: "completed",
            completedAt: new Date().toISOString(),
          });
        }

        resolve();
      } else {
        const error = `Render failed with code ${code}`;
        console.error(`\n✗ ${error}`);
        updateJobStatus(job.id, {
          status: "failed",
          completedAt: new Date().toISOString(),
          error,
        });
        reject(new Error(error));
      }
    });

    render.on("error", (err) => {
      console.error("Render process error:", err);
      updateJobStatus(job.id, {
        status: "failed",
        completedAt: new Date().toISOString(),
        error: err.message,
      });
      reject(err);
    });
  });
}

/**
 * Process the render queue
 */
export async function processQueue(): Promise<void> {
  const state = loadQueue();

  // Reset any jobs that were rendering (interrupted)
  state.jobs.forEach((job) => {
    if (job.status === "rendering" || job.status === "uploading") {
      job.status = "pending";
      job.startedAt = undefined;
    }
  });
  saveQueue(state);

  console.log("═".repeat(60));
  console.log("Audiogram Tools - Render Queue");
  console.log("═".repeat(60));

  const status = getQueueStatus();
  console.log(`Pending: ${status.pending}`);
  console.log(`Completed: ${status.completed}`);
  console.log(`Failed: ${status.failed}`);
  console.log(`Max Concurrent: ${MAX_CONCURRENT}`);
  console.log("═".repeat(60));

  if (status.pending === 0) {
    console.log("\nNo pending jobs in queue.");
    return;
  }

  console.log(`\nProcessing ${status.pending} jobs...`);

  // Process jobs one at a time (for hour-long videos, parallel isn't practical)
  const pendingJobs = state.jobs.filter((j) => j.status === "pending");

  for (const job of pendingJobs) {
    try {
      await renderJob(job);
    } catch (error) {
      console.error(`Job ${job.id} failed:`, error);
      // Continue with next job
    }
  }

  const finalStatus = getQueueStatus();
  console.log("\n" + "═".repeat(60));
  console.log("Queue processing complete");
  console.log("═".repeat(60));
  console.log(`Completed: ${finalStatus.completed}`);
  console.log(`Failed: ${finalStatus.failed}`);
}

/**
 * CLI entry point
 */
async function main(): Promise<void> {
  const command = process.argv[2];

  switch (command) {
    case "status":
      const status = getQueueStatus();
      console.log("Queue Status:");
      console.log(JSON.stringify(status, null, 2));
      break;

    case "clear":
      const cleared = clearFinishedJobs();
      console.log(`Cleared ${cleared} finished jobs from queue.`);
      break;

    case "process":
    case "run":
      await processQueue();
      break;

    default:
      console.log("Usage:");
      console.log("  npx ts-node render-queue.ts status   - Show queue status");
      console.log("  npx ts-node render-queue.ts process  - Process pending jobs");
      console.log("  npx ts-node render-queue.ts clear    - Clear finished jobs");
      console.log("");
      console.log("Or import and use programmatically:");
      console.log("  import { addJob, processQueue } from './render-queue';");
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}
