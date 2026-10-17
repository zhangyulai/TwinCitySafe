<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import LeakSummary from '../../components/LeakSummary.vue';
import EmergencyBrief from '../../components/EmergencyBrief.vue';
import DigitalTwinScene from '../../components/digital-twin/DigitalTwinScene.vue';
import SimulationControls from '../../components/SimulationControls.vue';
import RealtimeWaterChart from '../../components/RealtimeWaterChart.vue';
import { useServiceStore } from '../../store/useServiceStore';
import { useRealtimeStore } from '../../store/useRealtimeStore';
import { useRiskPrediction } from '../../composables/useRiskPrediction';
import { reviewApi } from '../../api/review';
import { incidentStatusLabels, incidentTypeLabels, type Incident } from '../../types/review';
import { deviceStatusLabels, weatherLabels } from '../../types/realtime';
import { floodLevelLabels } from '../../types/flood';
import { devControlsEnabled } from '../../config/presentation';
import { parkContext } from '../../config/park';
import type { BuildingMetadata } from '../../three/types/scene';
import './realtime-dashboard.css';
const selectedBuilding = shallowRef<BuildingMetadata | null>(null);
const service = useServiceStore(), realtime = useRealtimeStore();
const flood = computed(() => realtime.state?.flood?.scenarioId ? realtime.state.flood : null);
const leak = computed(() => realtime.state?.leak?.scenarioId ? realtime.state.leak : null);
const { prediction: riskPrediction } = useRiskPrediction(computed(() => !!flood.value));
const p03 = computed(() => realtime.getDeviceById('P03'));
const online = computed(() => realtime.devices.filter(d => d.status !== 'offline').length);
const abnormal = computed(() => realtime.devices.filter(d => d.status === 'warning' || d.status === 'offline' || d.fault !== 'normal' || d.analysis?.isAnomaly).length);
const pipeAttention = computed(() => realtime.pipelines.filter(p => p.status !== 'normal').length);
const alerts = computed(() => {
  const records = realtime.devices.filter(d => d.analysis?.activeAlarmId).map(d => ({ id: d.analysis!.activeAlarmId!, title: `${d.id} · ${d.name}`, note: d.analysis!.advice.title, route: `/operation?device=${d.id}` }));
  if (flood.value?.alarm) records.push({ id: flood.value.alarm.id, title: `${parkContext.floodZone}内涝`, note: flood.value.alarm.message, route: '/simulation' });
  if (leak.value?.alarm?.status === 'active') records.push({ id: leak.value.alarm.id, title: '给水管网异常', note: '查看压力、定位排名与影响范围', route: '/pipeline' });
  return records.filter((item, i) => records.findIndex(other => other.id === item.id) === i);
});
const operationState = computed(() => !realtime.state ? 'loading' : flood.value || leak.value ? 'incident' : abnormal.value || pipeAttention.value || alerts.value.length ? 'warning' : 'normal');
const operationLabels = { loading: '等待连接', normal: '运行平稳', warning: '需要关注', incident: '事故演化中' };
const currentRisk = computed(() => flood.value?.riskScore ?? leak.value?.riskScore ?? null);
const riskLevel = computed(() => flood.value?.riskLevel ?? leak.value?.riskLevel ?? 'low');
const lastTime = computed(() => realtime.lastUpdated ? new Date(realtime.lastUpdated).toLocaleTimeString('zh-CN', { hour12: false }) : '—');
const format = (value: number | null | undefined, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
const incidents = shallowRef<Incident[]>([]), archiveError = ref(''), archiveLoading = ref(true), archiveTotal = ref<number | null>(null);
let archiveRequest: AbortController | undefined, alive = true;
async function loadArchives() {
  archiveRequest?.abort(); const request = new AbortController(); archiveRequest = request; archiveLoading.value = true;
  try { const data = await reviewApi.list({ limit: 3 }, request.signal); if (alive && !request.signal.aborted) { incidents.value = data.items; archiveTotal.value = data.total; archiveError.value = ''; } }
  catch { if (alive && !request.signal.aborted) archiveError.value = '历史档案暂不可用，实时监测仍可查看。'; }
  finally { if (alive && !request.signal.aborted) archiveLoading.value = false; }
}
function startDemo(scenario: 'flood' | 'leak') { window.dispatchEvent(new CustomEvent('twincity-demo-start', { detail: { scenario } })); }
watch(() => `${flood.value?.scenarioId ?? ''}:${leak.value?.scenarioId ?? ''}`, () => void loadArchives());
onMounted(() => { void service.checkHealth(); void loadArchives(); });
onBeforeUnmount(() => { alive = false; archiveRequest?.abort(); });
</script>
<template>
  <div class="section-heading realtime-heading dashboard-heading">
    <div><span class="eyebrow">PARK SAFETY OVERVIEW <b class="dashboard-data-code">DT-OPS / LIVE GRID</b></span><h2>园区安全态势</h2><p>构建监测—预测—推演—处置—复盘一体化园区安全闭环</p></div>
    <div class="realtime-heading-actions"><span class="realtime-badge" :class="realtime.connectionStatus" data-testid="realtime-badge" :data-status="realtime.connectionStatus" :title="realtime.lastError"><i></i>{{ realtime.connectionStatus === 'connected' ? '实时仿真数据' : realtime.connectionStatus === 'connecting' ? '正在连接仿真数据' : '数据连接断开' }}</span><SimulationControls v-if="devControlsEnabled" /></div>
  </div>
  <EmergencyBrief/><LeakSummary/>
  <section class="overview-metrics" aria-label="园区关键指标">
    <RouterLink to="/operation" class="overview-metric"><span><i class="metric-index">01</i>设备在线 <b>设备监测 ↗</b></span><strong>{{ realtime.state ? online : '—' }}<small>/ {{ realtime.state ? realtime.devices.length : '—' }} 台</small></strong><p><i></i>{{realtime.state ? `${abnormal} 台设备需要关注` : '等待实时数据'}}</p></RouterLink>
    <RouterLink to="/pipeline" class="overview-metric"><span><i class="metric-index">02</i>管网资产 <b>地下空间 ↗</b></span><strong>{{realtime.state ? realtime.pipelines.length : '—'}}<small>条管段</small></strong><p>{{realtime.state ? `${pipeAttention} 条异常或隔离管段` : '等待实时数据'}}</p></RouterLink>
    <RouterLink :to="leak?'/pipeline?mode=leak':'/simulation'" class="overview-metric"><span><i class="metric-index">03</i>当前场景风险 <b>规则模型</b></span><strong :class="`risk-tone-${riskLevel}`">{{format(currentRisk)}}<small v-if="currentRisk!==null">/ 100</small></strong><p>{{flood?'暴雨内涝':leak?'管网泄漏':'当前无活动事故'}}</p></RouterLink>
    <RouterLink to="/review" class="overview-metric"><span><i class="metric-index">04</i>事件档案 <b>查看复盘 ↗</b></span><strong>{{archiveTotal ?? '—'}}<small>个事件</small></strong><p>{{archiveError?'档案暂不可用':'事故过程与处置记录可追溯'}}</p></RouterLink>
  </section>
  <div class="dashboard-grid realtime-dashboard final-dashboard" data-testid="dashboard-page">
    <aside class="side-column">
      <section class="panel park-operation" :class="operationState" data-testid="park-operation-state">
        <div class="panel-title"><h3>园区运行状态</h3><span class="source-label">软件仿真</span></div>
        <div class="park-state"><i></i><strong>{{ operationLabels[operationState] }}</strong></div>
        <p class="muted">{{ operationState === 'incident' ? '事故状态与实时设备、环境联动' : operationState === 'warning' ? '存在异常、离线或隔离资产，等待人工复核' : operationState === 'loading' ? '正在接入设备、管网与环境数据' : '设备、管网与环境持续监测中' }}</p>
        <div class="dashboard-counts"><div><strong>{{ realtime.state ? online : '—' }}<small>/ {{ realtime.state ? realtime.devices.length : '—' }}</small></strong><span>设备在线</span></div><div><strong :class="{'amber-text':abnormal>0}">{{ realtime.state ? abnormal : '—' }}</strong><span>异常 / 离线设备</span></div></div>
        <div class="live-summary-row"><span>管网状态</span><RouterLink to="/pipeline">{{ realtime.state ? `${realtime.pipelines.length} 条 · ${pipeAttention ? pipeAttention + ' 条需关注' : '运行正常'}` : '等待数据' }} →</RouterLink></div>
      </section>
      <section class="panel p03-panel" data-testid="p03-card" :data-status="p03?.status" :class="p03 ? `status-${p03.status}` : ''">
        <div class="panel-title"><h3>P03 排水泵</h3><RouterLink to="/operation?device=P03" class="panel-link">设备详情 →</RouterLink></div>
        <div class="device-status-line"><span class="device-status-chip"><i></i>{{ p03 ? deviceStatusLabels[p03.status] : '等待数据' }}</span><span>效率 <strong>{{ format(p03?.efficiency) }}%</strong></span></div>
        <div class="p03-readings"><div><strong>{{ format(p03?.temperature) }}<small>℃</small></strong><span>温度</span></div><div><strong>{{ format(p03?.vibration,2) }}<small>mm/s</small></strong><span>振动</span></div></div>
        <div class="p03-secondary"><span>电流 {{ format(p03?.current) }} A</span><span>健康 {{ format(p03?.health) }}</span></div>
        <RouterLink class="device-scene-link" to="/operation?device=P03">查看 P03 运维分析 →</RouterLink>
      </section>
      <section class="panel weather-panel"><div class="panel-title"><h3>气象与水位</h3><span>实时观测</span></div><div class="weather-current"><strong>{{ format(realtime.weather?.temperature) }}<small>℃</small></strong><span>{{ realtime.weather ? weatherLabels[realtime.weather.condition] : '等待数据' }}</span></div><div class="realtime-values"><div><span>降雨强度</span><strong data-testid="rainfall" :data-value="realtime.weather?.rainfall">{{ format(realtime.weather?.rainfall) }} <small>mm/h</small></strong></div><div><span>B2 仿真区 {{ flood ? '事故水位' : '基础水位' }}</span><strong data-testid="water-level" :data-value="realtime.environment?.b2WaterLevel">{{ format(realtime.environment?.b2WaterLevel,2) }} <small>cm</small></strong></div><div><span>相对湿度 / 风速</span><strong>{{ format(realtime.weather?.humidity,0) }}% / {{ format(realtime.weather?.windSpeed) }} <small>m/s</small></strong></div></div><p class="muted">{{ flood ? '水位由简化水量平衡模型计算' : '日常进水与排水平衡 · 持续采样' }}</p></section>
    </aside>
    <DigitalTwinScene :realtime-state="realtime.state" @building-select="selectedBuilding = $event"/>
    <aside class="side-column dashboard-right">
      <section class="panel current-incident"><div class="panel-title"><h3>当前事故</h3><span class="source-label">{{ flood || leak ? '规则风险' : '实时状态' }}</span></div>
        <div v-if="flood" class="dashboard-flood" data-testid="dashboard-flood"><span>{{ parkContext.floodZone }}内涝风险</span><strong :class="`risk-tone-${riskLevel}`">{{ format(currentRisk) }}<small> / 100</small></strong><span>{{ floodLevelLabels[flood.riskLevel] }} · 内涝场景风险 · 规则模型</span><RouterLink to="/simulation">查看暴雨内涝推演 →</RouterLink></div>
        <div v-else-if="leak" class="dashboard-leak"><span>地下给水管网泄漏</span><strong :class="`risk-tone-${riskLevel}`">{{ format(currentRisk) }}<small> / 100</small></strong><p>异常匹配度 {{ format(leak.detectionScore,3) }}</p><RouterLink to="/pipeline">查看定位与隔离 →</RouterLink></div>
        <div v-else class="dashboard-calm"><span class="calm-mark">✓</span><strong>当前无活动事故</strong><p>环境与设备持续监测，历史事件可随时复盘。</p></div>
        <div v-if="flood" class="dashboard-risk-prediction" data-testid="dashboard-risk-prediction"><span>未来30分钟风险 · 机器学习预测</span><b>{{ riskPrediction?.mlForecast.at(-1)?.riskScore.toFixed(1) ?? '—' }}</b><small v-if="riskPrediction&&!riskPrediction.modelStatus.available">模型暂不可用，物理预测保留</small><RouterLink to="/risk">查看综合风险研判 →</RouterLink></div>
        <p v-else class="dashboard-prediction-note">{{ leak ? '内涝预测模型不适用于管网泄漏' : '启动内涝场景后查看未来风险' }}</p>
      </section>
      <section class="panel dashboard-alerts"><div class="panel-title"><h3>当前告警</h3><span>{{ realtime.state ? alerts.length : '—' }} 条</span></div><ul v-if="alerts.length"><li v-for="alert in alerts.slice(0,3)" :key="alert.id"><RouterLink :to="alert.route"><strong>{{ alert.title }}</strong><p>{{ alert.note }}</p></RouterLink></li></ul><div v-else class="dashboard-empty"><i></i><p>{{ realtime.state ? '暂无活动告警' : '正在读取告警状态' }}</p><small>{{ realtime.state ? '设备与事故规则持续监测中' : '连接恢复后自动更新' }}</small></div></section>
      <section class="panel water-history-panel"><div class="panel-title"><h3>B2 水位趋势</h3><span>已发生的观测</span></div><RealtimeWaterChart :samples="realtime.history"/><p class="live-updated" data-testid="realtime-updated" :data-timestamp="realtime.lastUpdated" :data-revision="realtime.state?.revision">{{ realtime.state?.running ? '持续监测' : '仿真已暂停' }} · 最后更新 {{ lastTime }}</p><p v-if="realtime.connectionStatus!=='connected'&&realtime.state" class="realtime-stale">保留上次状态 · 正在尝试恢复连接</p></section>
    </aside>
  </div>
  <span class="twin-announcement" role="status">{{ selectedBuilding ? `已选中${selectedBuilding.name}` : '未选中建筑' }}</span>
  <section class="dashboard-bottom"><div class="panel dashboard-quick"><div><span class="eyebrow">EXPLORE THE COMPLETE SAFETY LOOP</span><h3>从实时监测，到全过程复盘</h3><p>演化由模型驱动，处置由你决定。</p></div><div class="dashboard-quick-actions"><button type="button" data-testid="dashboard-demo-flood" @click="startDemo('flood')"><span>01</span><strong>暴雨内涝演示</strong><small>预测 · 比较 · 人工处置 →</small></button><button type="button" data-testid="dashboard-demo-leak" @click="startDemo('leak')"><span>02</span><strong>管网泄漏演示</strong><small>检测 · 定位 · 阀门隔离 →</small></button><RouterLink to="/review"><span>03</span><strong>事件复盘</strong><small>历史回放 · 工单 · 报告 →</small></RouterLink></div></div><div class="panel dashboard-archives"><div class="panel-title"><h3>最近事件档案</h3><RouterLink class="panel-link" to="/review">{{ archiveTotal === null ? '查看档案' : `${archiveTotal} 条档案` }} →</RouterLink></div><p v-if="archiveError" class="muted" role="status">{{ archiveError }} <button type="button" class="inline-retry" @click="loadArchives">重试</button></p><p v-else-if="!incidents.length" class="dashboard-empty">{{ archiveLoading ? '正在读取已保存事件…' : '暂无历史事件，可启动场景建立事故档案。' }}</p><RouterLink v-for="incident in incidents" :key="incident.id" class="dashboard-archive-row" :to="`/review?incident=${incident.id}`"><span>{{ incidentTypeLabels[incident.incident_type] }}<small>{{ incident.started_at ? new Date(incident.started_at).toLocaleString('zh-CN',{hour12:false}) : '时间未记录' }}</small></span><b :class="incident.status.toLowerCase()">{{ incidentStatusLabels[incident.status] }}</b></RouterLink></div></section>
</template>
