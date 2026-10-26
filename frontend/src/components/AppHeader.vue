<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="brand-area">
        <div class="brand-icon" v-html="ICONS.plane"></div>
        <div class="brand-title">长龙航线</div>

        <!-- Tab Segmented 切换 -->
        <nav class="tab-segmented">
          <button 
            type="button"
            class="tab-btn" 
            :class="{ active: currentTab === 'routes' }"
            @click="$emit('update:currentTab', 'routes')"
          >
            <span v-html="ICONS.plane"></span>
            <span>航线探索</span>
          </button>
          <button 
            type="button"
            class="tab-btn" 
            :class="{ active: currentTab === 'map' }"
            @click="$emit('update:currentTab', 'map')"
          >
            <span v-html="ICONS.compass"></span>
            <span>地图探索</span>
          </button>
        </nav>
      </div>

      <div class="header-actions" style="display:flex; align-items:center; gap:8px;">
        <!-- 会员身份同步状态胶囊 / 按钮 -->
        <button 
          v-if="authStatus?.is_logged_in"
          type="button"
          class="btn-glass"
          style="padding:5px 10px; font-size:0.78rem; display:inline-flex; align-items:center; gap:6px;"
          @click="$emit('open-auth')"
          :title="`凭据有效 · 更新于 ${authStatus.update_time || '刚刚'} (点击可重新同步)`"
        >
          <span style="width:7px; height:7px; border-radius:50%; background:#10b981; box-shadow:0 0 6px rgba(16,185,129,0.7); display:inline-block;"></span>
          <span v-html="ICONS.user" style="color:#0284c7; display:inline-flex;"></span>
          <span style="font-weight:700;">{{ authStatus.user_name || '长龙会员' }}</span>
          <span v-if="authStatus.member_level" style="font-size:0.68rem; padding:1px 6px; border-radius:4px; background:#eff6ff; color:#2563eb; font-weight:700;">{{ authStatus.member_level }}</span>
          <span v-else-if="authStatus.mobile" style="color:var(--text-muted); font-size:0.72rem;">{{ authStatus.mobile }}</span>
        </button>


        <button 
          v-else
          type="button"
          class="btn-primary"
          style="padding:5px 12px; font-size:0.78rem; background:linear-gradient(135deg, #0284c7, #0369a1); display:inline-flex; align-items:center; gap:5px;"
          @click="$emit('open-auth')"
          title="点击同步微信长龙登录凭据，解锁机位实时查询"
        >
          <span v-html="ICONS.zap" style="display:inline-flex;"></span>
          <span>同步长龙登录</span>
        </button>


        <!-- 航线监控按钮 -->
        <button 
          type="button" 
          class="btn-glass"
          :class="{ 'is-patrolling': patrolState?.running }"
          @click="$emit('open-patrol')"
          title="航线监控与全网放票普查"
        >
          <span 
            v-html="ICONS.radar" 
            :class="{ 'spin-icon': patrolState?.running }"
          ></span>
          <span>{{ headerLabel }}</span>
        </button>

        <!-- GitHub 仓库链接 -->
        <a 
          href="https://github.com/eureka-wu/clairline" 
          target="_blank" 
          rel="noopener noreferrer"
          class="btn-glass"
          style="padding:5px 9px; display:inline-flex; align-items:center; gap:5px; text-decoration:none; color:inherit; font-size:0.75rem;"
          title="访问 GitHub 开源仓库 (eureka-wu/clairline)"
        >
          <span v-html="ICONS.github" style="display:inline-flex;"></span>
          <span style="font-weight:600;">GitHub</span>
        </a>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue';
import { ICONS } from '../data/icons.js';

const props = defineProps({
  currentTab: {
    type: String,
    default: 'routes'
  },
  patrolState: {
    type: Object,
    default: () => ({ running: false, mode: 'idle', completed: 0, total: 0 })
  },
  authStatus: {
    type: Object,
    default: () => ({ is_logged_in: false, user_name: '', mobile: '', cert_installed: false })
  }
});

defineEmits(['update:currentTab', 'open-patrol', 'open-auth']);

const headerLabel = computed(() => {
  if (!props.patrolState?.running) {
    // 待命或巡检完成时：右侧彻底不显示数字，呈现清爽极简的「航线监控」
    return '航线监控';
  }
  const { mode, completed, total } = props.patrolState;
  const isAll = mode === 'all';
  const safeTotal = total > 0 ? total : (isAll ? 397 : 30);
  const prefix = isAll ? '普查中' : '监控中';
  return `${prefix} ${completed}/${safeTotal}`;
});
</script>
