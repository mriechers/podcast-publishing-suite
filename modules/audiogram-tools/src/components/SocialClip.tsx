import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Background } from "./Background";
import { Waveform, WaveformStyle } from "./Waveform";
import { SocialTextOverlay } from "./TextOverlay";
import { brand, colorSchemes, ColorScheme } from "../brand";

export interface SocialClipProps {
  /** Path to the audio file (use staticFile() for public folder, or URL) */
  audioSrc?: string;
  /** Guest name to display */
  guestName?: string;
  /** Hook text / quote to display (optional) */
  hookText?: string;
  /** Show logo */
  showLogo?: boolean;
  /** Waveform visualization style */
  waveformStyle?: WaveformStyle;
  /** Color scheme preset */
  colorScheme?: ColorScheme;
  /** Position of text overlay */
  textPosition?: "top" | "center" | "bottom";
  /** Custom background image filename (in public/). Replaces galaxy spiral */
  backgroundImage?: string;
}

/**
 * Social Clip composition for TikTok/Reels/Shorts (9:16 @ 1080x1920)
 *
 * Layout optimized for vertical viewing:
 * - Background: Animated galaxy spiral (adapted for vertical)
 * - Top: Show logo, guest name, optional hook text
 * - Center: Large waveform visualization
 * - Audio: Clip audio track
 *
 * Key differences from FullEpisode:
 * - Vertical aspect ratio (9:16)
 * - Larger, centered waveform
 * - Simplified text (no episode number/title)
 * - Optional hook text for engagement
 */
export const SocialClip: React.FC<SocialClipProps> = ({
  audioSrc = "",
  guestName = "Guest Name",
  hookText,
  showLogo = true,
  waveformStyle = "circle",
  colorScheme = "dark",
  textPosition = "top",
  backgroundImage,
}) => {
  const colors = colorSchemes[colorScheme];
  const hasAudio = audioSrc && audioSrc.length > 0;

  return (
    <AbsoluteFill>
      {/* Layer 1: Animated Background */}
      <Background
        useGalaxySpiral={!backgroundImage}
        backgroundImage={backgroundImage}
        primaryColor={colors.primaryColor}
        secondaryColor={colors.secondaryColor}
        accentColor={colors.accentColor}
        rotationSpeed={0.4}
        pulseIntensity={0.5}
      />

      {/* Layer 2: Text Overlay - simplified for social */}
      <Sequence from={0}>
        <SocialTextOverlay
          guestName={guestName}
          hookText={hookText}
          showLogo={showLogo}
          position={textPosition}
        />
      </Sequence>

      {/* Layer 3: Waveform Visualization - centered and prominent */}
      <Waveform
        audioSrc={audioSrc}
        style={waveformStyle}
        color={colors.waveformColor}
        secondaryColor={colors.accentColor}
        barCount={48}
        smoothing={0.75}
        intensity={1.5}
        position="center"
      />

      {/* Layer 4: Audio Track (only if audio provided) */}
      {hasAudio && <Audio src={audioSrc} />}
    </AbsoluteFill>
  );
};

/**
 * Default props for preview in Remotion Studio
 */
export const socialClipDefaultProps: SocialClipProps = {
  audioSrc: staticFile("WC_S01_trailer.mp3"),
  guestName: "Dr. Jane Doe",
  hookText: "This changed everything for me...",
  showLogo: true,
  waveformStyle: "circle",
  colorScheme: "dark",
  textPosition: "top",
};

export default SocialClip;
