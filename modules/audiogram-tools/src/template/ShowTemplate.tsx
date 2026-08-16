import React from "react";
import { AbsoluteFill, Audio, staticFile } from "remotion";
import { OrientationConfig, LayerDef } from "./types";
import { SolidBackground } from "./layers/SolidBackground";
import { GalaxySpiral } from "./layers/GalaxySpiral";
import { CabinetFrame } from "./layers/CabinetFrame";
import { TitleImage } from "./layers/TitleImage";

// Resolve an asset src that might be a bare filename (needs staticFile)
// or already a fully-formed URL (from defaultProps where staticFile was applied).
const resolveAssetSrc = (src: string): string =>
  /^(https?:|\/|file:)/.test(src) ? src : staticFile(src);

export interface ShowTemplateProps {
  /** Template layer configuration (from template.json) */
  templateConfig: OrientationConfig;
  /** Audio source path */
  audioSrc?: string;
  /** Episode art image path (for cabinet-frame clipping) */
  episodeArtSrc?: string;
}

/**
 * Generic data-driven Remotion composition.
 * Renders a stack of typed layers defined in template.json.
 *
 * Each layer type maps to a dedicated React component.
 * The layer stack renders bottom-to-top (first layer = back).
 */
export const ShowTemplate: React.FC<ShowTemplateProps> = ({
  templateConfig,
  audioSrc,
  episodeArtSrc,
}) => {
  const hasAudio = Boolean(audioSrc && audioSrc.length > 0);

  return (
    <AbsoluteFill>
      {templateConfig.layers.map((layer, index) => (
        <LayerRenderer
          key={index}
          layer={layer}
          episodeArtSrc={episodeArtSrc}
        />
      ))}
      {hasAudio && <Audio src={resolveAssetSrc(audioSrc!)} />}
    </AbsoluteFill>
  );
};

/**
 * Routes a LayerDef to the appropriate component.
 */
const LayerRenderer: React.FC<{
  layer: LayerDef;
  episodeArtSrc?: string;
}> = ({ layer, episodeArtSrc }) => {
  switch (layer.type) {
    case "solid":
      return <SolidBackground color={layer.color} grain={layer.grain} />;
    case "spiral":
      return (
        <GalaxySpiral
          asset={layer.asset}
          rotationSpeed={layer.rotationSpeed}
          opacity={layer.opacity}
        />
      );
    case "cabinet-frame":
      return (
        <CabinetFrame
          asset={layer.asset}
          artClip={layer.artClip}
          episodeArtSrc={episodeArtSrc}
        />
      );
    case "title-image":
      return (
        <TitleImage
          asset={layer.asset}
          layout={layer.layout}
          leftAsset={layer.leftAsset}
          rightAsset={layer.rightAsset}
        />
      );
    default: {
      const _exhaustive: never = layer;
      return null;
    }
  }
};
