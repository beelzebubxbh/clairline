<template>
  <div v-if="visible" class="modal-overlay" @click.self="handleOverlayClick">
    <div class="modal-card" style="max-width: 480px;">
      <!-- 模态框头部 -->
      <div class="modal-header">
        <div style="font-weight:800; font-size:1.05rem; display:flex; align-items:center; gap:8px;">
          <span v-html="ICONS.shield" style="color:var(--accent-cyan);"></span>
          <span>长龙航空 · 会员登录与凭证同步向导</span>
        </div>
        <button type="button" class="btn-popover-close" style="font-size:1.3rem;" @click="closeModal">&times;</button>
      </div>

      <!-- 模态框主体 -->
      <div class="modal-body" style="padding:18px 20px;">
        
        <!-- 当前状态卡片 -->
        <div 
          style="padding:12px 14px; border-radius:8px; margin-bottom:14px;"
          :style="{ 
            background: effectiveAuth?.is_logged_in ? '#f0fdf4' : '#fffbeb',
            border: effectiveAuth?.is_logged_in ? '1px solid #bbf7d0' : '1px solid #fde68a'
          }"
        >
          <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:10px;">
              <span 
                style="width:10px; height:10px; border-radius:50%; display:inline-block;"
                :style="{ background: effectiveAuth?.is_logged_in ? '#10b981' : '#f59e0b' }"
              ></span>
              <div>
                <div style="font-size:0.85rem; font-weight:800; color:var(--text-primary); display:flex; align-items:center; gap:6px;">
                  <span>{{ effectiveAuth?.is_logged_in ? effectiveAuth.user_name : '尚未同步长龙会员登录态' }}</span>
                  <span 
                    v-if="effectiveAuth?.is_logged_in && (effectiveAuth.is_verified || effectiveAuth.user_name !== '长龙会员')"
                    style="font-size:0.65rem; padding:1px 5px; border-radius:3px; background:#dcfce7; color:#15803d; font-weight:700;"
                  >
                    已实名
                  </span>
                </div>
                <div style="font-size:0.72rem; color:var(--text-muted); margin-top:2px;">
                  {{ effectiveAuth?.is_logged_in ? `手机: ${effectiveAuth.mobile || '已同步'} · 更新: ${effectiveAuth.update_time || '刚刚'}` : '同步后可实时获取航班剩余机位与真实放票日历' }}
                </div>
              </div>
            </div>
            <span 
              v-if="effectiveAuth?.is_logged_in"
              style="font-size:0.72rem; padding:3px 9px; border-radius:4px; background:#e0f2fe; color:#0284c7; font-weight:800; display:inline-flex; align-items:center; gap:4px;"
            >
              <span v-html="ICONS.crown" style="display:inline-flex;"></span>
              <span>{{ effectiveAuth.member_level || '乘云会员' }}</span>
            </span>
          </div>
        </div>

        <!-- 场景 1：如果已经抓取并同步成功，直接展示已就绪状态，不展示“开始同步”大按钮 -->
        <div 
          v-if="effectiveAuth?.is_logged_in && !showResyncFlow && !isCapturing && !captureSuccess"
          style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:18px 16px; text-align:center; margin-bottom:8px;"
        >
          <div style="display:inline-flex; margin-bottom:6px; color:#10b981;" v-html="ICONS.checkCircle"></div>
          <div style="font-size:0.92rem; font-weight:800; color:#047857; margin-bottom:4px;">
            长龙会员凭证已同步生效
          </div>
          <div style="font-size:0.75rem; color:#065f46; line-height:1.5; margin-bottom:16px;">
            当前已建立长龙小程序认证通道，畅飞卡剩余机位与真实放票日历处于就绪状态。
          </div>
          <button 
            type="button" 
            class="btn-glass" 
            style="font-size:0.75rem; color:#0284c7; border-color:#bae6fd; padding:5px 14px; background:#ffffff; display:inline-flex; align-items:center; gap:5px; margin:0 auto;"
            @click="showResyncFlow = true"
          >
            <span v-html="ICONS.refresh" style="display:inline-flex;"></span>
            <span>重新同步或切换账号</span>
          </button>
        </div>

        <!-- 场景 2：未登录、或用户主动点击重新同步、或正在嗅探捕获中 -> 展示向导流程 -->
        <div v-else>
          <!-- 步骤 1：本地安全根证书检查 -->
          <div style="background:#f8fafc; border:1px solid var(--border-subtle); border-radius:6px; padding:12px 14px; margin-bottom:12px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
              <div style="font-size:0.82rem; font-weight:700; display:flex; align-items:center; gap:6px;">
                <span v-html="ICONS.shield" :style="{ color: authStatus?.cert_installed ? '#10b981' : '#f59e0b' }"></span>
                <span>步骤 1：本地安全根证书</span>
              </div>
              <span 
                style="font-size:0.72rem; font-weight:700; padding:2px 8px; border-radius:4px;"
                :style="{ 
                  background: authStatus?.cert_installed ? '#dcfce7' : '#fee2e2',
                  color: authStatus?.cert_installed ? '#15803d' : '#b91c1c'
                }"
              >
                {{ authStatus?.cert_installed ? '已信任' : '待配置' }}
              </span>
            </div>

            <div v-if="authStatus?.cert_installed" style="font-size:0.75rem; color:#15803d;">
              系统已正确信任 mitmproxy 根证书，无需额外配置，可直接进行步骤 2。
            </div>
            <div v-else>
              <div style="font-size:0.75rem; color:#b45309; line-height:1.5; margin-bottom:8px;">
                首次使用需要将本地解密证书加入系统受信任存储区（仅需配置一次）。
              </div>
              <button 
                type="button" 
                class="btn-primary" 
                style="padding:5px 12px; font-size:0.75rem; display:inline-flex; align-items:center; gap:5px;" 
                :disabled="installingCert"
                @click="handleInstallCert"
              >
                <span v-html="ICONS.shield" style="display:inline-flex;"></span>
                <span>{{ installingCert ? '正在安装...' : '一键自动导入根证书' }}</span>
              </button>
              <div style="font-size:0.7rem; color:#94a3b8; margin-top:4px;">
                * 导入时若 Windows 弹出安全警告提示框，请点击“是”允许信任
              </div>
            </div>
          </div>

          <!-- 步骤 2：自动网络嗅探与凭据捕获 -->
          <div style="background:#f8fafc; border:1px solid var(--border-subtle); border-radius:6px; padding:12px 14px;">
            <div style="font-size:0.82rem; font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
              <span v-html="ICONS.radar" style="color:var(--accent-cyan);"></span>
              <span>步骤 2：启动自动嗅探与同步</span>
            </div>

            <!-- 待命状态：尚未开始嗅探 -->
            <div v-if="!isCapturing && !captureSuccess">
              <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.5; margin-bottom:10px;">
                点击下方按钮后，程序将<strong>自动开启系统代理 (127.0.0.1:8080)</strong>。此时只需在电脑版微信中点开<strong>【长龙航空】小程序 ➔ 点击【我的】</strong>，程序捕获凭据后将<strong>全自动关闭系统代理并存入数据库</strong>。
              </div>
              <button 
                type="button" 
                class="btn-primary" 
                style="width:100%; padding:8px 0; font-size:0.82rem; justify-content:center; display:inline-flex; align-items:center; gap:6px;"
                @click="handleStartCapture"
              >
                <span v-html="ICONS.zap" style="display:inline-flex;"></span>
                <span>开始同步长龙登录态 (自动托管代理)</span>
              </button>
            </div>

            <!-- 正在嗅探中 -->
            <div v-else-if="isCapturing && !captureSuccess" style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:12px; text-align:center;">
              <div style="display:inline-block; margin-bottom:8px;">
                <span class="auth-spin-radar" v-html="ICONS.radar"></span>
              </div>
              <div style="font-size:0.82rem; font-weight:800; color:#047857; margin-bottom:4px;">
                Windows 系统代理已自动开启 (127.0.0.1:8080)
              </div>
              <div style="font-size:0.75rem; color:#065f46; line-height:1.5; margin-bottom:12px;">
                请在微信电脑版中打开<strong>【长龙航空】小程序</strong>，务必点击底部的<strong>【我的】</strong>页面加载个人中心...
              </div>
              <button 
                type="button" 
                class="btn-glass" 
                style="padding:4px 14px; font-size:0.75rem;" 
                @click="handleStopCapture"
              >
                取消同步 (自动关闭系统代理)
              </button>
            </div>

            <!-- 捕获成功状态 -->
            <div v-else-if="captureSuccess" style="background:#ecfdf5; border:1px solid #6ee7b7; border-radius:6px; padding:12px; text-align:center;">
              <div style="display:inline-flex; margin-bottom:6px; color:#10b981;" v-html="ICONS.checkCircle"></div>
              <div style="font-size:0.88rem; font-weight:800; color:#047857; margin-bottom:4px;">
                长龙会员凭据同步成功！
              </div>
              <div style="font-size:0.75rem; color:#065f46;">
                Windows 系统代理已全自动恢复关闭，网络恢复正常直连。
              </div>
            </div>
          </div>
        </div>
      </div>



      <!-- 模态框底部 -->
      <div class="modal-footer" style="justify-content: space-between; align-items:center;">
        <div style="display:flex; align-items:center; gap:8px;">
          <button 
            type="button" 
            class="btn-glass" 
            style="font-size:0.7rem; color:#ef4444; border-color:#fecaca; padding:3px 8px;"
            title="清空 credentials.json 与数据库个人信息，还原为新用户状态"
            @click="handleResetAuth"
          >
            清空登录态 (重置)
          </button>
          <button 
            v-if="authStatus?.cert_installed"
            type="button" 
            class="btn-glass" 
            style="font-size:0.7rem; color:#f59e0b; border-color:#fed7aa; padding:3px 8px;"
            title="从 Windows 系统证书库中移除 mitmproxy 根证书，测试全新安装流程"
            @click="handleUninstallCert"
          >
            卸载证书测试
          </button>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
          <a 
            href="https://github.com/eureka-wu/clairline" 
            target="_blank" 
            rel="noopener noreferrer"
            style="font-size:0.7rem; color:var(--text-muted); text-decoration:none; display:inline-flex; align-items:center; gap:4px;"
            title="GitHub 开源仓库"
          >
            <span v-html="ICONS.github" style="display:inline-flex;"></span>
            <span>eureka-wu/clairline</span>
          </a>
          <button type="button" class="btn-glass" style="font-size:0.78rem;" @click="closeModal">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue';
import { ICONS } from '../data/icons.js';
import { startCapture, stopCapture, fetchCaptureStatus, installCert, uninstallCert, resetAuth, fetchAuthStatus } from '../api/auth.js';


const props = defineProps({
  visible: Boolean,
  authStatus: Object,
  autoStart: Boolean
});

const emit = defineEmits(['close', 'synced', 'refresh-auth']);

const isCapturing = ref(false);
const captureSuccess = ref(false);
const installingCert = ref(false);
const localAuth = ref(null);
let pollTimer = null;

const effectiveAuth = computed(() => {
  return localAuth.value || props.authStatus || {};
});

watch(() => props.visible, (val) => {
  if (val) {
    captureSuccess.value = false;
    localAuth.value = null;
    emit('refresh-auth');
    if (props.autoStart && !isCapturing.value) {
      setTimeout(() => {
        handleStartCapture();
      }, 250);
    }
  } else {
    if (isCapturing.value) {
      handleStopCapture();
    }
  }
});

function notify(title, message, type = 'info') {
  if (typeof window !== 'undefined' && window.$dialog) {
    window.$dialog(title, message, type);
  } else {
    alert(`${title}: ${message}`);
  }
}

async function handleInstallCert() {
  installingCert.value = true;
  try {
    const res = await installCert();
    if (res.ok) {
      notify('证书安装成功', '根证书已成功导入系统受信任存储区！', 'success');
      emit('refresh-auth');
    } else {
      notify('证书导入提示', res.error || '未完成导入，请检查系统权限', 'warning');
    }
  } catch (e) {
    notify('操作失败', e.message || '证书安装异常', 'error');
  } finally {
    installingCert.value = false;
  }
}

async function handleResetAuth() {
  if (!confirm('确定清空本地登录凭据与会员信息？将模拟纯净新用户状态。')) return;
  try {
    const res = await resetAuth();
    if (res.ok) {
      notify('重置成功', '已彻底清空本地会员凭据，恢复为纯净新用户状态！', 'success');
      emit('refresh-auth');
      emit('synced');
    }
  } catch (e) {
    notify('重置失败', e.message || '重置异常', 'error');
  }
}

async function handleUninstallCert() {
  if (!confirm('确定从 Windows 信任库中移除 mitmproxy 根证书以测试首次安装流程？')) return;
  try {
    const res = await uninstallCert();
    if (res.ok) {
      notify('证书移除完成', '已成功移除根证书！当前状态将变为未信任。', 'info');
      emit('refresh-auth');
    }
  } catch (e) {
    notify('卸载失败', e.message || '卸载异常', 'error');
  }
}


async function handleStartCapture() {
  try {
    const res = await startCapture();
    if (res.ok) {
      isCapturing.value = true;
      captureSuccess.value = false;
      startPolling();
    } else {
      notify('启动嗅探失败', res.error || '未知原因', 'error');
    }
  } catch (e) {
    notify('网络请求异常', e.message || '无法连接本地后台服务', 'error');
  }
}

async function handleStopCapture() {
  stopPolling();
  isCapturing.value = false;
  try {
    await stopCapture();
  } catch (e) {}
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const res = await fetchCaptureStatus();
      if (res && res.status === 'success') {
        stopPolling();
        isCapturing.value = false;
        captureSuccess.value = true;
        if (res.auth && res.auth.is_logged_in) {
          localAuth.value = res.auth;
        }
        emit('refresh-auth', res.auth);
        emit('synced');
        // 瞬间丝滑过渡：400ms 快速关闭抓包框，立刻无缝拉起全屏发光雷达普查
        setTimeout(() => {
          closeModal();
        }, 400);
      } else if (res && res.status === 'error') {
        stopPolling();
        isCapturing.value = false;
        notify('嗅探异常', res.message || '嗅探进程异常退出，详情请查看 logs/ 目录', 'error');
      } else if (res && res.status === 'idle' && isCapturing.value) {
        // 后台由于某种原因退出
        stopPolling();
        isCapturing.value = false;
      }
    } catch (e) {
      stopPolling();
      isCapturing.value = false;
    }
  }, 1000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function handleOverlayClick() {
  if (!isCapturing.value) {
    closeModal();
  }
}

function closeModal() {
  if (isCapturing.value) {
    handleStopCapture();
  }
  emit('close');
}

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.auth-spin-radar {
  display: inline-flex;
  color: #10b981;
  animation: radar-pulse 1.8s linear infinite;
}

@keyframes radar-pulse {
  0% { transform: scale(0.95); opacity: 0.7; }
  50% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.7; }
}
</style>
