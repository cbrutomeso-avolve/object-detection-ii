"use client";

type Props = {
  count: number;
  roiSet: boolean;
  onClearCrops: () => void;
  onClearRoi: () => void;
};

export default function CropList({ count, roiSet, onClearCrops, onClearRoi }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span data-testid="crop-count" className="text-sm text-gray-300">
          {count} crop{count !== 1 ? "s" : ""} drawn
        </span>
        {count > 0 && (
          <button
            type="button"
            onClick={onClearCrops}
            className="text-xs text-red-400 hover:text-red-300 underline"
          >
            Clear crops
          </button>
        )}
      </div>
      {roiSet && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-blue-400">ROI set</span>
          <button
            type="button"
            onClick={onClearRoi}
            className="text-xs text-red-400 hover:text-red-300 underline"
          >
            Clear ROI
          </button>
        </div>
      )}
    </div>
  );
}
