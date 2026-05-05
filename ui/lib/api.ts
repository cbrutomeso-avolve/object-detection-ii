const API_BASE = "http://localhost:8000";

export type Category = { id: number; name: string };

export type Detection = {
  bbox: [number, number, number, number];
  score: number;
};

export type DetectResponse = {
  category_id: number;
  category_name: string;
  detections: Detection[];
};

export type Rect = { x: number; y: number; w: number; h: number };

export type DetectPayload = {
  plan: File;
  references: Blob[];
  category_id: number;
  category_name: string;
  roi?: [number, number, number, number];
};

export async function fetchCategories(): Promise<Category[]> {
  const res = await fetch(`${API_BASE}/categories`);
  if (!res.ok) throw new Error(`/categories returned ${res.status}`);
  return res.json();
}

export async function runDetect(payload: DetectPayload): Promise<DetectResponse> {
  const fd = new FormData();
  fd.append("plan", payload.plan);
  for (const blob of payload.references) {
    fd.append("references", blob, "crop.png");
  }
  fd.append("category_id", String(payload.category_id));
  fd.append("category_name", payload.category_name);
  if (payload.roi) {
    fd.append("roi", JSON.stringify(payload.roi));
  }
  const res = await fetch(`${API_BASE}/detect`, { method: "POST", body: fd });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`/detect returned ${res.status}: ${text}`);
  }
  return res.json();
}
