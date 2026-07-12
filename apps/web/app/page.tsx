"use client";
import { useState } from "react";
import { api, type PlaceHit, type Congestion, type Alternatives, type Course } from "@/lib/api";
import KakaoMap from "@/components/KakaoMap";

const TODAY = new Date();
const iso = (d: Date) => d.toISOString().slice(0, 10);
const plus = (n: number) => { const d = new Date(TODAY); d.setDate(d.getDate() + n); return iso(d); };

export default function Home() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const [sel, setSel] = useState<PlaceHit | null>(null);
  const [date, setDate] = useState(plus(3));
  const [cong, setCong] = useState<Congestion | null>(null);
  const [alts, setAlts] = useState<Alternatives | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (tag: string, fn: () => Promise<void>) => {
    setLoading(tag); setErr(null);
    try { await fn(); } catch (e) { setErr(String(e)); } finally { setLoading(null); }
  };
  const doSearch = () => run("search", async () => {
    setSel(null); setCong(null); setAlts(null); setCourse(null);
    setHits(await api.search(q));
  });
  const pickPlace = (p: PlaceHit) => run("cong", async () => {
    setSel(p); setAlts(null); setCourse(null); setPicked({});
    setCong(await api.congestion(p.contentId, date));
  });
  const changeDate = (d: string) => {
    setDate(d);
    if (sel) run("cong", async () => setCong(await api.congestion(sel.contentId, d)));
  };
  const findAlts = () => sel && run("alts", async () => setAlts(await api.alternatives(sel.contentId, date, 3)));
  const makeCourse = () => run("course", async () => {
    setCourse(await api.course([sel!.contentId, ...Object.keys(picked)], date));
  });

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 text-slate-800">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-teal-700">숨은한국</h1>
        <p className="text-sm text-slate-500">붐비는 곳 말고, 숨은 한국 — 혼잡 예측 기반 여행 추천</p>
      </header>

      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doSearch()}
          placeholder="관광지 검색 (예: 경복궁, 해운대)" className="flex-1 rounded-lg border border-slate-300 px-3 py-2" />
        <input type="date" value={date} min={plus(0)} max={plus(29)} onChange={(e) => changeDate(e.target.value)}
          className="rounded-lg border border-slate-300 px-2 py-2 text-sm" />
        <button onClick={doSearch} className="rounded-lg bg-teal-600 px-4 py-2 text-white">검색</button>
      </div>
      {err && <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-600">오류: {err}</p>}
      {loading && <p className="mt-3 text-sm text-slate-400">불러오는 중… ({loading})</p>}

      {hits.length > 0 && !sel && (
        <ul className="mt-4 divide-y rounded-lg border border-slate-200">
          {hits.map((h) => (
            <li key={h.contentId}>
              <button onClick={() => pickPlace(h)} className="flex w-full items-center gap-3 p-3 text-left hover:bg-slate-50">
                {h.image
                  ? <img src={h.image} alt="" className="h-12 w-12 rounded object-cover" />
                  : <div className="h-12 w-12 rounded bg-slate-100" />}
                <span><b>{h.title}</b><br /><span className="text-xs text-slate-500">{h.addr}</span></span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {cong && sel && (
        <section className="mt-6 rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{cong.name}</h2>
            <button onClick={() => { setSel(null); setCong(null); }} className="text-xs text-slate-400">← 다시 검색</button>
          </div>
          <div className="mt-2 flex items-center gap-3">
            <span className="rounded-full px-3 py-1 text-sm font-bold text-white" style={{ background: cong.color }}>
              {cong.grade} {cong.index}
            </span>
            <span className="text-xs text-slate-500">{date} · {cong.source === "KTO_FORECAST" ? "공사 예측" : "숨은한국 AI 추정"}</span>
          </div>
          {cong.note && <p className="mt-1 text-xs text-amber-600">{cong.note}</p>}

          {cong.series30d.length > 0 && (
            <div className="mt-4">
              <p className="mb-1 text-xs text-slate-500">향후 30일 혼잡 (칸 클릭 = 날짜 변경)</p>
              <div className="grid grid-cols-10 gap-1">
                {cong.series30d.map((d) => (
                  <button key={d.date} title={`${d.date} ${d.grade} ${d.index}`} onClick={() => changeDate(d.date)}
                    className={`h-7 rounded text-[9px] text-white ${d.date === date ? "ring-2 ring-teal-700" : ""}`}
                    style={{ background: d.color }}>{d.date.slice(8)}</button>
                ))}
              </div>
            </div>
          )}
          <button onClick={findAlts}
            className={`mt-4 w-full rounded-lg py-2 font-semibold ${cong.index >= 60 ? "bg-orange-500 text-white" : "border border-teal-600 text-teal-700"}`}>
            {cong.index >= 60 ? "이 날 비슷한데 한적한 곳 찾기" : "비슷한 다른 명소 보기"}
          </button>
        </section>
      )}

      {alts && (
        <section className="mt-6">
          <h3 className="mb-2 font-semibold">한적한 대안 {alts.count}곳</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            {alts.alternatives.map((a) => {
              const on = a.contentId in picked;
              return (
                <div key={a.contentId} className={`rounded-xl border border-slate-200 p-3 ${on ? "ring-2 ring-teal-600" : ""}`}>
                  <b className="text-sm">{a.name}</b>
                  <p className="mt-1 text-xs text-slate-600">{a.reason}</p>
                  <p className="mt-2 text-[11px] text-slate-500">유사도 {a.simPct}% · 혼잡 {a.congestion} · {a.distanceKm}km</p>
                  <button
                    onClick={() => setPicked((p) => { const n = { ...p }; if (on) delete n[a.contentId]; else n[a.contentId] = a.name; return n; })}
                    className={`mt-2 w-full rounded py-1 text-xs ${on ? "bg-teal-600 text-white" : "border border-slate-300"}`}>
                    {on ? "코스에 추가됨 ✓" : "코스에 추가"}
                  </button>
                </div>
              );
            })}
          </div>
          {Object.keys(picked).length > 0 && (
            <button onClick={makeCourse} className="mt-4 w-full rounded-lg bg-teal-700 py-2 font-semibold text-white">
              {sel?.title} + {Object.keys(picked).length}곳으로 코스 만들기
            </button>
          )}
        </section>
      )}

      {course && (
        <section className="mt-6 rounded-xl border border-slate-200 p-4">
          <h3 className="font-semibold">추천 코스 · 총 {course.totalDistanceKm}km</h3>
          <p className="mt-1 text-sm text-slate-600">{course.narrative}</p>
          <KakaoMap stops={course.legs.map((l) => ({ seq: l.seq, name: l.name, lat: l.lat, lon: l.lon }))} />
          <ol className="mt-3 space-y-2">
            {course.legs.map((l) => (
              <li key={l.seq} className="flex items-center gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-600 text-xs text-white">{l.seq}</span>
                <span className="text-sm">
                  <b>{l.arrive}</b> {l.name}
                  {l.congestion != null && <span className="ml-1 text-[11px] text-slate-400">혼잡 {l.congestion}</span>}
                  {l.travelKmFromPrev > 0 && <span className="ml-1 text-[11px] text-slate-400">· {l.travelKmFromPrev}km 이동</span>}
                </span>
              </li>
            ))}
          </ol>
          <a href={course.kakaoMapUrl} target="_blank" rel="noreferrer"
            className="mt-3 inline-block rounded-lg bg-yellow-400 px-4 py-2 text-sm font-semibold">카카오맵에서 열기</a>
        </section>
      )}

      <footer className="mt-10 text-center text-[11px] text-slate-400">데이터: 한국관광공사 TourAPI · 기상청</footer>
    </main>
  );
}
