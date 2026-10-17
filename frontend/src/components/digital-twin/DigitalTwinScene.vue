<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from "vue";
import type {LeakPreview} from "../../types/leak";
import { DigitalTwin } from "../../three";
import type { BuildingMetadata, SceneMode, SceneStats } from "../../three";
import { riskLabels } from "../../three/types/scene";
import type { BuildingSelection } from "../../three/types/scene";
import { pipelineLabels, type ParkRealtimeState } from "../../types/realtime";
import "./digital-twin.css";
import { useQualityStore } from "../../store/useQualityStore";
import type { SceneQuality } from "../../three/types/quality";
import { debugEnabled } from "../../config/presentation";
import AmapBasemap from "./AmapBasemap.vue";
import type { CampusEquipment } from "../../three/device/CampusEquipmentManager";
const qualityStore = useQualityStore();
const fullscreen = ref(!!document.fullscreenElement);
const showDebug = computed(() => debugEnabled && !fullscreen.value);
const slowSamples = ref(0);
const showPerformanceHint = computed(() => slowSamples.value >= 5 && qualityStore.quality !== 'low');
function updateFullscreen() { fullscreen.value = !!document.fullscreenElement; }
function changeQuality(event: Event) { qualityStore.setQuality((event.target as HTMLSelectElement).value as SceneQuality); }


import {statusLabels as pipelineStatusLabels} from "../../types/pipeline";
import {pipelineApi} from "../../api/pipelines";
import type {PipelineNetwork,PipelineType} from "../../types/pipeline";
const props = defineProps<{
  realtimeState?: ParkRealtimeState | null;
  dataMode?:'live'|'replay';
  replayState?:Record<string,unknown>|null;
  replayType?:string;
  replayIncidentId?:string|null;
  replayTime?:number;
  replayPlaying?:boolean;
  replayFocusId?:string;

  focusDeviceId?: string;
  pipelineNetwork?: PipelineNetwork;
  focusPipelineId?: string;
  focusNodeId?: string;
  pipelineTypes?: PipelineType[];
  traceEdges?: string[];
  affectedTrace?: boolean;
  initialUnderground?: boolean;
  floodGuidance?: boolean;
  emergencyPreview?: string[];
  leakPreview?: LeakPreview;
  initialMode?: SceneMode;
}>();

const emit = defineEmits<{
  "building-select": [metadata: BuildingSelection | null];
  "device-select": [id: string];
  "pipeline-select": [id:string];
  "valve-select": [id:string];
}>();
const host = ref<HTMLDivElement>();
const selected = shallowRef<BuildingMetadata | null>(null);
const selectedPipelineId = ref<string | null>(null);
const selectedDeviceId = ref<string | null>(null);
const selectedEquipment = shallowRef<CampusEquipment | null>(null);
const selectedDevice = computed(() =>
  props.realtimeState?.devices.find((d) => d.id === selectedDeviceId.value),
);
const selectedPipeline = computed(
  () =>
    props.realtimeState?.pipelines.find(
      (pipeline) => pipeline.id === selectedPipelineId.value,
    ) ?? null,
);
const mode = ref<SceneMode>("above");
const amapConfigured = Boolean(String(import.meta.env.VITE_AMAP_KEY ?? "").trim() && String(import.meta.env.VITE_AMAP_SECURITY_JS_CODE ?? "").trim());
const showRealGis = ref(false);
const cruising = ref(false);
const emergencyRoutePlaying = ref(false);
const emergencyRouteSpeed = ref(1);
const error = ref("");
const ready = ref(false);
const stats = ref<SceneStats>({ fps: 0, drawCalls: 0, triangles: 0 });
const basemapSource = ref<"local" | "online">("local");
const gisContextEnabled = import.meta.env.VITE_ENABLE_GIS_CONTEXT === "true";
const modes: { id: SceneMode; label: string }[] = [
  { id: "above", label: "地上" },
  { id: "risk", label: "风险" },
  { id: "underground", label: "管网" },
  { id: "emergency", label: "应急" },
];
const modeDescription = computed(() =>
  props.dataMode==='replay' ? '历史回放 · 与实时引擎隔离' : showRealGis.value ? '二维真实 GIS · 漕河泾园区周边' : mode.value === "underground"
    ? '地下管网 · 给排水与消防设施'
    : mode.value === "risk"
      ? (props.realtimeState?.flood?.scenarioId ? "风险分级 · 场景规则与基础示例" : "风险分级 · 示例数据")
      : mode.value === "emergency"
        ? '应急指挥 · 事故位置、救援路线与人员疏散路径'
      : gisContextEnabled ? '公开 GIS 空间底座 · 仿真资产叠加' : '参数化园区 · 仿真资产叠加',
);
const sceneCaptionDescription = computed(() => {
  if (props.dataMode === "replay") return "历史回放 · 数据库记录（灰色表示未记录）";
  if (showRealGis.value) return "真实道路、地名与建筑轮廓 · 资产标记为软件仿真映射";
  if (mode.value === "risk") {
    return props.realtimeState?.flood?.scenarioId
      ? "B2 为场景规则风险 · 其余建筑为示例"
      : "风险分级 · 建筑基础风险为示例";
  }
  if (mode.value === "emergency") return "应急指挥图层 · 路线为软件仿真演示，不用于真实疏散决策";
  return gisContextEnabled
    ? `${basemapSource.value === "online" ? "在线 OSM GIS 底图" : "本地公开 GIS 底图"} · 三维建筑与仿真资产叠加`
    : "参数化园区建筑、道路与景观 · 实时仿真资产叠加";
});
let twin: DigitalTwin | undefined;
watch(() => qualityStore.quality, value => { twin?.setQuality(value); slowSamples.value = 0; });
function applyReplay(){if(props.dataMode!=='replay'||!twin)return;twin.setReplayContext(props.replayIncidentId??null,props.replayType??'',props.replayTime??0,!!props.replayPlaying);twin.applyReplayState(props.replayState??null);twin.cueReplayCamera(props.replayFocusId);}
watch(()=>[props.replayState,props.replayTime,props.replayPlaying,props.replayType,props.replayIncidentId,props.replayFocusId],applyReplay);

watch(()=>props.leakPreview,value=>twin?.previewLeak(value));
watch(()=>props.emergencyPreview,value=>twin?.previewEmergency(value??[]));
let assetRequest:AbortController|undefined;
const assetError=ref('');
async function loadNetwork(){
 const current=twin;assetRequest?.abort();assetRequest=new AbortController();
 try{const data=props.pipelineNetwork??await pipelineApi.network(assetRequest.signal);if(twin!==current)return;twin?.loadPipelines(data);applyPipelineView();assetError.value='';}
 catch {if(!assetRequest.signal.aborted)assetError.value='管网资产加载失败，请检查迁移与 Seed';}
}
function applyPipelineView(){
 if(props.initialUnderground)twin?.setMode('underground');
 if(props.pipelineTypes)twin?.filterPipelines(props.pipelineTypes);
 if(props.focusPipelineId){twin?.selectPipeline(props.focusPipelineId);selectedPipelineId.value=props.focusPipelineId;}
 if(props.traceEdges)twin?.tracePipelines(props.traceEdges,props.affectedTrace);
}
function setSceneMode(nextMode: SceneMode): void {
  showRealGis.value = false;
  twin?.setMode(nextMode);
}
function toggleRealGis(): void {
  if (!showRealGis.value) twin?.setMode("above");
  showRealGis.value = !showRealGis.value;
}
function startEmergencyRoute(): void { twin?.startEmergencyRouteDemo(emergencyRouteSpeed.value); emergencyRoutePlaying.value = true; }
function pauseEmergencyRoute(): void { twin?.pauseEmergencyRouteDemo(); emergencyRoutePlaying.value = false; }
function resetEmergencyRoute(): void { twin?.resetEmergencyRouteDemo(); emergencyRoutePlaying.value = false; }

function mountScene(): void {
  twin?.dispose();
  twin = undefined;
  ready.value = false;
  error.value = "";
  selected.value = null;
  selectedPipelineId.value = null;
  emit("building-select", null);
  cruising.value = false;
  if (!host.value) return;
  try {
    twin = new DigitalTwin(host.value, {
      deviceSelect: (id) => {
        selectedDeviceId.value = id;
        if (id) emit("device-select", id);
      },
      equipmentSelect: (equipment) => { selectedEquipment.value = equipment; selected.value = null; selectedDeviceId.value = null; },
      select: (metadata) => {
        selectedEquipment.value = null;
        selected.value = metadata;
        emit(
          "building-select",
          metadata
            ? {
                ...metadata,
                buildingId: metadata.id,
                buildingName: metadata.name,
                buildingType: metadata.type,
              }
            : null,
        );
      },
      valveSelect:(id)=>emit("valve-select",id),
      pipelineSelect: (id) => {
        selectedPipelineId.value = id;
        if(id)emit("pipeline-select",id);
      },
      mode: (value) => {
        mode.value = value;
        if (value !== "above") showRealGis.value = false;
      },
      cruise: (value) => {
        cruising.value = value;
      },
      stats: (value) => {
        stats.value = value;
        slowSamples.value = value.fps > 0 && value.fps < 30 ? slowSamples.value + 1 : 0;
      },
      basemapSource: (source) => { basemapSource.value = source; },
      error: (message) => {
        error.value = message;
        ready.value = false;
      },
    });
    twin.setQuality(qualityStore.quality);
    if(props.dataMode==='replay')applyReplay();else if (props.realtimeState) twin.applyRealtimeState(props.realtimeState);
    twin.start();
    if(props.emergencyPreview)twin.previewEmergency(props.emergencyPreview);
    if(props.leakPreview)twin.previewLeak(props.leakPreview);
    if(props.initialMode){if(props.initialMode==='risk'&&props.realtimeState?.flood?.scenarioId)twin.focusFlood('risk');else twin.setMode(props.initialMode);}
    if(props.floodGuidance&&props.realtimeState?.flood?.scenarioId)twin.focusFlood();
    void loadNetwork();
    if (props.focusDeviceId) {
      twin.focusDevice(props.focusDeviceId);
      selectedDeviceId.value = props.focusDeviceId;
    }
    ready.value = true;
  } catch (cause) {
    console.error("Web3D initialization failed:", cause);
    error.value =
      "三维场景暂时无法启动，请确认浏览器支持 WebGL 2 并开启图形加速。";
  }
}
watch(
  () => props.realtimeState,
  (state) => {
    if (state && props.dataMode!=='replay') twin?.applyRealtimeState(state);
  },
);
watch(
  () => props.focusDeviceId,
  (id) => {
    if (id) {
      twin?.focusDevice(id);
      selectedDeviceId.value = id;
    }
  },
);
watch(()=>props.pipelineNetwork,()=>void loadNetwork());
watch(()=>props.focusPipelineId,id=>{if(id && id!==selectedPipelineId.value){twin?.selectPipeline(id);selectedPipelineId.value=id;}});
watch(()=>props.focusNodeId,id=>{if(id)twin?.focusPipelineNode(id);});
watch(()=>props.pipelineTypes,types=>{if(types)twin?.filterPipelines(types);},{deep:true});
watch(()=>[props.traceEdges,props.affectedTrace],()=>twin?.tracePipelines(props.traceEdges??[],props.affectedTrace),{deep:true});
watch(()=>props.realtimeState?.flood?.scenarioId,(id,old)=>{if(props.floodGuidance&&id&&id!==old)twin?.focusFlood();});
onMounted(() => { document.addEventListener("fullscreenchange", updateFullscreen); mountScene(); });
onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", updateFullscreen);
  assetRequest?.abort();
  twin?.dispose();
  twin = undefined;
});
</script>

<template>
  <section class="twin-panel panel" aria-label="智慧园区数字孪生">
    <header class="twin-toolbar">
      <div class="twin-title">
        <i></i
        ><span
          >数字孪生园区<small>{{ modeDescription }}</small></span
        >
      </div>
      <div class="twin-actions">
        <label class="twin-quality" title="调整视觉质量，不影响仿真或预测数据">
          <span>画质</span>
          <select :value="qualityStore.quality" @change="changeQuality" data-testid="scene-quality" aria-label="三维画质">
            <option value="high">精细</option><option value="medium">均衡</option><option value="low">性能</option>
          </select>
        </label>
        <div class="twin-mode-switch" role="group" aria-label="场景模式">
          <button
            v-for="item in (dataMode==='replay'?modes.filter(m=>m.id!=='risk'&&m.id!=='emergency'):modes)"
            :key="item.id"
            :aria-pressed="mode === item.id"
            :disabled="!ready"
            @click="setSceneMode(item.id)"
          >
            {{ item.label }}
          </button>
        </div>
        <button
          class="twin-control twin-gis-toggle"
          :class="{ active: showRealGis }"
          :aria-pressed="showRealGis"
          :title="amapConfigured ? '切换高德真实 GIS 底图' : '切换 OpenStreetMap 在线真实 GIS 底图'"
          @click="toggleRealGis"
        >二维 GIS</button>
        <div v-if="mode === 'emergency'" class="twin-emergency-controls" aria-label="应急路线演示控制">
          <button class="twin-control" @click="emergencyRoutePlaying ? pauseEmergencyRoute() : startEmergencyRoute()">{{ emergencyRoutePlaying ? '暂停路线' : '开始演示' }}</button>
          <label><span>速度</span><select v-model.number="emergencyRouteSpeed" @change="emergencyRoutePlaying && startEmergencyRoute()"><option :value=".5">0.5×</option><option :value="1">1×</option><option :value="2">2×</option><option :value="5">5×</option></select></label>
          <button class="twin-control" @click="resetEmergencyRoute">重置</button>
        </div>
        <button
          class="twin-control"
          :disabled="!ready"
          title="恢复园区全景"
          @click="twin?.resetCamera()"
        >
          恢复视角
        </button>
        <button
          class="twin-control"
          :class="{ active: cruising }"
          :aria-pressed="cruising"
          :disabled="!ready"
          @click="twin?.toggleCruise()"
        >
          {{ cruising ? "停止巡游" : "自动巡游" }}
        </button>
      </div>
    </header>
    <div class="twin-viewport">
      <AmapBasemap v-if="showRealGis" class="twin-real-gis" />
      <div ref="host" class="twin-webgl-host" :class="{ 'twin-webgl-host--hidden': showRealGis }"
      data-testid="twin-scene"
      :data-mode="mode" :data-source-mode="dataMode??'live'" :data-quality="qualityStore.quality"
      :data-selected="selected?.id ?? ''"
      :data-selected-pipeline="selectedPipelineId ?? ''"
      :data-selected-device="selectedDeviceId ?? ''"
      ></div>
    </div>
    <div v-if="assetError" class="pipeline-asset-error" role="alert">{{assetError}}</div>
    <div v-if="error" class="twin-error" role="alert">
      <strong>场景加载异常</strong>
      <p>{{ error }}</p>
      <button class="twin-control" @click="mountScene">重新加载场景</button>
    </div>
    <div v-else-if="!ready" class="twin-loading">正在构建智慧园区…</div>
    <div v-if="ready" class="twin-scene-caption">
      <span>示范园区 / 01</span
      ><strong>{{
        mode === "underground"
          ? "B2 · 地下管网"
          : mode === "risk"
            ? "建筑风险分级"
            : mode === "emergency"
              ? "应急指挥 · 路线推演"
          : showRealGis ? "地上 · 真实 GIS 底图" : "地上 · 园区全景"
      }}</strong
      ><small>{{ sceneCaptionDescription }}</small>
    </div>
    <div
      v-if="ready && mode === 'risk'"
      class="twin-legend"
      aria-label="风险图例"
    >
      <span class="low">低风险</span><span class="general">一般</span
      ><span class="elevated">较高</span><span class="high">高风险</span>
    </div>
    <div
      v-if="ready && mode === 'underground'"
      class="twin-legend"
      aria-label="管线图例"
    >
      <span class="water">给水</span><span class="drain">排水</span
      ><span class="fire">消防</span><span class="valve">阀门</span><span class="general">电力</span>
    </div>
    <div v-if="ready && mode === 'emergency'" class="twin-legend" aria-label="应急图例">
      <span class="high">事故位置</span><span class="general">救援路线</span><span class="low">疏散路径</span>
    </div>
    <aside
      v-if="selectedEquipment && !error"
      class="twin-detail"
      data-testid="equipment-scene-details"
      aria-label="设备点位详情"
    >
      <div class="twin-detail-top"><span>园区设备点位 · 软件仿真</span><button aria-label="关闭设备点位详情" @click="selectedEquipment = null">×</button></div>
      <h3>{{ selectedEquipment.name }}</h3>
      <dl>
        <div><dt>类型</dt><dd>{{ {camera:'摄像头', hydrant:'消防栓', sensor:'环境传感器'}[selectedEquipment.type] }}</dd></div>
        <div><dt>状态</dt><dd>{{ selectedEquipment.status }}</dd></div>
        <div><dt>实时数据</dt><dd>{{ selectedEquipment.realtime }}</dd></div>
      </dl>
    </aside>
    <aside
      v-if="selectedDevice && !focusDeviceId && !error"
      class="twin-detail"
      data-testid="device-scene-details"
    >
      <div class="twin-detail-top">
        <span>当前设备 · 实时仿真</span
        ><button aria-label="关闭设备详情" @click="selectedDeviceId = null">
          ×
        </button>
      </div>
      <h3>{{ selectedDevice.name }}</h3>
      <p>Health Index {{ selectedDevice.health.toFixed(1) }}</p>
      <p>{{ selectedDevice.analysis?.advice.title ?? "等待分析" }}</p>
      <RouterLink
        class="device-scene-link"
        :to="{ path: '/operation', query: { device: selectedDevice.id } }"
        >进入智慧运维 →</RouterLink
      >
    </aside>
    <aside
      v-if="dataMode!=='replay' && selected && !error && !(selected.id==='B2-PARKING' && realtimeState?.flood?.scenarioId)"
      class="twin-detail"
      data-testid="building-details"
      aria-label="建筑详情"
    >
      <div class="twin-detail-top">
        <span>当前选中对象 · 示例属性</span
        ><button
          aria-label="关闭详情"
          title="关闭详情"
          @click="twin?.clearSelection()"
        >
          ×
        </button>
      </div>
      <h3>{{ selected.name }}</h3>
      <p>
        {{ selected.typeLabel }}<span>{{ selected.id }}</span>
      </p>
      <dl>
        <div>
          <dt>建筑面积</dt>
          <dd>{{ selected.area.toLocaleString("zh-CN") }} <small>m²</small></dd>
        </div>
        <div>
          <dt>楼层</dt>
          <dd>
            {{
              selected.level < 0
                ? `地下 ${Math.abs(selected.level)} 层`
                : `${selected.floors} 层`
            }}
          </dd>
        </div>
        <div>
          <dt>设备数量</dt>
          <dd>{{ selected.deviceCount }}</dd>
        </div>
        <div>
          <dt>当前告警</dt>
          <dd>{{ selected.alarms }}</dd>
        </div>
        <div>
          <dt>安全指数</dt>
          <dd class="twin-detail-score">{{ selected.safetyIndex }}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{{ selected.status }}</dd>
        </div>
        <div>
          <dt>风险等级</dt>
          <dd>{{ riskLabels[selected.risk] }}</dd>
        </div>
      </dl>
      <div class="twin-detail-bottom">
        <span>{{ riskLabels[selected.risk] }} · 示例</span
        ><button class="twin-control" @click="twin?.focusSelected()">
          聚焦建筑
        </button>
      </div>
    </aside>
    <div
      v-if="ready && props.realtimeState && mode !== 'above'"
      class="twin-water-readout"
      data-testid="b2-water-level"
    >
      <span>B2 水位</span
      ><strong
        >{{ props.realtimeState.environment.b2WaterLevel.toFixed(2) }}
        <small>cm</small></strong
      >
      <small>{{realtimeState?.flood?.scenarioId?'内涝场景演化':'基础水位模拟'}}</small>
    </div>
    <aside
      v-if="selectedPipeline && !error && !pipelineNetwork"
      class="twin-detail twin-pipeline-detail"
      data-testid="pipeline-details"
      aria-label="管线详情"
    >
      <div class="twin-detail-top">
        <span>当前选中管线 · 实时仿真</span
        ><button
          aria-label="关闭管线详情"
          title="关闭管线详情"
          @click="twin?.clearSelection()"
        >
          ×
        </button>
      </div>
      <h3>{{ pipelineLabels[selectedPipeline.type] }}管线</h3>
      <p>{{ selectedPipeline.id }}<span>园区地下管网</span></p>
      <dl>
        <div>
          <dt>压力</dt>
          <dd data-testid="pipeline-pressure">
            {{ selectedPipeline.pressure.toFixed(3) }} <small>MPa</small>
          </dd>
        </div>
        <div>
          <dt>流量</dt>
          <dd data-testid="pipeline-flow">
            {{ selectedPipeline.flow.toFixed(2) }} <small>m³/h</small>
          </dd>
        </div>
        <div>
          <dt>运行状态</dt>
          <dd class="twin-detail-score">{{pipelineStatusLabels[selectedPipeline.status]}}</dd>
        </div>
      </dl>
      <div class="twin-detail-bottom"><span>每秒更新 · 非实测数据</span></div>
    </aside>
    <footer class="twin-statusbar">
      <button v-if="showPerformanceHint && !fullscreen" class="twin-performance-hint" @click="qualityStore.setQuality('low')">建议切换性能模式</button>
      <span
        >{{ showRealGis ? '拖动浏览 · 滚轮缩放 · 控制栏调整视角 · 标记为仿真资产映射' : '左键旋转 · 滚轮缩放 · 右键平移 · 点击' }}{{
          showRealGis ? '' : (mode === "underground" ? "建筑 / 管线" : "建筑")
        }}查看详情</span>
      <span v-if="gisContextEnabled && !showRealGis && mode === 'above'" class="twin-gis-status"><i></i>{{ basemapSource === 'online' ? '在线 OSM GIS 已叠加' : '本地 GIS 底座' }}</span>
      <span
        v-if="ready && showDebug"
        data-testid="scene-fps"
        :title="`${stats.drawCalls} draw calls / ${stats.triangles.toLocaleString()} triangles`"
        ><i></i>WebGL <b>{{ stats.fps || "—" }}</b> FPS</span
      >
    </footer>
  </section>
</template>
