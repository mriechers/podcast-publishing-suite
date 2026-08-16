import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Background } from "./Background";
import { Waveform, WaveformStyle } from "./Waveform";
import { TextOverlay } from "./TextOverlay";
import { brand, colorSchemes, ColorScheme } from "../brand";

export interface FullEpisodeProps {
  /** Path to the audio file (use staticFile() for public folder, or URL) */
  audioSrc?: string;
  /** Guest name to display */
  guestName?: string;
  /** Episode number */
  episodeNumber?: string | number;
  /** Episode title */
  episodeTitle?: string;
  /** Show logo visibility */
  showLogo?: boolean;
  /** Waveform visualization style */
  waveformStyle?: WaveformStyle;
  /** Color scheme preset */
  colorScheme?: ColorScheme;
  /** Custom background image filename (in public/). Replaces galaxy spiral */
  backgroundImage?: string;
}

/**
 * Full Episode composition for YouTube (16:9 @ 1920x1080)
 *
 * Layout:
 * - Background: Animated galaxy spiral with floating particles
 * - Center: Show logo, episode info, guest name
 * - Bottom: Waveform visualization
 * - Audio: Full episode audio track
 */
export const FullEpisode: React.FC<FullEpisodeProps> = ({
  audioSrc = "",
  guestName = "Guest Name",
  episodeNumber,
  episodeTitle,
  showLogo = true,
  waveformStyle = "mirror",
  colorScheme = "dark",
  backgroundImage,
}) => {
  const colors = colorSchemes[colorScheme];
  const hasAudio = audioSrc && audioSrc.length > 0;

  return (
    <AbsoluteFill>
      {/* Layer 1: Animated Background with Galaxy Spiral */}
      <Background
        useGalaxySpiral={!backgroundImage}
        backgroundImage={backgroundImage}
        primaryColor={colors.primaryColor}
        secondaryColor={colors.secondaryColor}
        accentColor={colors.accentColor}
        rotationSpeed={0.3}
        pulseIntensity={0.4}
      />

      {/* Layer 1.5: Text backdrop for legibility over photos */}
      {backgroundImage && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "70%",
            background:
              "linear-gradient(to bottom, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0.45) 60%, transparent 100%)",
            pointerEvents: "none",
          }}
        />
      )}

      {/* Layer 2: Text Overlays - fade in at start */}
      <Sequence from={0}>
        <TextOverlay
          showLogo={showLogo}
          episodeNumber={episodeNumber}
          guestName={guestName}
          episodeTitle={episodeTitle}
          animateIn={true}
          position="center"
        />
      </Sequence>

      {/* Layer 3: Waveform Visualization */}
      <Waveform
        audioSrc={audioSrc}
        style={waveformStyle}
        color={colors.waveformColor}
        secondaryColor={colors.accentColor}
        barCount={64}
        smoothing={backgroundImage ? 0.5 : 0.8}
        intensity={backgroundImage ? 3 : 1.2}
        position="bottom"
      />

      {/* Layer 4: Audio Track (only if audio provided) */}
      {hasAudio && <Audio src={audioSrc} />}
    </AbsoluteFill>
  );
};

/**
 * Default props for preview in Remotion Studio
 */
export const fullEpisodeDefaultProps: FullEpisodeProps = {
  audioSrc: staticFile("WC_S01_trailer.mp3"),
  guestName: "Dr. Jane Doe",
  episodeNumber: 42,
  episodeTitle: "Exploring the Unknown: A Journey into Wonder",
  showLogo: true,
  waveformStyle: "mirror",
  colorScheme: "dark",
};

export default FullEpisode;
