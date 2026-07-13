// 위시리스트 — localStorage 영속 (백엔드 불필요)
export type WishItem = { contentId: string; title: string; image?: string | null };
const KEY = "hk_wishlist";

export function getWishlist(): WishItem[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}
function save(list: WishItem[]) {
  localStorage.setItem(KEY, JSON.stringify(list));
}
export function isWished(id: string): boolean {
  return getWishlist().some((w) => w.contentId === id);
}
export function toggleWish(item: WishItem): WishItem[] {
  const list = getWishlist();
  const i = list.findIndex((w) => w.contentId === item.contentId);
  if (i >= 0) list.splice(i, 1);
  else list.push({ contentId: item.contentId, title: item.title, image: item.image ?? null });
  save(list);
  return list;
}
export function removeWish(id: string): WishItem[] {
  const list = getWishlist().filter((w) => w.contentId !== id);
  save(list);
  return list;
}
