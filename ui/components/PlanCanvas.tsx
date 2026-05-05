"use client";

import { useRef, useState, useCallback } from "react";
import { Rect, Detection } from "@/lib/api";
import { useCanvasInteraction } from "@/hooks/useCanvasInteraction";
import { extractCropBlob } from "@/lib/extractCrop";
import BboxOverlay from "./BboxOverlay";

type DrawMode = "crop" | "roi";

type Props = {
  planObjectURL: string;
  mode: DrawMode;
  cropRects: Rect[];
  roiRect: Rect | null;
  detections: Detection[];
  onCropAdded: (rect: Rect, blob: Blob) => void;
  onRoiSet: (rect: Rect) => void;
};

export default function PlanCanvas({
  planObjectURL,
  mode,
  cropRects,
  roiRect,
  detections,
  onCropAdded,
  onRoiSet,
}: Props) {
  const imageRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [naturalSize, setNaturalSize] = useState({ w: 1, h: 1 });

  const handleCropComplete = useCallback(
    async (rect: Rect) => {
      try {
        const blob = await extractCropBlob(planObjectURL, rect);
        onCropAdded(rect, blob);
      } catch (e) {
        console.error("Crop extraction failed", e);
      }
    },
    [planObjectURL, onCropAdded]
  );

  useCanvasInteraction({
    canvasRef,
    imageRef,
    mode,
    onCropComplete: handleCropComplete,
    onRoiComplete: onRoiSet,
  });

  function pct(val: number, total: number) {
    return `${(val / total) * 100}%`;
  }

  return (
    <div className="relative inline-block w-full">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imageRef}
        data-testid="plan-image"
        src={planObjectURL}
        alt="plan"
        className="block w-full pointer-events-none select-none"
        style={{ userSelect: "none" }}
        onLoad={() => {
          if (imageRef.current) {
            setNaturalSize({
              w: imageRef.current.naturalWidth,
              h: imageRef.current.naturalHeight,
            });
          }
        }}
      />

      {/* drawing canvas — sits on top, same size */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full cursor-crosshair"
        style={{ touchAction: "none" }}
      />

      {/* completed crop rect overlays */}
      {cropRects.map((r, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: pct(r.x, naturalSize.w),
            top: pct(r.y, naturalSize.h),
            width: pct(r.w, naturalSize.w),
            height: pct(r.h, naturalSize.h),
            pointerEvents: "none",
          }}
          className="border-2 border-purple-500 border-dashed"
        />
      ))}

      {/* ROI overlay */}
      {roiRect && (
        <div
          style={{
            position: "absolute",
            left: pct(roiRect.x, naturalSize.w),
            top: pct(roiRect.y, naturalSize.h),
            width: pct(roiRect.w, naturalSize.w),
            height: pct(roiRect.h, naturalSize.h),
            pointerEvents: "none",
          }}
          className="border-2 border-blue-500 border-dashed"
        />
      )}

      {/* detection bbox overlays */}
      {detections.map((d, i) => (
        <BboxOverlay
          key={i}
          detection={d}
          naturalWidth={naturalSize.w}
          naturalHeight={naturalSize.h}
        />
      ))}
    </div>
  );
}
