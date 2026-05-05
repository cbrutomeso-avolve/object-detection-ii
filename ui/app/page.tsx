"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Category,
  Detection,
  Rect,
  fetchCategories,
  runDetect,
} from "@/lib/api";
import PlanUploader from "@/components/PlanUploader";
import PlanCanvas from "@/components/PlanCanvas";
import CategorySelector from "@/components/CategorySelector";
import DrawModeToggle from "@/components/DrawModeToggle";
import CropList from "@/components/CropList";

type DrawMode = "crop" | "roi";

export default function Home() {
  const [planFile, setPlanFile] = useState<File | null>(null);
  const [planObjectURL, setPlanObjectURL] = useState<string | null>(null);
  const [cropRects, setCropRects] = useState<Rect[]>([]);
  const [cropBlobs, setCropBlobs] = useState<Blob[]>([]);
  const [roiRect, setRoiRect] = useState<Rect | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("crop");
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories()
      .then((cats) => {
        setCategories(cats);
        if (cats.length > 0) setSelectedCategory(cats[0]);
      })
      .catch(() => setError("Could not reach the API — is it running on port 8000?"))
      .finally(() => setCategoriesLoading(false));
  }, []);

  function handleFileSelected(file: File, url: string) {
    setPlanFile(file);
    setPlanObjectURL(url);
    setCropRects([]);
    setCropBlobs([]);
    setRoiRect(null);
    setDetections([]);
    setError(null);
  }

  const handleCropAdded = useCallback((rect: Rect, blob: Blob) => {
    setCropRects((prev) => [...prev, rect]);
    setCropBlobs((prev) => [...prev, blob]);
    setDetections([]);
  }, []);

  const handleRoiSet = useCallback((rect: Rect) => {
    setRoiRect(rect);
    setDetections([]);
  }, []);

  function clearCrops() {
    setCropRects([]);
    setCropBlobs([]);
    setDetections([]);
  }

  function clearRoi() {
    setRoiRect(null);
    setDetections([]);
  }

  async function handleDetect() {
    if (!planFile || cropBlobs.length === 0 || !selectedCategory) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await runDetect({
        plan: planFile,
        references: cropBlobs,
        category_id: selectedCategory.id,
        category_name: selectedCategory.name,
        roi: roiRect
          ? [roiRect.x, roiRect.y, roiRect.w, roiRect.h]
          : undefined,
      });
      setDetections(result.detections);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsLoading(false);
    }
  }

  const canDetect =
    !!planFile && cropBlobs.length > 0 && !!selectedCategory && !isLoading;

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-screen-2xl mx-auto p-4 flex flex-col gap-4">
        {/* header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-xl font-semibold">Object Detection</h1>
          <PlanUploader onFileSelected={handleFileSelected} currentFile={planFile} />
        </div>

        {error && (
          <div className="rounded-md bg-red-900/50 border border-red-700 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="flex gap-4">
          {/* canvas area */}
          <div className="flex-1 min-w-0 bg-gray-800 rounded-lg overflow-hidden">
            {planObjectURL ? (
              <PlanCanvas
                planObjectURL={planObjectURL}
                mode={drawMode}
                cropRects={cropRects}
                roiRect={roiRect}
                detections={detections}
                onCropAdded={handleCropAdded}
                onRoiSet={handleRoiSet}
              />
            ) : (
              <div className="flex items-center justify-center h-96 text-gray-500 text-sm">
                Upload a plan to get started
              </div>
            )}
          </div>

          {/* sidebar */}
          <div className="w-64 flex-shrink-0 flex flex-col gap-4">
            {planObjectURL && (
              <>
                <DrawModeToggle mode={drawMode} onChange={setDrawMode} />
                <CropList
                  count={cropRects.length}
                  roiSet={!!roiRect}
                  onClearCrops={clearCrops}
                  onClearRoi={clearRoi}
                />
              </>
            )}

            <CategorySelector
              categories={categories}
              selected={selectedCategory}
              onSelect={setSelectedCategory}
              loading={categoriesLoading}
            />

            <button
              type="button"
              data-testid="detect-btn"
              onClick={handleDetect}
              disabled={!canDetect}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? "Detecting…" : "Detect"}
            </button>

            {detections.length > 0 && (
              <div className="text-sm text-gray-300">
                Found{" "}
                <span className="font-semibold text-white">{detections.length}</span>{" "}
                detection{detections.length !== 1 ? "s" : ""}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
