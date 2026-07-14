"use client";
import { useEffect, useState } from "react";
import { api, type Region, type Itinerary } from "@/lib/api";
import KakaoMap from "@/components/KakaoMap";

const WD = ["일", "월", "화", "수", "목", "금", "토"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const GENRE_EMOJI: Record<string, string> = { 관광지: "🏛️", 식도락: "🍜", 쇼핑: "🛍️", 레포츠: "🏄", 문화시설: "🎭" };

// 향후 30일 날짜(당일~+29)
const DAYS30 = Array.from({ length: 30 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return iso(d); });

function RangeCalendar({ start, end, onPick }: { start: string; end: string; onPick: (s: string, e: string) => void }) {
  const first = new Date(DAYS30[0] + "T00:00:00");
  const lead = first.getDay();
  const cells: (string | null)[] = [...Array(lead).fill(null), ...DAYS30];
  const inRange = (d: string) => start && end && d >= start && d <= end;

  const click = (d: string) => {
    if (!start || (start && end)) onPick(d, "");          // 1클릭: 시작
    else onPick(start, d < start ? start : d);            // 2클릭: 끝(역순 보정)
  };
  return (
    <div>
      <p className="mb-1 text-xs text-slate-500">기간 선택 (시작일·종료일 2번 클릭 · 최대 5일)</p>
      <div className="grid grid-cols-7 gap-1">
        {WD.map((w, i) => <div key={w} className={`text-center text-[11px] font-semibold ${i === 0 ? "text-red-500" : i === 6 ? "text-blue-500" : "text-slate-400"}`}>{w}</div>)}
        {cells.map((d, i) => d === null ? <div key={`e${i}`} /> : (
          <button key={d} onClick={() => click(d)}
            className={`aspect-square rounded-md text-[11px] transition hover:scale-105 ${d === start || d === end ? "bg-teal-600 text-white font-bold" : inRange(d) ? "bg-teal-100 text-teal-800" : "bg-slate-50 text-slate-600 hover:bg-slate-100"}`}>
            {Number(d.slice(8))}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function TripPlanner() {
  const [sido, setSido] = useState<Region[]>([]);
  const [sigungu, setSigungu] = useState<Region[]>([]);
  const [genres, setGenres] = useState<string[]>([]);
  const [foodCats, setFoodCats] = useState<string[]>([]);
  const [foodCat, setFoodCat] = useState("전체");
  const [area, setArea] = useState("");
  const [sgus, setSgus] = useState<string[]>([]);
  const [picked, setPicked] = useState<string[]>(["관광지"]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [plan, setPlan] = useState<Itinerary | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.regions().then(setSido).catch(() => {});
    api.genres().then(setGenres).catch(() => {});
    api.foodCategories().then(setFoodCats).catch(() => {});
  }, []);
  useEffect(() => {
    setSgus([]);
    if (area) api.regions(area).then(setSigungu).catch(() => setSigungu([]));
    else setSigungu([]);
  }, [area]);

  const toggleGenre = (g: string) =>
    setPicked((p) => p.includes(g) ? (p.length > 1 ? p.filter((x) => x !== g) : p) : [...p, g]);
  const toggleSgu = (code: string) =>
    setSgus((p) => p.includes(code) ? p.filter((x) => x !== code) : [...p, code]);

  const gen = async () => {
    if (!area || !start) { setErr("지역과 기간(시작일)을 선택하세요"); return; }
    setLoading(true); setErr(null); setPlan(null);
    try { setPlan(await api.itinerary(area, start, end || start, picked, sgus, picked.includes("식도락") ? foodCat : "")); }
    catch (e) { setErr(String(e)); } finally { setLoading(false); }
  };

  const gradeColor = (v: number) => v < 20 ? "#22c55e" : v < 40 ? "#eab308" : v < 60 ? "#f97316" : v < 80 ? "#ef4444" : "#991b1b";

  return (
    <section className="animate-[fadeIn_.3s_ease]">
      {/* 지역: 시·도 선택 + 시·군·구 다중 선택 */}
      <div className="flex flex-wrap gap-2">
        <select value={area} onChange={(e) => setArea(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="">시·도 선택</option>
          {sido.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </div>
      {area && sigungu.length > 0 && (
        <div className="mt-2">
          <p className="mb-1.5 text-xs text-slate-500">
            시·군·구 선택 (여러 곳 선택 가능 · 미선택 시 전체)
            {sgus.length > 0 && <span className="ml-1 text-teal-600">· {sgus.length}곳</span>}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {sigungu.map((s) => {
              const on = sgus.includes(s.code);
              return (
                <button key={s.code} onClick={() => toggleSgu(s.code)}
                  className={`rounded-full px-2.5 py-1 text-xs transition ${on ? "bg-teal-600 text-white" : "border border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
                  {s.name}{on ? " ✓" : ""}
                </button>
              );
            })}
          </div>
          <p className="mt-1 text-[11px] text-slate-400">여러 곳을 고르면 거리 기반으로 가까운 순서대로 동선을 짜드려요</p>
        </div>
      )}

      {/* 장르 (다중 선택) */}
      <div className="mt-3">
        <div className="flex flex-wrap gap-2">
          {genres.map((g) => {
            const on = picked.includes(g);
            return (
              <button key={g} onClick={() => toggleGenre(g)}
                className={`rounded-full px-3 py-1.5 text-sm transition ${on ? "bg-teal-600 text-white" : "border border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
                {GENRE_EMOJI[g] || ""} {g}{on ? " ✓" : ""}
              </button>
            );
          })}
        </div>
        <p className="mt-1 text-[11px] text-slate-400">여러 개 선택 가능 · 식사·카페는 자동으로 알맞은 시간에 넣어드려요</p>
      </div>

      {/* 음식 종류 (식도락 선택 시) */}
      {picked.includes("식도락") && foodCats.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs font-semibold text-amber-700">🍽️ 음식 종류</p>
          <div className="flex flex-wrap gap-2">
            {foodCats.map((f) => (
              <button key={f} onClick={() => setFoodCat(f)}
                className={`rounded-full px-3 py-1 text-sm transition ${foodCat === f ? "bg-amber-500 text-white" : "border border-slate-300 text-slate-600 hover:bg-amber-50"}`}>
                {f}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 기간 달력 */}
      <div className="mt-4 rounded-xl border border-slate-200 p-3">
        <RangeCalendar start={start} end={end} onPick={(s, e) => { setStart(s); setEnd(e); }} />
        {start && <p className="mt-2 text-xs text-teal-700">{start}{end && end !== start ? ` ~ ${end}` : " (당일)"}</p>}
      </div>

      <button onClick={gen} disabled={loading}
        className="mt-4 w-full rounded-lg bg-teal-700 py-2.5 font-semibold text-white transition hover:bg-teal-800 active:scale-95 disabled:opacity-60">
        {loading ? "일정 짜는 중…" : "여행 일정 추천받기"}
      </button>
      {err && <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-600">오류: {err}</p>}

      {/* 결과 */}
      {plan && (
        <div className="mt-6 animate-[fadeIn_.3s_ease]">
          <h3 className="font-semibold">{plan.areaName}{plan.signguName ? ` ${plan.signguName}` : ""} · {plan.genre} · {plan.days.length}일 코스</h3>
          <p className="text-xs text-slate-500">붐비지 않는 곳 위주로 날짜별로 배치했습니다.</p>
          <div className="mt-3 space-y-4">
            {plan.days.map((d, i) => (
              <div key={d.date} className="rounded-xl border border-slate-200 p-3 shadow-sm">
                <div className="flex items-center justify-between">
                  <b className="text-sm">Day {i + 1} · {d.date}({d.weekday})</b>
                  <span className="flex items-center gap-1">
                    {d.weather && <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700">{d.weather.emoji} {d.weather.label}{d.weather.tmp != null ? ` ${d.weather.tmp}°` : ""}</span>}
                    {d.totalDistanceKm != null && d.totalDistanceKm > 0 && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">🧭 {d.totalDistanceKm}km</span>}
                    <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ background: gradeColor(d.avgCongestion) }}>평균 혼잡 {d.avgCongestion}</span>
                  </span>
                </div>
                {d.weather?.note && <p className="mt-1 text-[11px] text-sky-600">☔ {d.weather.note}</p>}
                <KakaoMap stops={d.stops.map((s) => ({ seq: s.seq, name: s.name, lat: s.lat, lon: s.lon }))} />
                <ol className="mt-2 space-y-2">
                  {d.stops.map((s) => {
                    const icon = s.kind === "meal" ? (s.label === "점심" ? "🍚" : "🍽️") : s.kind === "cafe" ? "☕" : "📍";
                    const isFood = s.kind !== "act";
                    return (
                      <li key={s.contentId} className="flex items-center gap-2">
                        <span className="w-11 shrink-0 text-right text-xs font-semibold text-slate-500">{s.arrive}</span>
                        {s.image ? <img src={s.image} alt="" className="h-10 w-10 shrink-0 rounded object-cover" /> : <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-slate-100 text-base">{icon}</div>}
                        <span className="text-sm">
                          <span className={`mr-1 rounded px-1 py-0.5 text-[10px] ${isFood ? "bg-amber-100 text-amber-700" : "bg-teal-100 text-teal-700"}`}>{icon} {s.label}</span>
                          <b>{s.name}</b>
                          {!isFood && <span className="ml-1 rounded px-1 text-[10px] text-white" style={{ background: gradeColor(s.congestion) }}>혼잡 {s.congestion}</span>}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
