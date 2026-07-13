"use client";
import { useEffect, useState } from "react";
import { api, type Region, type Itinerary } from "@/lib/api";
import KakaoMap from "@/components/KakaoMap";

const WD = ["일", "월", "화", "수", "목", "금", "토"];
const iso = (d: Date) => d.toISOString().slice(0, 10);
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
  const [area, setArea] = useState("");
  const [sgu, setSgu] = useState("");
  const [genre, setGenre] = useState("관광지");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [plan, setPlan] = useState<Itinerary | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.regions().then(setSido).catch(() => {}); api.genres().then(setGenres).catch(() => {}); }, []);
  useEffect(() => {
    setSgu("");
    if (area) api.regions(area).then(setSigungu).catch(() => setSigungu([]));
    else setSigungu([]);
  }, [area]);

  const gen = async () => {
    if (!area || !start) { setErr("지역과 기간(시작일)을 선택하세요"); return; }
    setLoading(true); setErr(null); setPlan(null);
    try { setPlan(await api.itinerary(area, start, end || start, genre, sgu)); }
    catch (e) { setErr(String(e)); } finally { setLoading(false); }
  };

  const gradeColor = (v: number) => v < 20 ? "#22c55e" : v < 40 ? "#eab308" : v < 60 ? "#f97316" : v < 80 ? "#ef4444" : "#991b1b";

  return (
    <section className="animate-[fadeIn_.3s_ease]">
      {/* 지역 */}
      <div className="flex flex-wrap gap-2">
        <select value={area} onChange={(e) => setArea(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="">시·도 선택</option>
          {sido.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={sgu} onChange={(e) => setSgu(e.target.value)} disabled={!area} className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">
          <option value="">전체 시·군·구</option>
          {sigungu.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </div>

      {/* 장르 */}
      <div className="mt-3 flex flex-wrap gap-2">
        {genres.map((g) => (
          <button key={g} onClick={() => setGenre(g)}
            className={`rounded-full px-3 py-1.5 text-sm transition ${genre === g ? "bg-teal-600 text-white" : "border border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
            {GENRE_EMOJI[g] || ""} {g}
          </button>
        ))}
      </div>

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
                  <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ background: gradeColor(d.avgCongestion) }}>평균 혼잡 {d.avgCongestion}</span>
                </div>
                <KakaoMap stops={d.stops.map((s) => ({ seq: s.seq, name: s.name, lat: s.lat, lon: s.lon }))} />
                <ol className="mt-2 space-y-1.5">
                  {d.stops.map((s) => (
                    <li key={s.contentId} className="flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-teal-600 text-[10px] text-white">{s.seq}</span>
                      {s.image ? <img src={s.image} alt="" className="h-9 w-9 rounded object-cover" /> : <div className="h-9 w-9 rounded bg-slate-100" />}
                      <span className="text-sm">{s.arrive} <b>{s.name}</b>
                        <span className="ml-1 rounded px-1 text-[10px] text-white" style={{ background: gradeColor(s.congestion) }}>혼잡 {s.congestion}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
