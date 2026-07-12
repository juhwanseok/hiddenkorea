"use client";
import { useEffect, useRef, useState } from "react";

type Stop = { seq: number; name: string; lat: number; lon: number };
declare global { interface Window { kakao: any } }

const KEY = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY;
const SDK_ID = "kakao-maps-sdk";

function loadSdk(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.kakao?.maps) return resolve();
    const exist = document.getElementById(SDK_ID) as HTMLScriptElement | null;
    const onload = () => window.kakao.maps.load(() => resolve());
    if (exist) { exist.addEventListener("load", onload); return; }
    const s = document.createElement("script");
    s.id = SDK_ID; s.async = true;
    s.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false`;
    s.onload = onload;
    s.onerror = () => reject(new Error("Kakao SDK 로드 실패"));
    document.head.appendChild(s);
  });
}

export default function KakaoMap({ stops }: { stops: Stop[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!KEY || !ref.current || stops.length === 0) return;
    let cancelled = false;
    loadSdk().then(() => {
      if (cancelled || !ref.current) return;
      const { kakao } = window;
      const map = new kakao.maps.Map(ref.current, {
        center: new kakao.maps.LatLng(stops[0].lat, stops[0].lon), level: 6,
      });
      const bounds = new kakao.maps.LatLngBounds();
      const path: any[] = [];
      stops.forEach((s) => {
        const pos = new kakao.maps.LatLng(s.lat, s.lon);
        path.push(pos); bounds.extend(pos);
        new kakao.maps.Marker({ map, position: pos, title: s.name });
        new kakao.maps.CustomOverlay({
          map, position: pos, yAnchor: 2.2,
          content: `<div style="background:#0d9488;color:#fff;border-radius:9999px;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700">${s.seq}</div>`,
        });
      });
      new kakao.maps.Polyline({
        map, path, strokeWeight: 4, strokeColor: "#0d9488", strokeOpacity: 0.8, strokeStyle: "solid",
      });
      map.setBounds(bounds);
    }).catch((e) => setErr(String(e.message || e)));
    return () => { cancelled = true; };
  }, [stops]);

  if (!KEY) {
    return (
      <div className="mt-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center text-xs text-slate-500">
        카카오맵 지도를 보려면 <code>NEXT_PUBLIC_KAKAO_MAP_KEY</code>를 설정하세요.<br />
        (아래 &lsquo;카카오맵에서 열기&rsquo; 링크는 키 없이도 동작합니다)
      </div>
    );
  }
  return (
    <div className="mt-3">
      {err && <p className="mb-1 text-xs text-red-500">지도 오류: {err} (도메인 등록 확인)</p>}
      <div ref={ref} className="h-64 w-full rounded-lg border border-slate-200" />
    </div>
  );
}
