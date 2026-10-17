<script setup lang="ts">
import {devControlsEnabled} from "../../config/presentation";
import { computed, ref, shallowRef, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useRealtimeStore } from "../../store/useRealtimeStore";
import { deviceApi } from "../../api/devices";
import type { DeviceAsset, SamplingStatus } from "../../types/operation";
import DigitalTwinScene from "../../components/digital-twin/DigitalTwinScene.vue";
import SimulationControls from "../../components/SimulationControls.vue";
import DeviceList from "./components/DeviceList.vue";
import DeviceSummary from "./components/DeviceSummary.vue";
import DeviceRealtimeMetrics from "./components/DeviceRealtimeMetrics.vue";
import DeviceHealthCard from "./components/DeviceHealthCard.vue";
import DeviceAnomalyCard from "./components/DeviceAnomalyCard.vue";
import MaintenanceAdviceCard from "./components/MaintenanceAdviceCard.vue";
import DeviceTrendChart from "./components/DeviceTrendChart.vue";
import "../Dashboard/realtime-dashboard.css";
import "./operation.css";
const realtime = useRealtimeStore(),
  route = useRoute(),
  router = useRouter();
const selectedId = ref(
  typeof route.query.device === "string" &&
    ["P01", "P02", "P03"].includes(route.query.device)
    ? route.query.device
    : "P03",
);
const assets = shallowRef<DeviceAsset[]>([]),
  sampling = shallowRef<SamplingStatus | null>(null),
  loading = ref(false),
  error = ref("");
const selected = computed(() =>
  assets.value.find((a) => a.id === selectedId.value),
);
const live = computed(() => realtime.getDeviceById(selectedId.value));
const points = computed(() => realtime.deviceHistory[selectedId.value] ?? []);
const isDev = devControlsEnabled;
let request: AbortController | undefined,
  timer: ReturnType<typeof setInterval> | undefined,
  alive = true;
async function load() {
  request?.abort();
  request = new AbortController();
  loading.value = true;
  error.value = "";
  try {
    const data = await deviceApi.list(request.signal);
    if (alive) assets.value = data;
  } catch {
    if (alive)
      error.value = "设备资产暂不可用，请确认数据库迁移和初始数据已完成。";
  } finally {
    if (alive) loading.value = false;
  }
}
async function checkSampling() {
  try {
    const data = await deviceApi.sampling();
    if (alive) sampling.value = data;
  } catch {
    if (alive)
      sampling.value = {
        available: false,
        intervalSeconds: 5,
        lastSampleAt: null,
        message: "采样服务暂不可用",
      };
  }
}
function select(id: string) {
  selectedId.value = id;
  void router.replace({ query: { ...route.query, device: id } });
}
onMounted(() => {
  void load();
  void checkSampling();
  timer = setInterval(() => void checkSampling(), 10000);
});
onBeforeUnmount(() => {
  alive = false;
  request?.abort();
  clearInterval(timer);
});
</script>
<template>
  <div class="section-heading operation-heading">
    <div>
      <span class="eyebrow">SMART EQUIPMENT OPERATION</span>
      <h2>智慧运维中心</h2>
      <p>软件仿真数据 · 异常检测基于仿真工况训练</p>
    </div>
    <div class="realtime-heading-actions">
      <span class="realtime-badge" :class="realtime.connectionStatus"
        ><i></i
        >{{
          realtime.connectionStatus === "connected"
            ? "实时仿真数据"
            : "连接中断 · 保留上次数据"
        }}</span
      ><SimulationControls v-if="isDev" />
    </div>
  </div>
  <div v-if="error" class="operation-error" role="alert">
    {{ error }} <button class="twin-control" @click="load">重试</button>
  </div>
  <div
    class="operation-grid"
    data-testid="operation-page"
    :data-selected="selectedId"
  >
    <DeviceList
      :assets="assets"
      :devices="realtime.devices"
      :selected="selectedId"
      :loading="loading"
      @select="select"
    />
    <main class="operation-center">
      <DigitalTwinScene
        :realtime-state="realtime.state"
        :focus-device-id="selectedId"
        @device-select="select"
      />
      <DeviceSummary
        v-if="selected"
        :asset="selected"
        :live="live"
      /><DeviceRealtimeMetrics :device="live" />
      <p
        class="operation-sampling"
        :class="{ failed: sampling && !sampling.available }"
      >
        {{
          sampling?.available
            ? `● 历史采样在线 · ${sampling.intervalSeconds}s / 次`
            : (sampling?.message ?? "检查历史采样中…")
        }}
        <span>实时参数来自统一仿真数据流</span>
      </p>
    </main>
    <aside class="operation-analysis">
      <DeviceHealthCard :analysis="live?.analysis" /><DeviceAnomalyCard
        :analysis="live?.analysis"
      /><MaintenanceAdviceCard :advice="live?.analysis?.advice" />
    </aside>
  </div>
  <DeviceTrendChart :device-id="selectedId" :realtime-points="points" />
</template>
