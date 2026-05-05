"use client";

import { Category } from "@/lib/api";

type Props = {
  categories: Category[];
  selected: Category | null;
  onSelect: (cat: Category) => void;
  loading: boolean;
};

export default function CategorySelector({ categories, selected, onSelect, loading }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="category-select" className="text-sm font-medium text-gray-300">
        Feature class
      </label>
      <select
        id="category-select"
        disabled={loading || categories.length === 0}
        value={selected?.id ?? ""}
        onChange={(e) => {
          const cat = categories.find((c) => c.id === Number(e.target.value));
          if (cat) onSelect(cat);
        }}
        className="rounded-md border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-white disabled:opacity-50"
      >
        {loading || categories.length === 0 ? (
          <option value="">Loading…</option>
        ) : (
          <>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </>
        )}
      </select>
    </div>
  );
}
