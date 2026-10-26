<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-card">
      <!-- 模态框头部 -->
      <div class="modal-header">
        <div style="font-weight:800; font-size:1.05rem; display:flex; align-items:center; gap:8px;">
          <span v-html="ICONS.radar" style="color:var(--accent-cyan);"></span>
          <span>航线监控与全网普查</span>
        </div>
        <button type="button" class="btn-popover-close" style="font-size:1.3rem;" @click="$emit('close')">&times;</button>
      </div>

      <!-- 双模式切换 Tab 标签导航 (彻底解决“为什么点进来全是热门巡检”的认知混淆) -->
      <div style="padding:10px 20px 0; background:#f8fafc; border-bottom:1px solid #e2e8f0; display:flex; gap:12px;">
        <button 
          type="button" 
          @click="activeTab = 'hot'"
          style="padding:8px 16px; font-size:0.82rem; font-weight:700; border:none; background:transparent; cursor:pointer; position:relative; transition:all 0.2s; display:inline-flex; align-items:center; gap:6px;"
          :style="{ 
            color: activeTab === 'hot' ? 'var(--accent-cyan)' : '#64748b',
            borderBottom: activeTab === 'hot' ? '2px solid var(--accent-cyan)' : '2px solid transparent'
          }"
        >
          <span v-html="ICONS.star" style="display:inline-flex;"></span>
          <span>重点监控航线 (自定义 30 条)</span>
        </button>
        <button 
          type="button" 
          @click="activeTab = 'all'"
          style="padding:8px 16px; font-size:0.82rem; font-weight:700; border:none; background:transparent; cursor:pointer; position:relative; transition:all 0.2s; display:inline-flex; align-items:center; gap:6px;"
          :style="{ 
            color: activeTab === 'all' ? '#059669' : '#64748b',
            borderBottom: activeTab === 'all' ? '2px solid #059669' : '2px solid transparent'
          }"
        >
          <span v-html="ICONS.globe" style="display:inline-flex;"></span>
          <span>全网航网普查 (397 条)</span>
        </button>
      </div>


      <!-- 模态框主体 -->
      <div class="modal-body" style="padding:16px 20px;">
        
        <!-- ==================== 选项卡 1：重点监控航线 (自定义 30 条) ==================== -->
        <div v-show="activeTab === 'hot'">
          <!-- 状态提示条 -->
          <div style="padding:8px 12px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:4px; background:#0284c7; color:#fff;">
                监控席位: {{ routes.length }} / 30 {{ routes.length >= 30 ? '满载' : '未满' }}
              </span>
              <span style="font-size:0.75rem; color:#1e40af;">
                {{ routes.length >= 30 ? '已达上限，删一个方可添加一个' : `还可以添加 ${30 - routes.length} 条心愿航线` }}
              </span>
            </div>
            <!-- 自动轮巡总开关 -->
            <label style="display:inline-flex; align-items:center; gap:6px; cursor:pointer; font-size:0.75rem; font-weight:700; color:#334155;">
              <input 
                type="checkbox" 
                :checked="switches.hot_enabled" 
                @change="onSwitchChange('hot_enabled', $event.target.checked)"
                style="accent-color:#0284c7;"
              >
              <span>后台自动轮巡: {{ switches.hot_enabled ? '已启用 (每25分钟)' : '已停用' }}</span>
            </label>
          </div>

          <!-- 已选航线 Tag 网格 -->
          <div style="margin-bottom:12px;">
            <div style="font-size:0.8rem; font-weight:700; color:var(--text-primary); margin-bottom:6px;">
              已关注重点监控航线 (点击右侧 × 可移除释放槽位):
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px; max-height:140px; overflow-y:auto; padding:4px 0;">
              <span 
                v-for="(r, idx) in routes" 
                :key="idx"
                style="display:inline-flex; align-items:center; gap:6px; background:#f1f5f9; border:1px solid #cbd5e1; padding:3px 8px; border-radius:4px; font-size:0.75rem; font-weight:700; color:#334155;"
              >
                <span>{{ r[0] }} ➔ {{ r[1] }}</span>
                <button 
                  type="button" 
                  @click="removeRoute(idx)"
                  style="border:none; background:transparent; color:#94a3b8; font-weight:bold; cursor:pointer; font-size:0.85rem;"
                  title="移除"
                >&times;</button>
              </span>
            </div>
          </div>

          <!-- 添加新航线 -->
          <div style="background:#f8fafc; border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:10px 14px; margin-bottom:14px;">
            <div style="font-size:0.8rem; font-weight:700; color:var(--text-primary); margin-bottom:6px; display:flex; align-items:center; justify-content:space-between;">
              <span>添加新监控航线</span>
              <span v-if="routes.length >= 30" style="font-size:0.72rem; color:#ef4444; font-weight:normal;">
                席位已满，请先点击上方已有航线的 × 移除一条
              </span>
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <select v-model="newFrom" :disabled="routes.length >= 30" class="custom-select-native" style="padding:4px 8px; font-size:0.8rem;">
                <option v-for="c in availableOrigins" :key="c" :value="c">{{ c }}</option>
              </select>
              <span style="color:#94a3b8;">➔</span>
              <select v-model="newTo" :disabled="routes.length >= 30" class="custom-select-native" style="padding:4px 8px; font-size:0.8rem;">
                <option v-for="c in availableDestsForNew" :key="c" :value="c">{{ c }}</option>
              </select>
              <button 
                type="button" 
                class="btn-primary" 
                style="padding:5px 12px; font-size:0.78rem;" 
                :disabled="routes.length >= 30 || !newFrom || !newTo"
                @click="addRoute"
              >
                加入监控
              </button>
            </div>
          </div>

          <!-- 立即执行 30 条重点监控 -->
          <div style="background:#f0f9ff; border:1px solid #bae6fd; border-radius:6px; padding:10px 14px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
            <div>
              <div style="font-size:0.82rem; font-weight:700; color:#0369a1;">手动即时监控</div>
              <div style="font-size:0.72rem; color:#0284c7;">慢速拟人防风控节奏（~4秒/条），更新在库日历，约 2 分钟完成</div>
            </div>
            <button 
              type="button" 
              class="btn-primary" 
              style="padding:6px 14px; font-size:0.78rem; display:inline-flex; align-items:center; gap:5px;"
              :disabled="patrolState.running"
              @click="triggerManual('hot')"
            >
              <span v-html="ICONS.play" style="display:inline-flex;"></span>
              <span>{{ patrolState.running && patrolState.mode === 'hot' ? '正在监控中...' : `立即监控这 ${routes.length} 条航线` }}</span>
            </button>
          </div>
        </div>


        <!-- ==================== 选项卡 2：全网航网普查 (全量 397 条) ==================== -->
        <div v-show="activeTab === 'all'">
          <!-- 说明面板 -->
          <div style="padding:10px 14px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; margin-bottom:12px;">
            <div style="font-size:0.82rem; font-weight:700; color:#15803d; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
              <span v-html="ICONS.globe" style="display:inline-flex;"></span>
              <span>长龙航空全航网地毯式普查</span>
            </div>

            <div style="font-size:0.75rem; color:#166534; line-height:1.5;">
              自动遍历长龙航空全国所有直飞航线（共 397 条），拉取官方未来 61 天真实放票日历，全面更新大盘数据库，让所有目的地余票一目了然。
            </div>
          </div>

          <!-- 定时时间点配置 -->
          <div style="background:#ffffff; border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:10px 14px; margin-bottom:14px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
              <div style="font-size:0.82rem; font-weight:700; display:flex; align-items:center; gap:6px;">
                <span v-html="ICONS.clock" style="color:#059669;"></span>
                <span>全量普查定时时间点 (至多 3 个):</span>
                <span style="font-size:0.72rem; color:#059669;">已设 {{ patrolTimes.length }}/3 个</span>
              </div>
              <label style="display:inline-flex; align-items:center; gap:6px; cursor:pointer; font-size:0.75rem; font-weight:700; color:#334155;">
                <input 
                  type="checkbox" 
                  :checked="switches.all_enabled" 
                  @change="onSwitchChange('all_enabled', $event.target.checked)"
                  style="accent-color:#059669;"
                >
                <span>定时普查开关: {{ switches.all_enabled ? '已启用' : '已停用' }}</span>
              </label>
            </div>

            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <span 
                v-for="(t, idx) in patrolTimes" 
                :key="idx"
                style="display:inline-flex; align-items:center; gap:4px; background:#ecfdf5; border:1px solid #a7f3d0; color:#047857; font-weight:800; font-size:0.78rem; padding:2px 6px; border-radius:4px;"
              >
                <span>{{ t }}</span>
                <button 
                  type="button" 
                  @click="removeTime(idx)"
                  style="border:none; background:transparent; color:#059669; cursor:pointer;"
                >&times;</button>
              </span>

              <div v-if="patrolTimes.length < 3" style="display:inline-flex; align-items:center; gap:6px;">
                <input type="time" v-model="newTime" style="padding:2px 6px; font-size:0.78rem; border:1px solid #cbd5e1; border-radius:4px;">
                <button type="button" class="btn-glass" style="padding:3px 8px; font-size:0.75rem;" @click="addTime">+ 添加</button>
              </div>
            </div>
          </div>

          <!-- 立即执行全量普查 -->
          <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:6px; padding:10px 14px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
            <div>
              <div style="font-size:0.82rem; font-weight:700; color:#047857;">手动即时全网普查</div>
              <div style="font-size:0.72rem; color:#059669;">受控双并发遍历全国拓扑，逐条覆盖更新数据库</div>
            </div>
            <button 
              type="button" 
              class="btn-primary" 
              style="padding:6px 14px; font-size:0.78rem; background:linear-gradient(135deg, #059669, #047857); display:inline-flex; align-items:center; gap:5px;"
              :disabled="patrolState.running"
              @click="triggerManual('all')"
            >
              <span v-html="ICONS.rocket" style="display:inline-flex;"></span>
              <span>{{ patrolState.running && patrolState.mode === 'all' ? '正在全网普查中...' : '立即全网普查 (397条)' }}</span>
            </button>

          </div>
        </div>

        <!-- ==================== 底部通用实时监控进度条 (运行中自动展现) ==================== -->
        <div v-if="patrolState.running || patrolState.percent > 0" style="margin-top:14px; background:#f8fafc; border:1px solid #bbf7d0; border-radius:6px; padding:10px 12px;">
          <div style="display:flex; justify-content:space-between; font-size:0.78rem; margin-bottom:6px; font-weight:700; color:#047857;">
            <span>{{ patrolStatusTitle }}: {{ currentRouteDisplay }} ({{ patrolState.completed }}/{{ safeTotal }})</span>
            <span>{{ patrolState.percent }}%</span>
          </div>
          <div style="width:100%; height:8px; background:#e2e8f0; border-radius:4px; overflow:hidden;">
            <div 
              style="height:100%; background:linear-gradient(90deg, #10b981, #059669); transition:width 0.3s ease;"
              :style="{ width: `${patrolState.percent}%` }"
            ></div>
          </div>
        </div>

      </div>

      <!-- 模态框底部 -->
      <div class="modal-footer">
        <button type="button" class="btn-glass" style="font-size:0.78rem;" @click="resetDefault">恢复默认 30 条</button>
        <div style="display:flex; gap:8px;">
          <button type="button" class="btn-glass" style="font-size:0.78rem;" @click="$emit('close')">取消</button>
          <button type="button" class="btn-primary" style="font-size:0.78rem;" @click="saveAll">保存配置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { ICONS } from '../data/icons.js';
import { DIRECT_MAP } from '../data/routes-network.js';
import { 
  fetchPatrolHotRoutes,
  savePatrolHotRoutes,
  fetchPatrolTimes, 
  savePatrolTimes, 
  fetchPatrolSwitches, 
  savePatrolSwitches, 
  triggerPatrol 
} from '../api/patrol.js';

const props = defineProps({
  visible: Boolean,
  patrolState: {
    type: Object,
    default: () => ({ running: false, mode: 'idle', completed: 0, total: 0, percent: 0, current_route: '' })
  }
});

const emit = defineEmits(['close', 'saved', 'triggered']);

const activeTab = ref('hot');
const routes = ref([]);
const patrolTimes = ref(['08:30', '20:00']);
const switches = ref({ hot_enabled: false, all_enabled: false });

const newFrom = ref('杭州');
const newTo = ref('阿勒泰');
const newTime = ref('12:00');

const availableOrigins = computed(() => Object.keys(DIRECT_MAP).filter(c => (DIRECT_MAP[c] || []).length > 0));
const availableDestsForNew = computed(() => DIRECT_MAP[newFrom.value] || []);

const safeTotal = computed(() => {
  if (props.patrolState.total > 0) return props.patrolState.total;
  return props.patrolState.mode === 'all' ? 397 : (routes.value.length || 30);
});

const patrolStatusTitle = computed(() => {
  return props.patrolState.mode === 'all' ? '全网普查中' : '重点监控中';
});

const currentRouteDisplay = computed(() => {
  const cr = props.patrolState.current_route;
  if (!cr) return '准备中...';
  if (Array.isArray(cr) && cr.length >= 2) {
    return `${cr[0]} ➔ ${cr[1]}`;
  }
  return String(cr);
});

watch(newFrom, (val) => {
  const dests = DIRECT_MAP[val] || [];
  if (!dests.includes(newTo.value)) {
    newTo.value = dests[0] || '';
  }
});

async function loadData() {
  try {
    const [hotRes, timesRes, swRes] = await Promise.all([
      fetchPatrolHotRoutes(),
      fetchPatrolTimes(),
      fetchPatrolSwitches()
    ]);
    if (hotRes?.routes && Array.isArray(hotRes.routes)) {
      routes.value = hotRes.routes.map(item => Array.isArray(item) ? item : [item.from || '', item.to || '']);
    }
    if (timesRes?.times && Array.isArray(timesRes.times)) patrolTimes.value = timesRes.times;
    if (swRes?.switches) switches.value = swRes.switches;
  } catch (e) {
    console.warn('加载巡检配置失败:', e);
  }
}

watch(() => props.visible, (val) => {
  if (val) loadData();
});

function removeRoute(idx) {
  routes.value.splice(idx, 1);
}

function addRoute() {
  if (routes.value.length >= 30) return;
  if (!newFrom.value || !newTo.value) return;
  const exists = routes.value.some(r => r[0] === newFrom.value && r[1] === newTo.value);
  if (exists) return;
  routes.value.push([newFrom.value, newTo.value]);
}

function removeTime(idx) {
  patrolTimes.value.splice(idx, 1);
}

function addTime() {
  if (patrolTimes.value.length >= 3) return;
  if (!newTime.value || patrolTimes.value.includes(newTime.value)) return;
  patrolTimes.value.push(newTime.value);
  patrolTimes.value.sort();
}

async function onSwitchChange(key, checked) {
  switches.value[key] = checked;
  try {
    await savePatrolSwitches(switches.value.hot_enabled, switches.value.all_enabled);
  } catch (e) {
    console.warn('更新开关失败:', e);
  }
}

async function triggerManual(mode) {
  try {
    await triggerPatrol(mode);
    emit('triggered');
  } catch (e) {
    alert(e.message || '触发失败');
  }
}

function resetDefault() {
  routes.value = [
    ["杭州", "阿勒泰"], ["杭州", "喀什"], ["杭州", "克拉玛依"], ["杭州", "西双版纳"],
    ["杭州", "丽江"], ["杭州", "三亚"], ["杭州", "海口"], ["杭州", "哈尔滨"],
    ["杭州", "长春"], ["杭州", "成都"], ["杭州", "重庆"], ["杭州", "广州"],
    ["杭州", "深圳"], ["杭州", "珠海"], ["杭州", "贵阳"], ["杭州", "昆明"],
    ["杭州", "乌鲁木齐"], ["杭州", "西宁"], ["杭州", "银川"], ["杭州", "大连"],
    ["杭州", "沈阳"], ["杭州", "海拉尔"], ["银川", "杭州"], ["银川", "乌鲁木齐"],
    ["银川", "喀什"], ["银川", "三亚"], ["银川", "广州"], ["长春", "杭州"],
    ["长春", "三亚"], ["长春", "成都"]
  ];
}

async function saveAll() {
  try {
    await Promise.all([
      savePatrolHotRoutes(routes.value),
      savePatrolTimes(patrolTimes.value)
    ]);
    emit('saved', routes.value.length);
    emit('close');
  } catch (e) {
    alert('保存失败，请检查服务状态');
  }
}

onMounted(() => {
  if (props.visible) loadData();
});
</script>
