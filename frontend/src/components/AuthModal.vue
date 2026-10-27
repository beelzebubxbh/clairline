<template>
  <transition name="am-fade">
    <div v-if="visible" class="am-overlay" @click.self="close">
      <div class="am-panel">
        <header class="am-head">
          <div class="am-title">
            <span class="am-icon">✈</span>
            <div>
              <h2>{{ authStatus?.is_logged_in ? '长龙会员' : '手机号登录' }}</h2>
              <p>{{ authStatus?.is_logged_in ? '已绑定畅飞卡，可直接查询放票' : '短信验证码直登，无需抓包与证书' }}</p>
            </div>
          </div>
          <button class="am-close" @click="close" title="关闭">✕</button>
        </header>

        <!-- 已登录 -->
        <section v-if="authStatus?.is_logged_in" class="am-body">
          <div class="am-profile">
            <div class="am-avatar">{{ (authStatus.user_name || '长').slice(0, 1) }}</div>
            <div class="am-info">
              <div class="am-name">
                {{ authStatus.user_name }}
                <span class="am-level">{{ authStatus.member_level }}</span>
              </div>
              <div class="am-meta">
                <span v-if="authStatus.mobile">手机 {{ authStatus.mobile }}</span>
                <span v-if="authStatus.is_verified" class="am-ok">已实名</span>
                <span v-else class="am-warn">未实名</span>
              </div>
              <div class="am-time">上次登录：{{ authStatus.update_time || '—' }}</div>
            </div>
          </div>

          <div class="am-note">
            登录态失效后需要重新用手机验证码登录一次。程序会先尝试自动续期，但官方未公开该接口，不保证成功。
          </div>

          <div class="am-actions">
            <button class="am-btn ghost" @click="handleLogout" :disabled="busy">退出登录</button>
            <button class="am-btn primary" @click="close">完成</button>
          </div>
        </section>

        <!-- 未登录 -->
        <section v-else class="am-body">
          <label class="am-field">
            <span>手机号</span>
            <input
              v-model="mobile"
              type="tel"
              inputmode="numeric"
              maxlength="11"
              placeholder="长龙航空注册手机号"
              @keyup.enter="handleSend"
            />
          </label>

          <label class="am-field">
            <span>短信验证码</span>
            <div class="am-code-row">
              <input
                ref="codeInput"
                v-model="code"
                class="sms-code-input"
                type="tel"
                inputmode="numeric"
                maxlength="6"
                placeholder="6 位数字"
                @keyup.enter="handleLogin"
              />
              <button
                class="am-code-btn"
                :disabled="countdown > 0 || sending"
                @click="handleSend"
              >{{ countdown > 0 ? `${countdown}s` : (sending ? '发送中…' : '获取验证码') }}</button>
            </div>
          </label>

          <p v-if="error" class="am-error">{{ error }}</p>
          <p v-else-if="hint" class="am-hint">{{ hint }}</p>

          <button class="am-btn primary block" :disabled="busy || !mobile || !code" @click="handleLogin">
            {{ busy ? '登录中…' : '立即登录' }}
          </button>

          <p class="am-tip">
            验证码由长龙航空官方下发，手机号与 Token 只保存在本机
            <code>~/.clairline/</code>，不会上传到任何第三方。
          </p>
        </section>

        <!-- 易盾滑块挂载点 -->
        <div id="yidun-captcha-box" style="display:none;"></div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue';
import { sendSmsCode, loginWithSmsCode, resetAuth } from '../api/auth.js';

const props = defineProps({
  visible: { type: Boolean, default: false },
  authStatus: { type: Object, default: () => ({}) }
});
const emit = defineEmits(['close', 'synced', 'refresh-auth']);

// 网易易盾验证码 ID（与长龙官网使用同一个）
const CAPTCHA_ID = 'd574bdc4ef2f474f9d21fe3c59291491';

const mobile = ref('');
const code = ref('');
const verifyId = ref('');
const countdown = ref(0);
const sending = ref(false);
const busy = ref(false);
const error = ref('');
const hint = ref('');
const codeInput = ref(null);

let captchaInstance = null;
let timer = null;

function close() {
  emit('close');
}

function resetState() {
  mobile.value = '';
  code.value = '';
  verifyId.value = '';
  countdown.value = 0;
  error.value = '';
  hint.value = '';
  sending.value = false;
  busy.value = false;
  if (timer) { clearInterval(timer); timer = null; }
}

function startCountdown() {
  countdown.value = 60;
  if (timer) clearInterval(timer);
  timer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) { clearInterval(timer); timer = null; }
  }, 1000);
}

function handleSend() {
  error.value = '';
  hint.value = '';
  const m = (mobile.value || '').trim();
  if (!/^1[3-9]\d{9}$/.test(m)) {
    error.value = '请输入正确的 11 位手机号';
    return;
  }
  if (typeof window.initNECaptcha !== 'function') {
    error.value = '安全验证组件未加载（需联网加载网易易盾 SDK），请检查网络后重试';
    return;
  }

  try {
    window.initNECaptcha({
      captchaId: CAPTCHA_ID,
      element: '#yidun-captcha-box',
      mode: 'popup',
      width: 320,
      onVerify: async (err, data) => {
        if (err) return; // 滑块未通过，易盾自己会刷新，不打断用户
        const validate = data?.validate || '';
        if (!validate) return;
        await doSend(m, validate);
      },
      onClose: () => { sending.value = false; }
    }, (instance) => {
      captchaInstance = instance;
      captchaInstance.popUp();
    }, (err) => {
      sending.value = false;
      error.value = '安全组件初始化失败：' + (err?.message || '请检查网络');
    });
  } catch (e) {
    sending.value = false;
    error.value = '安全组件异常：' + (e.message || e);
  }
}

async function doSend(m, validate) {
  sending.value = true;
  try {
    const res = await sendSmsCode(m, validate);
    if (res.ok) {
      verifyId.value = res.verifyId || '';
      startCountdown();
      hint.value = '验证码已下发，请查收短信';
      await nextTick();
      codeInput.value?.focus();
    } else {
      error.value = res.error || '发送失败';
    }
  } catch (e) {
    error.value = e.message || '发送失败';
  } finally {
    sending.value = false;
  }
}

async function handleLogin() {
  error.value = '';
  if (!/^\d{6}$/.test((code.value || '').trim())) {
    error.value = '请输入 6 位短信验证码';
    return;
  }
  busy.value = true;
  try {
    const res = await loginWithSmsCode((mobile.value || '').trim(), code.value.trim(), verifyId.value);
    if (res.ok) {
      emit('synced', res);
      emit('close');
      resetState();
    } else {
      error.value = res.error || '登录失败';
    }
  } catch (e) {
    error.value = e.message || '登录失败';
  } finally {
    busy.value = false;
  }
}

async function handleLogout() {
  if (!window.confirm('确定要退出登录吗？本地凭据会被清空，需要重新接收短信验证码。')) return;
  busy.value = true;
  try {
    await resetAuth();
    emit('refresh-auth');
    emit('close');
  } catch (e) {
    error.value = e.message || '退出失败';
  } finally {
    busy.value = false;
  }
}

watch(() => props.visible, (v) => {
  if (v) resetState();
});
</script>

<style scoped>
.am-overlay {
  position: fixed; inset: 0; z-index: 3100;
  background: rgba(15, 23, 42, 0.45); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.am-panel {
  width: min(430px, 100%); background: var(--bg-surface);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow: hidden;
}
.am-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 18px 20px 14px; border-bottom: 1px solid var(--border-subtle);
}
.am-title { display: flex; gap: 12px; align-items: center; }
.am-icon {
  width: 36px; height: 36px; border-radius: 50%;
  background: #eff6ff; color: #2563eb; display: grid; place-items: center; font-size: 17px;
}
.am-title h2 { margin: 0; font-size: 1rem; color: var(--text-primary); }
.am-title p { margin: 2px 0 0; font-size: 0.76rem; color: var(--text-muted); }
.am-close {
  border: none; background: transparent; cursor: pointer; padding: 4px 8px;
  color: var(--text-dim); border-radius: var(--radius-sm); font-size: 0.95rem;
}
.am-close:hover { background: #f1f5f9; color: var(--text-primary); }

.am-body { padding: 18px 20px 20px; }

.am-profile { display: flex; gap: 14px; align-items: center; margin-bottom: 14px; }
.am-avatar {
  width: 48px; height: 48px; border-radius: 50%; flex: none;
  background: linear-gradient(135deg, #34d399, #059669); color: #fff;
  display: grid; place-items: center; font-size: 1.1rem; font-weight: 700;
}
.am-name { font-size: 1rem; font-weight: 700; color: var(--text-primary); display: flex; gap: 8px; align-items: center; }
.am-level {
  font-size: 0.68rem; font-weight: 600; color: #b45309; background: #fef3c7;
  padding: 1px 7px; border-radius: var(--radius-full);
}
.am-meta { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; display: flex; gap: 10px; }
.am-ok { color: var(--accent-emerald); }
.am-warn { color: #b45309; }
.am-time { font-size: 0.72rem; color: var(--text-dim); margin-top: 4px; }

.am-note {
  font-size: 0.75rem; color: var(--text-muted); background: #f8fafc;
  border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
  padding: 9px 12px; line-height: 1.5; margin-bottom: 16px;
}

.am-field { display: block; margin-bottom: 14px; }
.am-field > span { display: block; font-size: 0.75rem; color: var(--text-muted); font-weight: 600; margin-bottom: 6px; }
.am-field input {
  width: 100%; box-sizing: border-box; padding: 10px 12px;
  border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
  font-size: 0.9rem; color: var(--text-primary); background: #fff; outline: none;
}
.am-field input:focus { border-color: var(--border-focus); }
.am-code-row { display: flex; gap: 8px; }
.am-code-row input { flex: 1; letter-spacing: 2px; }
.am-code-btn {
  flex: none; min-width: 108px; padding: 0 14px; cursor: pointer;
  border: 1px solid var(--accent-emerald-border); background: var(--accent-emerald-light);
  color: var(--accent-emerald); border-radius: var(--radius-md);
  font-size: 0.8rem; font-weight: 600;
}
.am-code-btn:disabled { opacity: .55; cursor: default; }

.am-error {
  font-size: 0.78rem; color: #b91c1c; background: #fef2f2;
  border: 1px solid #fecaca; border-radius: var(--radius-md);
  padding: 8px 12px; margin: 0 0 14px;
}
.am-hint { font-size: 0.78rem; color: var(--accent-emerald); margin: 0 0 14px; }

.am-btn {
  border: none; cursor: pointer; border-radius: var(--radius-full);
  padding: 10px 20px; font-size: 0.86rem; font-weight: 600;
}
.am-btn.primary { background: var(--accent-emerald); color: #fff; }
.am-btn.ghost { background: #f1f5f9; color: var(--text-secondary); }
.am-btn.block { width: 100%; }
.am-btn:disabled { opacity: .55; cursor: default; }
.am-actions { display: flex; justify-content: flex-end; gap: 10px; }

.am-tip {
  font-size: 0.71rem; color: var(--text-dim); line-height: 1.6;
  margin: 14px 0 0; text-align: center;
}
.am-tip code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }

.am-fade-enter-active, .am-fade-leave-active { transition: opacity .16s; }
.am-fade-enter-from, .am-fade-leave-to { opacity: 0; }
</style>