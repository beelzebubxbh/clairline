<template>
  <transition name="rt-fade">
    <div v-if="visible" class="rt-overlay" @click.self="close">
      <div class="rt-panel">
        <header class="rt-head">
          <div class="rt-title">
            <span class="rt-icon">⇄</span>
            <div>
              <h2>往返搜索</h2>
              <p>选好去程和回程，一次筛出两边都有票的目的地</p>
            </div>
          </div>
          <button class="rt-close" @click="close" title="关闭">✕</button>
        </header>

        <section class="rt-form">
          <div class="rt-row">
            <label class="rt-field">
              <span>出发地</span>
              <select v-model="origin" @change="onOriginChange">
                <option v-for="c in origins" :key="c" :value="c">
                  {{ c }} · {{ counts[c] }} 条直飞
                </option>
              </select>
            </label>

            <label class="rt-field">
              <span>目的地</span>
              <select v-model="dest">
                <option value="">不限（搜索全部有票目的地）</option>
                <option v-for="c in destinations" :key="c" :value="c">{{ c }}</option>
              </select>
            </label>
          </div>

          <div class="rt-row rt-patterns">
            <span class="rt-label">行程节奏</span>
            <div class="rt-chips">
              <button
                v-for="p in patterns" :key="p.key"
                :class="['rt-chip', { active: pattern === p.key }]"
                @click="pattern = p.key"
              >{{ p.label }}</button>
              <button :class="['rt-chip', { active: pattern === 'custom' }]" @click="pattern = 'custom'">
                自定义
              </button>
            </div>
          </div>

          <div v-if="pattern !== 'custom'" class="rt-row">
            <span class="rt-label">查未来</span>
            <div class="rt-chips">
              <button
                v-for="w in [2, 4, 6, 8]" :key="w"
                :class="['rt-chip', { active: weeks === w }]"
                @click="weeks = w"
              >{{ w }} 个周末</button>
            </div>
            <span class="rt-hint">可预约窗口：{{ bookableFrom }} ~ {{ bookableTo }}</span>
          </div>

          <div v-else class="rt-row">
            <label class="rt-field rt-field-sm">
              <span>出发日期从</span>
              <input type="date" v-model="customStart" :min="bookableFrom" />
            </label>
            <label class="rt-field rt-field-sm">
              <span>到</span>
              <input type="date" v-model="customEnd" :min="bookableFrom" />
            </label>
            <label class="rt-field rt-field-sm">
              <span>停留天数</span>
              <input type="number" min="1" max="14" v-model.number="stayDays" />
            </label>
          </div>

          <div class="rt-row rt-times">
            <span class="rt-label">出发时段</span>
            <input type="time" v-model="outAfter" />
            <span class="rt-sep">至</span>
            <input type="time" v-model="outBefore" />
            <span class="rt-label rt-label-gap">回程时段</span>
            <input type="time" v-model="retAfter" />
            <span class="rt-sep">至</span>
            <input type="time" v-model="retBefore" />
            <button v-if="hasTimeFilter" class="rt-link" @click="clearTimes">清除</button>
          </div>

          <div class="rt-row rt-actions">
            <label class="rt-check">
              <input type="checkbox" v-model="withDetail" />
              同时查询具体航班与余票（较慢，仅 3~30 天内有效）
            </label>
            <button class="rt-search" :disabled="loading" @click="runSearch">
              {{ loading ? '搜索中…' : '搜索有票往返' }}
            </button>
          </div>

          <p class="rt-preview" v-if="pairs.length">
            将查询 {{ pairs.length }} 组日期：
            <template v-for="(p, i) in pairs.slice(0, 4)" :key="i">
              {{ p.out }}→{{ p.ret }}<template v-if="i < Math.min(pairs.length, 4) - 1">、</template>
            </template>
            <template v-if="pairs.length > 4"> 等</template>
          </p>
        </section>

        <section class="rt-results">
          <div v-if="error" class="rt-error">{{ error }}</div>

          <div v-else-if="loading" class="rt-empty">
            <div class="rt-spinner"></div>
            <p>正在比对往返航线的放票日历…</p>
          </div>

          <div v-else-if="!searched" class="rt-empty">
            <p>选好节奏后点「搜索有票往返」</p>
            <p class="rt-dim">示例：周六出发、周日回，就能看到哪些城市这个周末还能兑换</p>
          </div>

          <div v-else-if="!results.length" class="rt-empty">
            <p>这段时间没有往返两程都有票的目的地</p>
            <p class="rt-dim">可以试试放宽到更多周末，或者取消时段限制</p>
          </div>

          <template v-else>
            <div class="rt-summary">
              <strong>{{ origin }}</strong> 出发 · 命中 <strong>{{ data.count }}</strong> 个目的地
              <span v-if="data.totalCached > data.count">（共 {{ data.totalCached }} 个，已截断）</span>
              <span v-if="data.detail_note" class="rt-note">{{ data.detail_note }}</span>
            </div>

            <article v-for="r in results" :key="r.to" class="rt-card">
              <div class="rt-card-head">
                <div class="rt-dest">
                  <span class="rt-city">{{ r.to }}</span>
                  <span class="rt-iata">{{ r.toIata }}</span>
                  <span v-if="r.nights" class="rt-nights">{{ r.nights }} 晚</span>
                </div>
                <div v-if="r.totalPrice" class="rt-price">往返 ¥{{ r.totalPrice }}</div>
              </div>

              <div class="rt-legs">
                <div v-for="leg in ['out', 'ret']" :key="leg" class="rt-leg">
                  <div class="rt-leg-head">
                    <span :class="['rt-badge', leg]">{{ leg === 'out' ? '去程' : '回程' }}</span>
                    <span class="rt-date">{{ r[leg].date }}</span>
                  </div>

                  <div v-if="r[leg].flights && r[leg].flights.length" class="rt-flights">
                    <div v-for="(f, i) in r[leg].flights" :key="i" class="rt-flight">
                      <span class="rt-fno">{{ f.flightNo }}</span>
                      <span class="rt-time">{{ f.depTime }} → {{ f.arrTime }}</span>
                      <span class="rt-stop">{{ f.stopover || '直飞' }}</span>
                      <span class="rt-seat">余 {{ f.secCardLeft }} 张</span>
                    </div>
                  </div>
                  <div v-else class="rt-leg-note">
                    {{ r[leg].note || '日历显示有票（勾选"查询具体航班"可看时刻与余量）' }}
                  </div>
                </div>
              </div>
            </article>
          </template>
        </section>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { fetchRoundtripCities, searchRoundtrip } from '../api/roundtrip.js';

const props = defineProps({ visible: { type: Boolean, default: false } });
const emit = defineEmits(['close']);

const patterns = [
  { key: 'sat_sun', label: '周六去 · 周日回' },
  { key: 'fri_sun', label: '周五去 · 周日回' },
  { key: 'fri_mon', label: '周五去 · 周一回' }
];

const origins = ref([]);
const routes = ref({});
const counts = ref({});
const bookableFrom = ref('');
const bookableTo = ref('');

const origin = ref('');
const dest = ref('');
const pattern = ref('sat_sun');
const weeks = ref(4);
const customStart = ref('');
const customEnd = ref('');
const stayDays = ref(2);
const outAfter = ref('');
const outBefore = ref('');
const retAfter = ref('');
const retBefore = ref('');
const withDetail = ref(true);

const loading = ref(false);
const searched = ref(false);
const error = ref('');
const data = ref(null);
const results = computed(() => data.value?.results || []);
const destinations = computed(() => routes.value[origin.value] || []);
const hasTimeFilter = computed(() => !!(outAfter.value || outBefore.value || retAfter.value || retBefore.value));

function close() { emit('close'); }
function clearTimes() {
  outAfter.value = ''; outBefore.value = ''; retAfter.value = ''; retBefore.value = '';
}

function fmt(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function parse(s) {
  const [y, m, d] = (s || '').split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

// 根据节奏生成「去程→回程」日期组合
const pairs = computed(() => {
  const out = [];
  if (pattern.value === 'custom') {
    if (!customStart.value || !customEnd.value) return [];
    const s = parse(customStart.value), e = parse(customEnd.value);
    if (e < s) return [];
    const stay = Math.max(1, Number(stayDays.value) || 1);
    let d = new Date(s);
    while (d <= e && out.length < 40) {
      const r = new Date(d); r.setDate(r.getDate() + stay);
      out.push({ out: fmt(d), ret: fmt(r) });
      d.setDate(d.getDate() + 1);
    }
    return out;
  }

  const conf = { sat_sun: [6, 1], fri_sun: [5, 2], fri_mon: [5, 3] }[pattern.value];
  if (!conf) return [];
  const [outDow, offset] = conf;
  const base = bookableFrom.value ? parse(bookableFrom.value) : new Date();
  const d = new Date(base);
  const diff = (outDow - d.getDay() + 7) % 7;
  d.setDate(d.getDate() + diff);
  for (let i = 0; i < weeks.value; i++) {
    const o = new Date(d); o.setDate(o.getDate() + i * 7);
    const r = new Date(o); r.setDate(r.getDate() + offset);
    out.push({ out: fmt(o), ret: fmt(r) });
  }
  return out;
});

function onOriginChange() { dest.value = ''; }

async function loadCities() {
  if (origins.value.length) return;
  try {
    const d = await fetchRoundtripCities();
    if (!d.ok) throw new Error(d.error || '加载失败');
    origins.value = d.origins || [];
    routes.value = d.routes || {};
    counts.value = d.counts || {};
    bookableFrom.value = d.bookableFrom || '';
    bookableTo.value = d.bookableTo || '';
    if (!origin.value && origins.value.length) origin.value = origins.value[0];
  } catch (e) {
    error.value = '无法加载航线网络：' + e.message;
  }
}

async function runSearch() {
  if (!origin.value) { error.value = '请选择出发地'; return; }
  if (!pairs.value.length) { error.value = '请至少给出一组有效的去程/回程日期'; return; }
  loading.value = true;
  error.value = '';
  try {
    data.value = await searchRoundtrip({
      from: origin.value,
      to: dest.value,
      pairs: pairs.value,
      outAfter: outAfter.value,
      outBefore: outBefore.value,
      retAfter: retAfter.value,
      retBefore: retBefore.value,
      detail: withDetail.value,
      detailLimit: 8
    });
    searched.value = true;
  } catch (e) {
    if (e.authExpired) {
      window.dispatchEvent(new CustomEvent('clairline:auth-expired'));
      error.value = '登录态已失效，请点右上角「同步长龙登录」，用手机验证码重新登录一次';
    } else {
      error.value = e.message || '搜索失败';
    }
  } finally {
    loading.value = false;
  }
}

watch(() => props.visible, (v) => { if (v) loadCities(); });
onMounted(() => { if (props.visible) loadCities(); });
</script>

<style scoped>
.rt-overlay {
  position: fixed; inset: 0; z-index: 3000;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.rt-panel {
  width: min(980px, 100%); max-height: 88vh;
  background: var(--bg-surface); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg); display: flex; flex-direction: column;
  overflow: hidden;
}
.rt-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 18px 22px 14px; border-bottom: 1px solid var(--border-subtle);
}
.rt-title { display: flex; gap: 12px; align-items: center; }
.rt-icon {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--accent-emerald-light); color: var(--accent-emerald);
  display: grid; place-items: center; font-size: 19px; font-weight: 700;
}
.rt-title h2 { margin: 0; font-size: 1.05rem; color: var(--text-primary); }
.rt-title p { margin: 2px 0 0; font-size: 0.78rem; color: var(--text-muted); }
.rt-close {
  border: none; background: transparent; cursor: pointer;
  font-size: 1rem; color: var(--text-dim); padding: 4px 8px; border-radius: var(--radius-sm);
}
.rt-close:hover { background: #f1f5f9; color: var(--text-primary); }

.rt-form { padding: 16px 22px; border-bottom: 1px solid var(--border-subtle); }
.rt-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.rt-row:last-child { margin-bottom: 0; }
.rt-field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 200px; }
.rt-field > span { font-size: 0.72rem; color: var(--text-muted); font-weight: 600; }
.rt-field select, .rt-field input {
  padding: 8px 10px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
  font-size: 0.86rem; color: var(--text-primary); background: #fff; outline: none;
}
.rt-field select:focus, .rt-field input:focus { border-color: var(--border-focus); }
.rt-field-sm { flex: 0 1 170px; min-width: 130px; }
.rt-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; white-space: nowrap; }
.rt-label-gap { margin-left: 14px; }
.rt-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.rt-chip {
  border: 1px solid var(--border-subtle); background: #fff; cursor: pointer;
  padding: 6px 13px; border-radius: var(--radius-full);
  font-size: 0.79rem; color: var(--text-secondary); transition: all .15s;
}
.rt-chip:hover { border-color: var(--accent-emerald-border); }
.rt-chip.active {
  background: var(--accent-emerald-light); border-color: var(--accent-emerald-border);
  color: var(--accent-emerald); font-weight: 600;
}
.rt-hint { font-size: 0.72rem; color: var(--text-dim); }
.rt-times input[type="time"] {
  padding: 6px 8px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
  font-size: 0.8rem; color: var(--text-primary); background: #fff;
}
.rt-sep { font-size: 0.74rem; color: var(--text-dim); }
.rt-link { border: none; background: none; color: var(--accent-cyan); cursor: pointer; font-size: 0.76rem; }
.rt-actions { justify-content: space-between; margin-top: 4px; }
.rt-check { font-size: 0.78rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; cursor: pointer; }
.rt-search {
  border: none; cursor: pointer; padding: 10px 22px; border-radius: var(--radius-full);
  background: var(--accent-emerald); color: #fff; font-weight: 600; font-size: 0.86rem;
}
.rt-search:disabled { opacity: .6; cursor: default; }
.rt-preview { margin: 10px 0 0; font-size: 0.73rem; color: var(--text-dim); }

.rt-results { padding: 16px 22px 22px; overflow-y: auto; flex: 1; }
.rt-empty { text-align: center; padding: 46px 12px; color: var(--text-secondary); font-size: 0.86rem; }
.rt-empty .rt-dim { color: var(--text-dim); font-size: 0.78rem; margin-top: 6px; }
.rt-spinner {
  width: 24px; height: 24px; margin: 0 auto 12px; border-radius: 50%;
  border: 2px solid var(--border-subtle); border-top-color: var(--accent-emerald);
  animation: rt-spin .8s linear infinite;
}
@keyframes rt-spin { to { transform: rotate(360deg); } }
.rt-error {
  background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c;
  padding: 10px 14px; border-radius: var(--radius-md); font-size: 0.82rem;
}
.rt-summary {
  font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 12px;
  display: flex; gap: 8px; flex-wrap: wrap; align-items: baseline;
}
.rt-note { color: var(--text-dim); font-size: 0.74rem; }

.rt-card {
  border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
  padding: 12px 14px; margin-bottom: 10px; background: #fff;
}
.rt-card:hover { border-color: var(--accent-emerald-border); box-shadow: var(--shadow-sm); }
.rt-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rt-dest { display: flex; align-items: center; gap: 8px; }
.rt-city { font-weight: 700; color: var(--text-primary); font-size: 0.95rem; }
.rt-iata { font-size: 0.7rem; color: var(--text-dim); background: #f1f5f9; padding: 1px 6px; border-radius: 4px; }
.rt-nights { font-size: 0.72rem; color: var(--text-muted); }
.rt-price { font-size: 0.8rem; font-weight: 700; color: var(--accent-emerald); }

.rt-legs { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.rt-leg-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.rt-badge {
  font-size: 0.68rem; padding: 1px 7px; border-radius: 4px; font-weight: 600;
}
.rt-badge.out { background: #eff6ff; color: #1d4ed8; }
.rt-badge.ret { background: #f0fdf4; color: var(--accent-emerald); }
.rt-date { font-size: 0.76rem; color: var(--text-muted); }
.rt-flight {
  display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap;
  font-size: 0.76rem; padding: 3px 0; border-top: 1px dashed #f1f5f9;
}
.rt-fno { font-weight: 600; color: var(--text-primary); }
.rt-time { color: var(--text-secondary); }
.rt-stop, .rt-seat { color: var(--text-dim); }
.rt-seat { color: var(--accent-emerald); font-weight: 600; }
.rt-leg-note { font-size: 0.73rem; color: var(--text-dim); padding: 3px 0; }

@media (max-width: 720px) {
  .rt-overlay { padding: 0; }
  .rt-panel { max-height: 100vh; height: 100vh; border-radius: 0; }
  .rt-legs { grid-template-columns: 1fr; }
  .rt-field { min-width: 100%; }
}
.rt-fade-enter-active, .rt-fade-leave-active { transition: opacity .16s; }
.rt-fade-enter-from, .rt-fade-leave-to { opacity: 0; }
</style>