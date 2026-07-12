// FastAPI 백엔드 연동 래퍼 (CODING_GUIDELINES: fetch는 이 파일만 사용)
const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type PlaceHit = {
  contentId: string; title: string; addr?: string | null;
  contentTypeId: string; image?: string | null; lat?: number | null; lon?: number | null;
};
export type DayCongestion = { date: string; index: number; grade: string; color: string };
export type Congestion = {
  contentId?: string; name: string; signguCd: string; date: string;
  index: number; grade: string; color: string; source: string;
  note?: string | null; series30d: DayCongestion[];
};
export type Alternative = {
  contentId: string; name: string; addr?: string | null; hiddenScore: number;
  simPct: number; congestion: number; distanceKm: number; reason: string;
};
export type Alternatives = { origin: string; date: string; count: number; alternatives: Alternative[] };
export type CourseLeg = {
  seq: number; contentId: string; name: string; arrive: string; lat: number; lon: number;
  congestion?: number | null; image?: string | null; travelKmFromPrev: number;
};
export type Course = {
  date: string; startTime: string; totalDistanceKm: number; stops: number;
  legs: CourseLeg[]; kakaoMapUrl: string; narrative: string;
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json() as Promise<T>;
}

export const api = {
  search: (q: string) => get<PlaceHit[]>(`/api/places/search?q=${encodeURIComponent(q)}&limit=10`),
  congestion: (contentId: string, date: string) =>
    get<Congestion>(`/api/congestion?contentId=${contentId}&date=${date}`),
  alternatives: (contentId: string, date: string, k = 3) =>
    get<Alternatives>(`/api/alternatives?contentId=${contentId}&date=${date}&k=${k}`),
  course: (poiIds: string[], date: string) =>
    get<Course>(`/api/course?poiIds=${poiIds.join(",")}&date=${date}`),
};
