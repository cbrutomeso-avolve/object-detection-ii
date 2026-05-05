"use client";

type DrawMode = "crop" | "roi";

type Props = {
  mode: DrawMode;
  onChange: (mode: DrawMode) => void;
};

export default function DrawModeToggle({ mode, onChange }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium text-gray-300">Draw mode</span>
      <div className="flex rounded-md overflow-hidden border border-gray-600">
        <button
          type="button"
          onClick={() => onChange("crop")}
          className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
            mode === "crop"
              ? "bg-purple-600 text-white"
              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          Draw Crop
        </button>
        <button
          type="button"
          onClick={() => onChange("roi")}
          className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
            mode === "roi"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          Set ROI
        </button>
      </div>
    </div>
  );
}
