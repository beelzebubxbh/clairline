/**
 * 会员认证、证书自检与嗅探抓包 API 接口层
 */

export async function fetchAuthStatus() {
  const res = await fetch('/api/auth/status');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function startCapture() {
  const res = await fetch('/api/capture/start', {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function stopCapture() {
  const res = await fetch('/api/capture/stop', {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function fetchCaptureStatus() {
  const res = await fetch('/api/capture/status');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function installCert() {
  const res = await fetch('/api/cert/install', {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function uninstallCert() {
  const res = await fetch('/api/cert/uninstall', {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function resetAuth() {
  const res = await fetch('/api/auth/reset', {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

