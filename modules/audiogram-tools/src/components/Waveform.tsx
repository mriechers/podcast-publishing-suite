import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Audio,
  Sequence,
} from "remotion";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";

export type WaveformStyle = "bars" | "mirror" | "circle" | "line";

interface WaveformProps {
  audioSrc: string;
  style?: WaveformStyle;
  color?: string;
  secondaryColor?: string;
  barCount?: number;
  smoothing?: number;
  intensity?: number;
  position?: "bottom" | "center" | "top";
}

/**
 * Audio waveform visualization component.
 * Supports multiple visual styles and is responsive to aspect ratio.
 */
export const Waveform: React.FC<WaveformProps> = ({
  audioSrc,
  style = "mirror",
  color = "#e94560",
  secondaryColor = "#0f3460",
  barCount = 64,
  smoothing = 0.8,
  intensity = 1,
  position = "bottom",
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const isVertical = height > width;

  // Check if we have a valid audio source
  const hasAudio = Boolean(audioSrc && audioSrc.length > 0);

  // Always call useAudioData (hooks must be called unconditionally)
  // Pass a placeholder URL when no audio - the hook will handle the error gracefully
  const audioData = useAudioData(audioSrc || "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");

  // Generate visualization
  let visualization: number[];

  if (!hasAudio || !audioData) {
    // Generate animated placeholder bars based on frame
    visualization = Array.from({ length: barCount }, (_, i) => {
      const phase = (frame / 30 + i / barCount) * Math.PI * 2;
      return 0.3 + Math.sin(phase) * 0.2 + Math.sin(phase * 2.5) * 0.1;
    });
  } else {
    const raw = visualizeAudio({
      fps,
      frame,
      audioData,
      numberOfSamples: barCount,
      smoothing: smoothing >= 0.5,
      optimizeFor: "accuracy",
    });

    // Compensate for frequency rolloff — speech/music energy is concentrated
    // in low bins, so higher bins need proportionally more boost to look balanced
    visualization = raw.map((v, i) => {
      const freqBoost = 1 + (i / raw.length) * 5;
      return Math.min(1, v * freqBoost);
    });
  }

  // Calculate dimensions based on aspect ratio
  const containerHeight = isVertical ? height * 0.25 : height * 0.2;
  const containerWidth = isVertical ? width * 0.9 : width * 0.7;

  // Position calculations
  const getTopPosition = () => {
    switch (position) {
      case "top":
        return isVertical ? height * 0.15 : height * 0.1;
      case "center":
        return (height - containerHeight) / 2;
      case "bottom":
      default:
        return isVertical ? height * 0.65 : height * 0.75;
    }
  };

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    left: (width - containerWidth) / 2,
    top: getTopPosition(),
    width: containerWidth,
    height: containerHeight,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  };

  return (
    <div style={containerStyle}>
      {style === "bars" && (
        <BarsWaveform
          visualization={visualization}
          color={color}
          width={containerWidth}
          height={containerHeight}
          intensity={intensity}
        />
      )}
      {style === "mirror" && (
        <MirrorWaveform
          visualization={visualization}
          color={color}
          secondaryColor={secondaryColor}
          width={containerWidth}
          height={containerHeight}
          intensity={intensity}
        />
      )}
      {style === "circle" && (
        <CircleWaveform
          visualization={visualization}
          color={color}
          size={Math.min(containerWidth, containerHeight) * 0.8}
          intensity={intensity}
        />
      )}
      {style === "line" && (
        <LineWaveform
          visualization={visualization}
          color={color}
          width={containerWidth}
          height={containerHeight}
          intensity={intensity}
        />
      )}
    </div>
  );
};

interface WaveformVisualizationProps {
  visualization: number[];
  color: string;
  width: number;
  height: number;
  intensity: number;
}

const BarsWaveform: React.FC<WaveformVisualizationProps> = ({
  visualization,
  color,
  width,
  height,
  intensity,
}) => {
  const barWidth = width / visualization.length;
  const gap = barWidth * 0.2;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        gap: gap,
      }}
    >
      {visualization.map((amplitude, index) => {
        const barHeight = Math.max(4, amplitude * height * intensity);
        return (
          <div
            key={index}
            style={{
              width: barWidth - gap,
              height: barHeight,
              backgroundColor: color,
              borderRadius: (barWidth - gap) / 2,
              transition: "height 0.05s ease-out",
            }}
          />
        );
      })}
    </div>
  );
};

interface MirrorWaveformProps extends WaveformVisualizationProps {
  secondaryColor: string;
}

const MirrorWaveform: React.FC<MirrorWaveformProps> = ({
  visualization,
  color,
  secondaryColor,
  width,
  height,
  intensity,
}) => {
  const barWidth = width / visualization.length;
  const gap = barWidth * 0.15;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        gap: gap,
      }}
    >
      {visualization.map((amplitude, index) => {
        const barHeight = Math.max(4, amplitude * (height / 2) * intensity);
        return (
          <div
            key={index}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 2,
            }}
          >
            {/* Top bar (mirrored) */}
            <div
              style={{
                width: barWidth - gap,
                height: barHeight,
                background: `linear-gradient(to top, ${color}, ${secondaryColor})`,
                borderRadius: (barWidth - gap) / 2,
                transform: "scaleY(-1)",
              }}
            />
            {/* Bottom bar */}
            <div
              style={{
                width: barWidth - gap,
                height: barHeight,
                background: `linear-gradient(to bottom, ${color}, ${secondaryColor})`,
                borderRadius: (barWidth - gap) / 2,
              }}
            />
          </div>
        );
      })}
    </div>
  );
};

interface CircleWaveformProps {
  visualization: number[];
  color: string;
  size: number;
  intensity: number;
}

const CircleWaveform: React.FC<CircleWaveformProps> = ({
  visualization,
  color,
  size,
  intensity,
}) => {
  const centerX = size / 2;
  const centerY = size / 2;
  const baseRadius = size * 0.3;
  const maxBarLength = size * 0.15;

  return (
    <svg width={size} height={size}>
      {visualization.map((amplitude, index) => {
        const angle = (index / visualization.length) * Math.PI * 2 - Math.PI / 2;
        const barLength = Math.max(4, amplitude * maxBarLength * intensity);

        const x1 = centerX + Math.cos(angle) * baseRadius;
        const y1 = centerY + Math.sin(angle) * baseRadius;
        const x2 = centerX + Math.cos(angle) * (baseRadius + barLength);
        const y2 = centerY + Math.sin(angle) * (baseRadius + barLength);

        return (
          <line
            key={index}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={color}
            strokeWidth={3}
            strokeLinecap="round"
          />
        );
      })}
      {/* Center circle */}
      <circle
        cx={centerX}
        cy={centerY}
        r={baseRadius * 0.9}
        fill="none"
        stroke={color}
        strokeWidth={2}
        opacity={0.5}
      />
    </svg>
  );
};

const LineWaveform: React.FC<WaveformVisualizationProps> = ({
  visualization,
  color,
  width,
  height,
  intensity,
}) => {
  const midY = height / 2;
  const maxAmplitude = height * 0.4;

  // Create SVG path for smooth line
  const points = visualization.map((amplitude, index) => {
    const x = (index / (visualization.length - 1)) * width;
    const y = midY - amplitude * maxAmplitude * intensity;
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(" L ")}`;

  // Mirror path for bottom
  const mirrorPoints = visualization.map((amplitude, index) => {
    const x = (index / (visualization.length - 1)) * width;
    const y = midY + amplitude * maxAmplitude * intensity;
    return `${x},${y}`;
  });

  const mirrorPathD = `M ${mirrorPoints.join(" L ")}`;

  return (
    <svg width={width} height={height}>
      <defs>
        <linearGradient id="lineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity={0.8} />
          <stop offset="50%" stopColor={color} stopOpacity={1} />
          <stop offset="100%" stopColor={color} stopOpacity={0.8} />
        </linearGradient>
      </defs>
      <path
        d={pathD}
        fill="none"
        stroke="url(#lineGradient)"
        strokeWidth={3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={mirrorPathD}
        fill="none"
        stroke="url(#lineGradient)"
        strokeWidth={3}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.6}
      />
      {/* Center line */}
      <line
        x1={0}
        y1={midY}
        x2={width}
        y2={midY}
        stroke={color}
        strokeWidth={1}
        opacity={0.3}
      />
    </svg>
  );
};

/**
 * Audio component wrapper that includes the audio track.
 * Use this in compositions to include both visualization and audio playback.
 */
export const AudioTrack: React.FC<{ src: string; volume?: number }> = ({
  src,
  volume = 1,
}) => {
  return <Audio src={src} volume={volume} />;
};

export default Waveform;
