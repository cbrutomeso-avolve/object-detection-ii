"use client";

import { useEffect, useRef } from "react";
import { Rect } from "@/lib/api";

type DrawMode = "crop" | "roi";

type Params = {
  canvasRef: React.RefObject<HTMLCanvasElement>;
  imageRef: React.RefObject<HTMLImageElement>;
  mode: DrawMode;
  onCropComplete: (rect: Rect) => void;
  onRoiComplete: (rect: Rect) => void;
};

export function useCanvasInteraction({
  canvasRef,
  imageRef,
  mode,
  onCropComplete,
  onRoiComplete,
}: Params) {
  // Keep mode in a ref so event listeners always see the latest value
  const modeRef = useRef(mode);
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image) return;

    let startX = 0;
    let startY = 0;
    let isDragging = false;

    function toImageCoords(cssX: number, cssY: number): { x: number; y: number } {
      const scaleX = image!.naturalWidth / image!.clientWidth;
      const scaleY = image!.naturalHeight / image!.clientHeight;
      return { x: Math.round(cssX * scaleX), y: Math.round(cssY * scaleY) };
    }

    function getOffset(e: MouseEvent): { x: number; y: number } {
      const rect = canvas!.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    function drawRect(x: number, y: number, w: number, h: number, color: string) {
      const ctx = canvas!.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas!.width, canvas!.height);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(x, y, w, h);
    }

    function onMouseDown(e: MouseEvent) {
      const { x, y } = getOffset(e);
      startX = x;
      startY = y;
      isDragging = true;
    }

    function onMouseMove(e: MouseEvent) {
      if (!isDragging) return;
      const { x, y } = getOffset(e);
      const w = x - startX;
      const h = y - startY;
      const color = modeRef.current === "crop" ? "#9333ea" : "#3b82f6";
      drawRect(startX, startY, w, h, color);
    }

    function onMouseUp(e: MouseEvent) {
      if (!isDragging) return;
      isDragging = false;

      const ctx = canvas!.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, canvas!.width, canvas!.height);

      const { x: endX, y: endY } = getOffset(e);
      const cssX = Math.min(startX, endX);
      const cssY = Math.min(startY, endY);
      const cssW = Math.abs(endX - startX);
      const cssH = Math.abs(endY - startY);

      if (cssW < 5 || cssH < 5) return; // ignore tiny accidental clicks

      const topLeft = toImageCoords(cssX, cssY);
      const bottomRight = toImageCoords(cssX + cssW, cssY + cssH);
      const rect: Rect = {
        x: topLeft.x,
        y: topLeft.y,
        w: bottomRight.x - topLeft.x,
        h: bottomRight.y - topLeft.y,
      };

      if (modeRef.current === "crop") {
        onCropComplete(rect);
      } else {
        onRoiComplete(rect);
      }
    }

    function syncCanvasSize() {
      if (!canvas || !image) return;
      canvas.width = image.clientWidth;
      canvas.height = image.clientHeight;
    }

    syncCanvasSize();

    const resizeObserver = new ResizeObserver(syncCanvasSize);
    resizeObserver.observe(image);

    // mousemove and mouseup are on window so drags that exit the canvas still complete
    canvas.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    return () => {
      canvas.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      resizeObserver.disconnect();
    };
  }, [canvasRef, imageRef, onCropComplete, onRoiComplete]);
}
