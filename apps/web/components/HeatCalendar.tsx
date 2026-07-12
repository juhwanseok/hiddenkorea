"use client";
import type { DayCongestion } from "@/lib/api";

const WD = ["일", "월", "화", "수", "목", "금", "토"];

export default function HeatCalendar({
  series, selected, onPick,
}: { series: DayCongestion[]; selected: string; onPick: (d: string) => void }) {
  if (series.length === 0) return null;
  const first = new Date(series[0].date + "T00:00:00");
  const lead = first.getDay(); // 0=일
  const cells: (DayCongestion | null)[] = [...Array(lead).fill(null), ...series];

  // 월 라벨(첫 날짜 기준)
  const monthLabel = `${first.getFullYear()}.${first.getMonth() + 1}`;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <p className="text-xs text-slate-500">향후 30일 혼잡 달력 (칸 클릭 = 날짜 선택)</p>
        <span className="text-xs font-medium text-slate-400">{monthLabel}~</span>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {WD.map((w, i) => (
          <div key={w} className={`text-center text-[11px] font-semibold ${i === 0 ? "text-red-500" : i === 6 ? "text-blue-500" : "text-slate-400"}`}>{w}</div>
        ))}
        {cells.map((d, i) =>
          d === null ? (
            <div key={`e${i}`} />
          ) : (
            <button key={d.date} title={`${d.date} ${d.grade} ${d.index}`} onClick={() => onPick(d.date)}
              className={`group flex aspect-square flex-col items-center justify-center rounded-md text-white transition-transform hover:scale-105 ${d.date === selected ? "ring-2 ring-offset-1 ring-teal-800" : ""}`}
              style={{ background: d.color }}>
              <span className="text-[11px] font-bold leading-none">{Number(d.date.slice(8))}</span>
              <span className="mt-0.5 text-[8px] leading-none opacity-90">{d.index}</span>
            </button>
          )
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
        {[["여유", "#22c55e"], ["보통", "#eab308"], ["다소혼잡", "#f97316"], ["혼잡", "#ef4444"], ["매우혼잡", "#991b1b"]].map(([n, c]) => (
          <span key={n} className="flex items-center gap-1"><i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: c as string }} />{n}</span>
        ))}
      </div>
    </div>
  );
}
