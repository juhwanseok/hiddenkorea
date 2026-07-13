"use client";
import { useState, useEffect } from "react";
import { api, type PlaceHit, type Congestion, type Alternatives, type Course, type PlaceDetail, type HighlightRegion } from "@/lib/api";
import KakaoMap from "@/components/KakaoMap";
import HeatCalendar from "@/components/HeatCalendar";
import TripPlanner from "@/components/TripPlanner";
import { getWishlist, toggleWish, removeWish, isWished, type WishItem } from "@/lib/wishlist";

const TODAY = new Date();
const iso = (d: Date) => d.toISOString().slice(0, 10);
const plus = (n: number) => { const d = new Date(TODAY); d.setDate(d.getDate() + n); return iso(d); };

export default function Home() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const [sel, setSel] = useState<PlaceHit | null>(null);
  const [date, setDate] = useState(plus(3));
  const [cong, setCong] = useState<Congestion | null>(null);
  const [detail, setDetail] = useState<PlaceDetail | null>(null);
  const [alts, setAlts] = useState<Alternatives | null>(null);
  const [nationAlts, setNationAlts] = useState<Alternatives | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"place" | "trip">("place");
  const [wish, setWish] = useState<WishItem[]>([]);
  const [showWish, setShowWish] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [popular, setPopular] = useState<PlaceHit[]>([]);

  // 마운트: 위시리스트 로드 + 공유 URL 복원(?place=&date= 또는 ?course=&date=)
  useEffect(() => {
    setWish(getWishlist());
    const p = new URLSearchParams(window.location.search);
    const d = p.get("date");
    if (d) setDate(d);
    if (p.get("place")) {
      const cid = p.get("place")!;
      run("cong", async () => {
        setSel({ contentId: cid, title: "", contentTypeId: "12" } as PlaceHit);
        setCong(await api.congestion(cid, d || date));
        api.detail(cid).then(setDetail).catch(() => {});
      });
    } else if (p.get("course")) {
      const ids = p.get("course")!.split(",").filter(Boolean);
      if (ids.length >= 2) run("course", async () => setCourse(await api.course(ids, d || date)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 1800); };
  const copy = (url: string, label: string) => {
    navigator.clipboard?.writeText(url).then(() => flash(`${label} 링크가 복사됐어요`)).catch(() => flash("복사 실패"));
  };
  const toggleWishItem = (it: WishItem) => { setWish(toggleWish(it)); };
  const makeCourseFromWish = () => {
    if (wish.length < 2) { flash("코스는 2곳 이상 필요해요"); return; }
    setShowWish(false); setMode("place"); setSel(null); setCong(null); setAlts(null);
    run("course", async () => setCourse(await api.course(wish.map((w) => w.contentId), date)));
  };
  const [focused, setFocused] = useState(false);
  const [highlights, setHighlights] = useState<HighlightRegion[]>([]);

  // 홈 유휴 상태: 선택일 기준 '평소보다 한적한 명소' 로드 (날짜 변경 시 갱신 = 유동적)
  useEffect(() => {
    if (mode === "place" && !sel && !hits.length) {
      api.highlights(date).then(setHighlights).catch(() => setHighlights([]));
    }
  }, [date, mode, sel, hits.length]);

  const run = async (tag: string, fn: () => Promise<void>) => {
    setLoading(tag); setErr(null);
    try { await fn(); } catch (e) { setErr(String(e)); } finally { setLoading(null); }
  };
  const reset = () => {
    setQ(""); setHits([]); setSel(null); setCong(null); setDetail(null);
    setAlts(null); setNationAlts(null); setCourse(null); setPicked({}); setErr(null); setMode("place");
  };
  const doSearch = () => run("search", async () => {
    setSel(null); setCong(null); setDetail(null); setAlts(null); setCourse(null);
    setHits(await api.search(q));
  });
  const pickPlace = (p: PlaceHit) => run("cong", async () => {
    setSel(p); setAlts(null); setNationAlts(null); setCourse(null); setPicked({}); setDetail(null); setFocused(false);
    setCong(await api.congestion(p.contentId, date));
    api.detail(p.contentId).then(setDetail).catch(() => {});
  });
  const pickById = (contentId: string, title: string) =>
    pickPlace({ contentId, title, contentTypeId: "12" } as PlaceHit);
  const onFocus = () => {
    setFocused(true);
    if (!popular.length) api.popular(8).then(setPopular).catch(() => {});
  };
  const changeDate = (d: string) => {
    setDate(d);
    if (sel) run("cong", async () => setCong(await api.congestion(sel.contentId, d)));
  };
  const findAlts = () => sel && run("alts", async () => {
    setAlts(await api.alternatives(sel.contentId, date, 3, "nearby"));
    api.alternatives(sel.contentId, date, 3, "nationwide").then(setNationAlts).catch(() => setNationAlts(null));
  });
  const makeCourse = () => run("course", async () => {
    setCourse(await api.course([sel!.contentId, ...Object.keys(picked)], date));
  });

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 text-slate-800">
      <header className="mb-6 flex items-start justify-between">
        <div>
          <button onClick={reset}
            className="cursor-pointer text-2xl font-bold text-teal-600 transition-colors hover:text-teal-800">
            숨은한국
          </button>
          <p className="text-sm text-slate-500">붐비는 곳 말고, 숨은 한국 — 혼잡 예측 기반 여행 추천</p>
        </div>
        <button onClick={() => setShowWish((v) => !v)} className="relative rounded-lg border border-slate-300 px-3 py-1.5 text-sm transition hover:bg-rose-50">
          ♥ 찜{wish.length > 0 && <span className="ml-1 rounded-full bg-rose-500 px-1.5 text-xs text-white">{wish.length}</span>}
        </button>
      </header>

      {/* 위시리스트 패널 */}
      {showWish && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50/40 p-4">
          <div className="flex items-center justify-between">
            <b className="text-sm">내가 찜한 곳 {wish.length}</b>
            <button onClick={() => setShowWish(false)} className="text-xs text-slate-400">닫기</button>
          </div>
          {wish.length === 0 ? (
            <p className="mt-2 text-xs text-slate-500">명소의 ♥ 를 눌러 담아보세요. 담은 곳들로 한 번에 코스를 만들 수 있어요.</p>
          ) : (
            <>
              <ul className="mt-2 divide-y">
                {wish.map((w) => (
                  <li key={w.contentId} className="flex items-center gap-2 py-1.5">
                    {w.image ? <img src={w.image} alt="" className="h-8 w-8 rounded object-cover" /> : <div className="h-8 w-8 rounded bg-slate-100" />}
                    <button onClick={() => { setShowWish(false); pickById(w.contentId, w.title); }} className="flex-1 text-left text-sm hover:text-teal-700">{w.title}</button>
                    <button onClick={() => setWish(removeWish(w.contentId))} className="text-xs text-slate-400 hover:text-rose-500">삭제</button>
                  </li>
                ))}
              </ul>
              <button onClick={makeCourseFromWish} className="mt-3 w-full rounded-lg bg-teal-700 py-2 text-sm font-semibold text-white transition hover:bg-teal-800">
                찜한 {wish.length}곳으로 코스 만들기
              </button>
            </>
          )}
        </div>
      )}
      {toast && <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-800 px-4 py-2 text-sm text-white shadow-lg">{toast}</div>}

      {/* 탭 */}
      <div className="mb-5 flex gap-1 rounded-lg bg-slate-100 p-1">
        {([["place", "장소별 혼잡"], ["trip", "여행 일정 추천"]] as const).map(([m, label]) => (
          <button key={m} onClick={() => setMode(m)}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition ${mode === m ? "bg-white text-teal-700 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
            {label}
          </button>
        ))}
      </div>

      {mode === "trip" && <TripPlanner />}

      {mode === "place" && (<>
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doSearch()}
          onFocus={onFocus}
          placeholder="관광지 검색 (예: 경복궁, 해운대)"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100" />
        <input type="date" value={date} min={plus(0)} max={plus(29)} onChange={(e) => changeDate(e.target.value)}
          className="rounded-lg border border-slate-300 px-2 py-2 text-sm" />
        <button onClick={doSearch} className="rounded-lg bg-teal-600 px-4 py-2 text-white transition hover:bg-teal-700 active:scale-95">검색</button>
      </div>
      {err && <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-600">오류: {err}</p>}
      {loading && <p className="mt-3 animate-pulse text-sm text-slate-400">불러오는 중…</p>}

      {hits.length > 0 && !sel && (
        <ul className="mt-4 divide-y rounded-lg border border-slate-200">
          {hits.map((h) => (
            <li key={h.contentId}>
              <button onClick={() => pickPlace(h)} className="flex w-full items-center gap-3 p-3 text-left transition hover:bg-teal-50">
                {h.image ? <img src={h.image} alt="" className="h-12 w-12 rounded object-cover" /> : <div className="h-12 w-12 rounded bg-slate-100" />}
                <span><b>{h.title}</b><br /><span className="text-xs text-slate-500">{h.addr}</span></span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* 검색 포커스 시: 인기 관광지 (매번 랜덤) */}
      {focused && !sel && hits.length === 0 && popular.length > 0 && (
        <div className="mt-3 rounded-xl border border-slate-200 p-3">
          <p className="mb-2 text-xs font-semibold text-slate-500">인기 관광지</p>
          <div className="flex flex-wrap gap-2">
            {popular.map((p) => (
              <button key={p.contentId} onClick={() => pickById(p.contentId, p.title)}
                className="rounded-full border border-slate-300 px-3 py-1 text-sm text-slate-600 transition hover:bg-teal-50 hover:text-teal-700">
                {p.title}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 홈 유휴: 선택일에 평소보다 한적한 명소 (지역별, 날짜 따라 유동적) */}
      {!sel && hits.length === 0 && highlights.length > 0 && (
        <section className="mt-6 animate-[fadeIn_.3s_ease]">
          <h2 className="text-base font-bold text-slate-800">
            {Number(date.slice(5, 7))}월 {Number(date.slice(8, 10))}일, 평소보다 한적한 명소 🌿
          </h2>
          <p className="mb-3 text-xs text-slate-500">이 날은 아래 명소들이 평소(30일 평균)보다 한산할 것으로 예측돼요. 클릭하면 상세 예보를 볼 수 있어요.</p>
          <div className="space-y-4">
            {highlights.map((rg) => (
              <div key={rg.areaName}>
                <p className="mb-1.5 text-sm font-semibold text-teal-700">{rg.areaName}</p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {rg.spots.map((s) => (
                    <button key={s.contentId} onClick={() => pickById(s.contentId, s.name)}
                      className="flex items-center gap-2 overflow-hidden rounded-lg border border-slate-200 p-2 text-left transition hover:shadow-md">
                      {s.image ? <img src={s.image} alt="" className="h-12 w-12 shrink-0 rounded object-cover" /> : <div className="h-12 w-12 shrink-0 rounded bg-slate-100" />}
                      <span className="min-w-0">
                        <b className="block truncate text-sm">{s.name}</b>
                        <span className="text-[11px] text-slate-500">혼잡 {s.today}</span>
                        <span className="ml-1 rounded bg-green-100 px-1 text-[11px] font-semibold text-green-700">평소 -{s.dropPct}%</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {cong && sel && (
        <section className="mt-6 animate-[fadeIn_.3s_ease] rounded-xl border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{cong.name}</h2>
            <div className="flex items-center gap-2">
              <button onClick={() => toggleWishItem({ contentId: cong.contentId!, title: cong.name, image: sel?.image })}
                className={`text-sm ${isWished(cong.contentId || "") ? "text-rose-500" : "text-slate-400 hover:text-rose-500"}`}>♥</button>
              <button onClick={() => copy(`${location.origin}/?place=${cong.contentId}&date=${date}`, "예보")}
                className="text-xs text-slate-400 transition hover:text-teal-600">🔗 공유</button>
              <button onClick={reset} className="text-xs text-slate-400 transition hover:text-slate-600">← 처음으로</button>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="rounded-full px-3 py-1 text-sm font-bold text-white shadow" style={{ background: cong.color }}>
              {cong.grade} {cong.index}
            </span>
            <span className="text-xs text-slate-500">{date} · {cong.source === "KTO_FORECAST" ? "공사 예측" : "숨은한국 AI 추정"}</span>
            {cong.weather && (
              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs text-sky-700">
                {cong.weather.emoji} {cong.weather.label}{cong.weather.tmp != null ? ` ${cong.weather.tmp}°` : ""}
              </span>
            )}
          </div>
          {cong.note && <p className="mt-1 text-xs text-amber-600">{cong.note}</p>}
          {cong.weather?.note && <p className="mt-1 text-xs text-sky-600">☔ {cong.weather.note}</p>}
          {cong.realtime && (
            <div className="mt-2 flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-1.5 text-xs">
              <span className="font-semibold text-rose-600">● 실시간</span>
              <span>{cong.realtime.area} · <b>{cong.realtime.level}</b>{cong.realtime.min ? ` (${cong.realtime.min}~${cong.realtime.max}명)` : ""}</span>
              <span className="text-slate-400">{cong.realtime.time}</span>
            </div>
          )}

          {/* 이곳에서 무엇을 할 수 있는지 */}
          {detail?.overview && (
            <div className="mt-3 rounded-lg bg-slate-50 p-3">
              <p className="mb-1 text-xs font-semibold text-teal-700">이곳에서는</p>
              <p className="text-xs leading-relaxed text-slate-600">{detail.overview}</p>
              {detail.homepage && <a href={detail.homepage.match(/https?:\/\/[^\s"']+/)?.[0] || "#"} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[11px] text-teal-600 underline">공식 홈페이지</a>}
            </div>
          )}

          <div className="mt-4">
            <HeatCalendar series={cong.series30d} selected={date} onPick={changeDate} />
          </div>

          <button onClick={findAlts}
            className={`mt-4 w-full rounded-lg py-2 font-semibold transition active:scale-95 ${cong.index >= 60 ? "bg-orange-500 text-white hover:bg-orange-600" : "border border-teal-600 text-teal-700 hover:bg-teal-50"}`}>
            {cong.index >= 60 ? "이 날 비슷한데 한적한 곳 찾기" : "비슷한 다른 명소 보기"}
          </button>
        </section>
      )}

      {alts && (
        <section className="mt-6 animate-[fadeIn_.3s_ease]">
          <h3 className="mb-2 font-semibold">한적한 대안 {alts.count}곳</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            {alts.alternatives.map((a) => {
              const on = a.contentId in picked;
              return (
                <div key={a.contentId} className={`flex flex-col rounded-xl border border-slate-200 p-3 shadow-sm transition hover:shadow-md ${on ? "ring-2 ring-teal-600" : ""}`}>
                  <div className="flex items-start justify-between">
                    <b className="text-sm">{a.name}</b>
                    <button onClick={() => toggleWishItem({ contentId: a.contentId, title: a.name })}
                      className={`text-sm ${isWished(a.contentId) ? "text-rose-500" : "text-slate-300 hover:text-rose-500"}`}>♥</button>
                  </div>
                  <p className="mt-1 text-xs text-teal-700">{a.reason}</p>
                  {a.overview && <p className="mt-1 line-clamp-3 text-[11px] leading-snug text-slate-500">{a.overview}</p>}
                  <p className="mt-2 text-[11px] text-slate-500">유사도 {a.simPct}% · 혼잡 {a.congestion} · {a.distanceKm}km</p>
                  <button
                    onClick={() => setPicked((p) => { const n = { ...p }; if (on) delete n[a.contentId]; else n[a.contentId] = a.name; return n; })}
                    className={`mt-2 w-full rounded py-1 text-xs transition active:scale-95 ${on ? "bg-teal-600 text-white" : "border border-slate-300 hover:bg-slate-50"}`}>
                    {on ? "코스에 추가됨 ✓" : "코스에 추가"}
                  </button>
                </div>
              );
            })}
          </div>
          {Object.keys(picked).length > 0 && (
            <button onClick={makeCourse} className="mt-4 w-full rounded-lg bg-teal-700 py-2 font-semibold text-white transition hover:bg-teal-800 active:scale-95">
              {sel?.title} + {Object.keys(picked).length}곳으로 코스 만들기
            </button>
          )}

          {/* 다른 지역은 어떠세요? — 전국에서 비슷한 느낌+더 한적한 곳 */}
          {nationAlts && nationAlts.alternatives.length > 0 && (
            <div className="mt-6 rounded-xl border border-teal-200 bg-teal-50/40 p-4">
              <h4 className="font-semibold text-teal-800">🌏 다른 지역은 어떠세요?</h4>
              <p className="mb-3 text-xs text-slate-500">{sel?.title}와(과) 비슷한 느낌인데, 다른 지역이라 더 한적한 곳이에요.</p>
              <div className="grid gap-3 sm:grid-cols-3">
                {nationAlts.alternatives.map((a) => (
                  <div key={a.contentId} className="flex flex-col rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                    <span className="mb-0.5 w-fit rounded-full bg-teal-600 px-2 py-0.5 text-[10px] font-semibold text-white">{a.region}</span>
                    <b className="text-sm">{a.name}</b>
                    {a.overview && <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-500">{a.overview}</p>}
                    <p className="mt-2 text-[11px] text-slate-500">유사도 {a.simPct}% · 혼잡 {a.congestion} · {a.distanceKm}km</p>
                    <button onClick={() => pickById(a.contentId, a.name)}
                      className="mt-2 w-full rounded border border-teal-500 py-1 text-xs text-teal-700 transition hover:bg-teal-50">
                      이 곳 예보 보기
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {course && (
        <section className="mt-6 animate-[fadeIn_.3s_ease] rounded-xl border border-slate-200 p-4 shadow-sm">
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
          <div className="mt-3 flex gap-2">
            <a href={course.kakaoMapUrl} target="_blank" rel="noreferrer"
              className="inline-block rounded-lg bg-yellow-400 px-4 py-2 text-sm font-semibold transition hover:bg-yellow-300">카카오맵에서 열기</a>
            <button onClick={() => copy(`${location.origin}/?course=${course.legs.map((l) => l.contentId).join(",")}&date=${course.date}`, "코스")}
              className="rounded-lg border border-teal-500 px-4 py-2 text-sm font-semibold text-teal-700 transition hover:bg-teal-50">🔗 코스 공유</button>
          </div>
        </section>
      )}
      </>)}

      <footer className="mt-10 text-center text-[11px] text-slate-400">데이터: 한국관광공사 TourAPI · 기상청</footer>
    </main>
  );
}
