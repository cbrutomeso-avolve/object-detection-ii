"use client";

import { useRef } from "react";

type Props = {
  onFileSelected: (file: File, objectURL: string) => void;
  currentFile: File | null;
};

export default function PlanUploader({ onFileSelected, currentFile }: Props) {
  const prevURL = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (prevURL.current) URL.revokeObjectURL(prevURL.current);
    const url = URL.createObjectURL(file);
    prevURL.current = url;
    onFileSelected(file, url);
  }

  return (
    <div className="flex items-center gap-3">
      <label
        htmlFor="plan-upload"
        className="cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
      >
        {currentFile ? "Change plan" : "Upload plan"}
      </label>
      <input
        ref={inputRef}
        id="plan-upload"
        type="file"
        accept="image/png,image/jpeg"
        className="sr-only"
        onChange={handleChange}
      />
      {currentFile && (
        <span className="text-sm text-gray-400 truncate max-w-xs">{currentFile.name}</span>
      )}
    </div>
  );
}
