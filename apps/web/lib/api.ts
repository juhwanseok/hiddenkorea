// FastAPI 백엔드 연동 래퍼 (CODING_GUIDELINES: fetch는 이 파일만 사용)
const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type PlaceHit = {
  contentId: string; title: string; addr?: string | null;
  contentTypeId: string; image?: string | null; lat?: number | null; lon?: number | null;
};
export type WeatherInfo = { label: string; emoji: string; tmp?: number | null; rain: boolean; indoorPref: boolean; note?: string | null };
export type RealtimeInfo = { area: string; level: string; msg?: string | null; min?: string | null; max?: string | null; time?: string | null };
export type DayCongestion = { date: string; index: number; grade: string; color: string };
export type Congestion = {
  contentId?: string; name: string; signguCd: string; date: string;
  index: number; grade: string; color: string; source: string;
  note?: string | null; weather?: WeatherInfo | null; realtime?: RealtimeInfo | null; series30d: DayCongestion[];
};
export type Alternative = {
  contentId: string; name: string; addr?: string | null; region?: string | null; hiddenScore: number;
  simPct: number; congestion: number; distanceKm: number; reason: string; overview?: string | null;
};
export type PlaceDetail = {
  contentId: string; overview?: string | null; homepage?: string | null; tel?: string | null;
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
export type Region = { code: string; name: string };
export type HighlightSpot = { contentId: string; name: string; today: number; avg: number; dropPct: number; image?: string | null };
export type HighlightRegion = { areaName: string; spots: HighlightSpot[] };
export type ItineraryStop = {
  seq: number; contentId: string; name: string; arrive: string;
  label: string; kind: "act" | "meal" | "cafe";
  lat: number; lon: number; congestion: number; image?: string | null;
};
export type ItineraryDay = { date: string; weekday: string; avgCongestion: number; totalDistanceKm?: number; weather?: WeatherInfo | null; stops: ItineraryStop[] };
export type Itinerary = {
  areaName: string; signguName?: string | null; genre: string;
  startDate: string; endDate: string; days: ItineraryDay[];
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json() as Promise<T>;
}

export const api = {
  search: (q: string) => get<PlaceHit[]>(`/api/places/search?q=${encodeURIComponent(q)}&limit=10`),
  popular: (n = 8) => get<PlaceHit[]>(`/api/places/popular?n=${n}`),
  highlights: (date: string) => get<HighlightRegion[]>(`/api/highlights?date=${date}&regionsN=6&perRegion=3`),
  detail: (contentId: string) => get<PlaceDetail>(`/api/places/detail?contentId=${contentId}`),
  congestion: (contentId: string, date: string) =>
    get<Congestion>(`/api/congestion?contentId=${contentId}&date=${date}`),
  alternatives: (contentId: string, date: string, k = 3, scope: "nearby" | "nationwide" = "nearby") =>
    get<Alternatives>(`/api/alternatives?contentId=${contentId}&date=${date}&k=${k}&scope=${scope}`),
  course: (poiIds: string[], date: string) =>
    get<Course>(`/api/course?poiIds=${poiIds.join(",")}&date=${date}`),
  regions: (areaCd?: string) => get<Region[]>(`/api/regions${areaCd ? `?areaCd=${areaCd}` : ""}`),
  genres: () => get<string[]>(`/api/genres`),
  foodCategories: () => get<string[]>(`/api/food-categories`),
  itinerary: (areaCd: string, startDate: string, endDate: string, genres: string[], signguCds: string[] = [], foodCats: string[] = []) =>
    get<Itinerary>(`/api/itinerary?areaCd=${areaCd}&startDate=${startDate}&endDate=${endDate}&genres=${encodeURIComponent(genres.join(","))}${signguCds.length ? `&signguCds=${signguCds.join(",")}` : ""}${foodCats.length ? `&foodCats=${encodeURIComponent(foodCats.join(","))}` : ""}`),
};
