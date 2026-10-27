/**
 * 会员认证 API 接口层（手机短信直登）
 */

export async function fetchAuthStatus() {
  const res = await fetch('/api/auth/status');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

/** 发送短信验证码。checkParam 来自网易易盾滑块通过后的 validate */
export async function sendSmsCode(mobile, checkParam) {
  const res = await fetch('/api/auth/send-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mobile, checkParam })
  });
  return await res.json();
}

/** 提交短信验证码完成登录 */
export async function loginWithSmsCode(mobile, code, verifyId) {
  const res = await fetch('/api/auth/login-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mobile, code, verifyId })
  });
  return await res.json();
}

/** 清空本地登录态 */
export async function resetAuth() {
  const res = await fetch('/api/auth/reset', { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}