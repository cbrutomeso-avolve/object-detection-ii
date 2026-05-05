"use client";

import { Detection } from "@/lib/api";

type Props = {
  detection: Detection;
  naturalWidth: number;
  naturalHeight: number;
};

export default function BboxOverlay({ detection, naturalWidth, naturalHeight }: Props) {
  const [x, y, w, h] = detection.bbox;
  const style: React.CSSProperties = {
    position: "absolute",
    left: `${(x / naturalWidth) * 100}%`,
    top: `${(y / naturalHeight) * 100}%`,
    width: `${(w / naturalWidth) * 100}%`,
    height: `${(h / naturalHeight) * 100}%`,
    pointerEvents: "none",
  };

  return (
    <div data-testid="bbox" style={style} className="border-2 border-red-500">
      <span className="absolute -top-4 left-0 bg-red-500 px-1 text-xs text-white leading-none">
        {(detection.score * 100).toFixed(0)}%
      </span>
    </div>
  );
}
