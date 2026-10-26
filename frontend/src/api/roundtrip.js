/**
 * 往返组合搜索 API 接口层
 */

export async function fetchRoundtripCities() {
  const res = await fetch('/api/roundtrip/cities');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function searchRoundtrip(payload) {
  const res = await fetch('/api/roundtrip/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.authExpired = !!data.authExpired;
    throw err;
  }
  return data;
}