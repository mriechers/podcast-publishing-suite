import React from "react";
import { Composition, staticFile } from "remotion";
import { z } from "zod";
import { FullEpisode } from "./components/FullEpisode";
import { SocialClip } from "./components/SocialClip";
import { OriginalTemplate } from "./components/OriginalTemplate";
import { Thumbnail } from "./components/Thumbnail";
import { ShowTemplate, ShowTemplateProps } from "./template/ShowTemplate";
import { OrientationSchema } from "./template/types";
import "./fonts.css";

// Schema definitions for type-safe props
const waveformStyleSchema = z.enum(["bars", "mirror", "circle", "line"]);
const colorSchemeSchema = z.enum(["dark", "green", "warm"]);

const fullEpisodeSchema = z.object({
  audioSrc: z.string(),
  guestName: z.string().optional(),
  episodeNumber: z.union([z.string(), z.number()]).optional(),
  episodeTitle: z.string().optional(),
  showLogo: z.boolean().optional(),
  waveformStyle: waveformStyleSchema.optional(),
  colorScheme: colorSchemeSchema.optional(),
  backgroundImage: z.string().optional(),
});

const socialClipSchema = z.object({
  audioSrc: z.string(),
  guestName: z.string().optional(),
  hookText: z.string().optional(),
  showLogo: z.boolean().optional(),
  waveformStyle: waveformStyleSchema.optional(),
  colorScheme: colorSchemeSchema.optional(),
  textPosition: z.enum(["top", "center", "bottom"]).optional(),
  backgroundImage: z.string().optional(),
});

// Default props
const fullEpisodeDefaultProps = {
  audioSrc: staticFile("WC_S01_trailer.mp3"),
  guestName: "Dr. Jane Doe",
  episodeNumber: 42,
  episodeTitle: "Exploring the Unknown: A Journey into Wonder",
  showLogo: true,
  waveformStyle: "mirror" as const,
  colorScheme: "dark" as const,
};

const socialClipDefaultProps = {
  audioSrc: staticFile("WC_S01_trailer.mp3"),
  guestName: "Dr. Jane Doe",
  hookText: "This changed everything for me...",
  showLogo: true,
  waveformStyle: "circle" as const,
  colorScheme: "dark" as const,
  textPosition: "top" as const,
};

// Original AE Template schema
const originalTemplateSchema = z.object({
  audioSrc: z.string().optional(),
  rotationSpeed: z.number().optional(),
});

const originalTemplateDefaultProps = {
  audioSrc: staticFile("WC_S01_trailer.mp3"),
  rotationSpeed: 36,
};

const showTemplateSchema = z.object({
  templateConfig: OrientationSchema,
  audioSrc: z.string().optional(),
  episodeArtSrc: z.string().optional(),
  durationInFrames: z.number().int().positive().optional(),
});

// WC horizontal template config (from shows/wonder-cabinet/video-template/template.json)
const wcHorizontalConfig = {
  width: 1920,
  height: 1080,
  layers: [
    { type: "solid" as const, color: "#10a544", grain: true },
    { type: "spiral" as const, asset: "bg-galaxy-spiral-1200w@2x.png", rotationSpeed: -0.5, opacity: 1.0 },
    { type: "cabinet-frame" as const, asset: "logo-primary-dark-bg-800w.png", artClip: true },
    { type: "title-image" as const, asset: "WonderCabinet-title.png", layout: "flanking" as const, leftAsset: "wonder.png", rightAsset: "cabinet.png" },
  ],
};

const wcVerticalConfig = {
  width: 1080,
  height: 1920,
  layers: [
    { type: "solid" as const, color: "#10a544", grain: true },
    { type: "spiral" as const, asset: "bg-galaxy-spiral-1200w@2x.png", rotationSpeed: -0.5, opacity: 1.0 },
    { type: "cabinet-frame" as const, asset: "logo-primary-dark-bg-800w.png", artClip: true },
    { type: "title-image" as const, asset: "WonderCabinet-title.png", layout: "stacked" as const },
  ],
};

/**
 * Root component that registers all podcast video compositions.
 *
 * Compositions:
 * - FullEpisode: 16:9 @ 1920x1080 for YouTube
 * - SocialClip: 9:16 @ 1080x1920 for TikTok/Reels/Shorts
 *
 * Usage:
 * - Preview: npx remotion studio
 * - Render: npx remotion render FullEpisode out/video.mp4 --props='{"audioSrc": "..."}'
 */
export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* ═══════════════════════════════════════════════════════════════
          FULL EPISODE - 16:9 for YouTube
          ═══════════════════════════════════════════════════════════════ */}
      <Composition
        id="FullEpisode"
        component={FullEpisode}
        schema={fullEpisodeSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={fullEpisodeDefaultProps}
      />

      <Composition
        id="FullEpisode-Bars"
        component={FullEpisode}
        schema={fullEpisodeSchema}
        durationInFrames={30 * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          ...fullEpisodeDefaultProps,
          waveformStyle: "bars" as const,
        }}
      />

      <Composition
        id="FullEpisode-Line"
        component={FullEpisode}
        schema={fullEpisodeSchema}
        durationInFrames={30 * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          ...fullEpisodeDefaultProps,
          waveformStyle: "line" as const,
        }}
      />

      <Composition
        id="FullEpisode-Green"
        component={FullEpisode}
        schema={fullEpisodeSchema}
        durationInFrames={30 * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          ...fullEpisodeDefaultProps,
          colorScheme: "green" as const,
        }}
      />

      {/* ═══════════════════════════════════════════════════════════════
          SOCIAL CLIP - 9:16 for TikTok/Reels/Shorts
          ═══════════════════════════════════════════════════════════════ */}
      <Composition
        id="SocialClip"
        component={SocialClip}
        schema={socialClipSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={socialClipDefaultProps}
      />

      <Composition
        id="SocialClip-Mirror"
        component={SocialClip}
        schema={socialClipSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          ...socialClipDefaultProps,
          waveformStyle: "mirror" as const,
        }}
      />

      <Composition
        id="SocialClip-Bars"
        component={SocialClip}
        schema={socialClipSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          ...socialClipDefaultProps,
          waveformStyle: "bars" as const,
          textPosition: "bottom" as const,
        }}
      />

      <Composition
        id="SocialClip-Green"
        component={SocialClip}
        schema={socialClipSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          ...socialClipDefaultProps,
          colorScheme: "green" as const,
        }}
      />

      {/* ═══════════════════════════════════════════════════════════════
          ONE-OFF: Sun Salutation bonus episode
          ═══════════════════════════════════════════════════════════════ */}
      <Composition
        id="SunSalutation"
        component={FullEpisode}
        schema={fullEpisodeSchema}
        durationInFrames={6283}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          audioSrc: staticFile("sun-salutation.mp3"),
          guestName: "Marcelo Gleiser",
          episodeNumber: "Bonus",
          episodeTitle: "A Sun Salutation on the Island of Knowledge",
          showLogo: true,
          waveformStyle: "bars" as const,
          colorScheme: "dark" as const,
          backgroundImage: "sun-salutation-art.jpeg",
        }}
      />

      {/* ═══════════════════════════════════════════════════════════════
          ORIGINAL AE TEMPLATE - 1:1 Recreation
          ═══════════════════════════════════════════════════════════════ */}
      <Composition
        id="OriginalTemplate"
        component={OriginalTemplate}
        schema={originalTemplateSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={originalTemplateDefaultProps}
      />
      {/* ═══════════════════════════════════════════════════════════════
          THUMBNAIL: Sun Salutation
          ═══════════════════════════════════════════════════════════════ */}
      <Composition
        id="SunSalutation-Thumb"
        component={Thumbnail}
        schema={z.object({
          guestName: z.string().optional(),
          episodeNumber: z.union([z.string(), z.number()]).optional(),
          episodeTitle: z.string().optional(),
          showLogo: z.boolean().optional(),
          backgroundImage: z.string().optional(),
        })}
        durationInFrames={1}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          guestName: "Sun Salutation",
          showLogo: true,
          backgroundImage: "sun-salutation-art.jpeg",
        }}
      />

      {/* ═══════════════════════════════════════════════════════════════
          WC SHOW TEMPLATE - Data-driven from template.json
          ═══════════════════════════════════════════════════════════════ */}
      <Composition
        id="WC-Horizontal"
        component={ShowTemplate as React.FC<ShowTemplateProps & Record<string, unknown>>}
        schema={showTemplateSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          templateConfig: wcHorizontalConfig,
          audioSrc: staticFile("WC_S01_trailer.mp3"),
          episodeArtSrc: "",
        }}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames ?? 30 * 60,
        })}
      />

      <Composition
        id="WC-Vertical"
        component={ShowTemplate as React.FC<ShowTemplateProps & Record<string, unknown>>}
        schema={showTemplateSchema}
        durationInFrames={30 * 60}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          templateConfig: wcVerticalConfig,
          audioSrc: staticFile("WC_S01_trailer.mp3"),
          episodeArtSrc: "",
        }}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames ?? 30 * 60,
        })}
      />

      {/* ═══════════════════════════════════════════════════════════════
          WC THUMBNAIL - 1280×720 static still for YouTube thumbnails
          ═══════════════════════════════════════════════════════════════ */}
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
    </>
  );
};

export default RemotionRoot;
