import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  Img,
  staticFile,
  Audio,
} from "remotion";

export interface OriginalTemplateProps {
  /** Audio source (optional - for podcast episodes) */
  audioSrc?: string;
  /** Rotation speed in degrees per second */
  rotationSpeed?: number;
}

/**
 * Exact cabinet path extracted from the official brand SVG
 * (logo-primary-dark-bg.svg). Original viewBox is 800x800.
 *
 * Includes the decorative scalloped top edge, cabinet body,
 * and elegant legs with ball/knob details.
 */
const CABINET_PATH =
  "M664.82,65.26c0-.63-.51-1.14-1.14-1.14-103.93-.12-140.54-16.85-172.86-31.62-24.09-11.01-46.85-21.41-90.84-21.41s-67.28,10.44-91.42,21.49c-32.14,14.72-68.56,31.4-172.28,31.53-.63,0-1.15.51-1.15,1.14v547.22c0,.64.51,1.15,1.15,1.15h76.27s.09.04.09.08c3.47,32.58,12.3,80.64,12.72,107.37,0,.03-.02.07-.05.08-4.64,2.58-7.82,7.49-7.82,13.2s3.03,10.39,7.48,13.02c.03.02.05.05.05.09-.44,6.14-1.17,10.84-2.34,13.33,0,.02-.01.04,0,.06,1.8,9.26,2.61,18.35,2.07,27.22,0,.05.04.1.09.1h15.42c.05,0,.1-.05.09-.1-.54-8.86.28-17.95,2.07-27.22,0-.02,0-.04,0-.06-1.17-2.49-1.91-7.19-2.34-13.33,0-.04.02-.07.05-.09,4.46-2.63,7.48-7.44,7.48-13.02s-3.18-10.62-7.81-13.2c-.03-.02-.05-.05-.05-.08.36-26.62,9.24-74.78,12.72-107.38,0-.05.05-.08.09-.08h294.88s.09.04.09.08c3.47,32.58,12.3,80.64,12.72,107.37,0,.03-.02.07-.05.08-4.64,2.58-7.82,7.49-7.82,13.2s3.03,10.39,7.48,13.02c.03.02.05.05.05.09-.44,6.14-1.17,10.84-2.34,13.33,0,.02-.01.04,0,.06,1.8,9.26,2.61,18.35,2.07,27.22,0,.05.04.1.09.1h15.42c.05,0,.1-.05.09-.1-.54-8.86.28-17.95,2.07-27.22,0-.02,0-.04,0-.06-1.17-2.49-1.91-7.19-2.34-13.33,0-.04.02-.07.05-.09,4.46-2.63,7.48-7.44,7.48-13.02s-3.18-10.62-7.81-13.2c-.03-.02-.05-.05-.05-.08.36-26.62,9.24-74.78,12.72-107.38,0-.05.05-.08.09-.08h76.27c.64,0,1.15-.51,1.15-1.15l-.05-547.22Z";

/**
 * The cabinet body portion (without legs) for clipping the spiral.
 * This is the rectangular area from the top decorative edge
 * down to where the legs begin (y=64.12 to y=612.62 in 800x800 viewBox).
 */
const CABINET_BODY_CLIP =
  "M664.82,65.26c0-.63-.51-1.14-1.14-1.14-103.93-.12-140.54-16.85-172.86-31.62-24.09-11.01-46.85-21.41-90.84-21.41s-67.28,10.44-91.42,21.49c-32.14,14.72-68.56,31.4-172.28,31.53-.63,0-1.15.51-1.15,1.14v547.22c0,.64.51,1.15,1.15,1.15h528.54c.64,0,1.15-.51,1.15-1.15l-.05-547.22Z";

/**
 * 1:1 Recreation of the After Effects template
 *
 * Elements:
 * - Solid green background (#10a544)
 * - Black cabinet silhouette (centered) — exact brand SVG path
 * - White galaxy spiral rotating inside cabinet body (clipped)
 * - "WONDER" and "CABINET" illustrated wordmarks on either side
 */
export const OriginalTemplate: React.FC<OriginalTemplateProps> = ({
  audioSrc = "",
  rotationSpeed = 36, // degrees per second (10 sec = 360°)
}) => {
  const frame = useCurrentFrame();
  const { fps, width: videoWidth, height: videoHeight } = useVideoConfig();
  const hasAudio = audioSrc && audioSrc.length > 0;

  // Calculate rotation based on frame
  const rotation = (frame / fps) * rotationSpeed;

  // The SVG path is defined in an 800x800 viewBox.
  // The cabinet occupies roughly x:135-665, y:11-787 within that space.
  // We scale it to fit our desired on-screen size.
  const svgViewBox = "0 0 800 800";
  const cabinetDisplayHeight = videoHeight * 0.78; // ~78% of video height
  const cabinetDisplayWidth = cabinetDisplayHeight; // 1:1 aspect from viewBox

  // Spiral positioning within the 800x800 viewBox coordinate system
  // The cabinet body interior spans x:136-664, y:64-612 (528x548 area).
  // Center of cabinet body: x=400, y=338. Fill most of the interior.
  const spiralCX = 400;
  const spiralCY = 340;
  const spiralRadius = 300;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#10a544",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Wordmark: WONDER (left side) */}
      <div
        style={{
          position: "absolute",
          left: 80,
          top: "42%",
          transform: "translateY(-50%)",
          height: 50,
        }}
      >
        <Img
          src={staticFile("wonder.png")}
          style={{
            height: "100%",
            width: "auto",
          }}
        />
      </div>

      {/* Wordmark: CABINET (right side) */}
      <div
        style={{
          position: "absolute",
          right: 80,
          top: "42%",
          transform: "translateY(-50%)",
          height: 50,
        }}
      >
        <Img
          src={staticFile("cabinet.png")}
          style={{
            height: "100%",
            width: "auto",
          }}
        />
      </div>

      {/* Cabinet with rotating spiral inside */}
      <div
        style={{
          position: "relative",
          width: cabinetDisplayWidth,
          height: cabinetDisplayHeight,
        }}
      >
        <svg
          width={cabinetDisplayWidth}
          height={cabinetDisplayHeight}
          viewBox={svgViewBox}
          style={{ position: "absolute", top: 0, left: 0 }}
        >
          <defs>
            {/* Clip path using the cabinet body shape */}
            <clipPath id="cabinetClip">
              <path d={CABINET_BODY_CLIP} />
            </clipPath>
          </defs>

          {/* Rotating spiral — clipped to cabinet body interior */}
          <g clipPath="url(#cabinetClip)">
            <image
              href={staticFile("bg-galaxy-spiral-1200w@2x.png")}
              x={spiralCX - spiralRadius}
              y={spiralCY - spiralRadius}
              width={spiralRadius * 2}
              height={spiralRadius * 2}
              transform={`rotate(${rotation} ${spiralCX} ${spiralCY})`}
              preserveAspectRatio="xMidYMid meet"
            />
          </g>

          {/* Full cabinet silhouette (body + legs) drawn on top */}
          <path d={CABINET_PATH} fill="black" />

          {/* Spiral again on top — but this time clipped, so it only
              shows through the cabinet body area (on top of the black fill).
              This creates the effect: black cabinet with spiral visible inside. */}
          <g clipPath="url(#cabinetClip)">
            <image
              href={staticFile("bg-galaxy-spiral-1200w@2x.png")}
              x={spiralCX - spiralRadius}
              y={spiralCY - spiralRadius}
              width={spiralRadius * 2}
              height={spiralRadius * 2}
              transform={`rotate(${rotation} ${spiralCX} ${spiralCY})`}
              preserveAspectRatio="xMidYMid meet"
            />
          </g>
        </svg>
      </div>

      {/* Audio Track (if provided) */}
      {hasAudio && <Audio src={audioSrc} />}
    </AbsoluteFill>
  );
};

export const originalTemplateDefaultProps: OriginalTemplateProps = {
  audioSrc: staticFile("WC_S01_trailer.mp3"),
  rotationSpeed: 36,
};

export default OriginalTemplate;
