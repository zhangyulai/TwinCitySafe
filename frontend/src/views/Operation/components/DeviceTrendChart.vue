<script setup lang="ts">
import {
  computed,
  ref,
  shallowRef,
  watch,
  onBeforeUnmount,
  onMounted,
} from "vue";
import ChartCanvas from "./ChartCanvas.vue";
import { deviceApi } from "../../../api/devices";
import type {
  TelemetryPoint,
  TelemetryHistory,
} from "../../../types/operation";
const props = defineProps<{
  deviceId: string;
  realtimePoints: TelemetryPoint[];
}>();
const range = ref("5min");
const metric = ref<"temperature" | "vibration" | "current" | "efficiency">(
  "temperature",
);
const fields = [
  { key: "temperature", label: "温度", unit: "℃" },
  { key: "vibration", label: "振动", unit: "mm/s" },
  { key: "current", label: "电流", unit: "A" },
  { key: "efficiency", label: "效率", unit: "%" },
] as const;
const ranges = [
  ["5min", "5 min"],
  ["1h", "1 h"],
  ["6h", "6 h"],
  ["24h", "24 h"],
];
const history = shallowRef<TelemetryHistory | null>(null),
  error = ref(""),
  loading = ref(false);
let request: AbortController | undefined,
  generation = 0,
  timer: ReturnType<typeof setInterval> | undefined;
async function load() {
  const version = ++generation;
  request?.abort();
  error.value = "";
  if (range.value === "5min") {
    loading.value = false;
    return;
  }
  request = new AbortController();
  loading.value = true;
  try {
    const result = await deviceApi.history(
      props.deviceId,
      range.value,
      request.signal,
    );
    if (version === generation) history.value = result;
  } catch {
    if (version === generation)
      error.value = "历史查询失败，请检查数据库连接后重试。";
  } finally {
    if (version === generation) loading.value = false;
  }
}
watch(
  () => [props.deviceId, range.value],
  () => {
    history.value = null;
    void load();
  },
  { immediate: true },
);
onMounted(() => {
  timer = setInterval(() => {
    if (range.value !== "5min") void load();
  }, 30000);
});
onBeforeUnmount(() => {
  generation++;
  request?.abort();
  clearInterval(timer);
});
const points = computed(() =>
  range.value === "5min" ? props.realtimePoints : (history.value?.points ?? []),
);
const field = computed(() => fields.find((f) => f.key === metric.value)!);
const option = computed(() => ({
  animation: false,
  grid: { left: 52, right: 24, top: 26, bottom: 32 },
  tooltip: {
    trigger: "axis",
    confine: true,
    backgroundColor: "#0b2132",
    borderColor: "#345369",
    textStyle: { color: "#d3e7ed" },
    valueFormatter: (value: number) =>
      `${Number(value).toFixed(2)} ${field.value.unit}`,
  },
  xAxis: {
    type: "time",
    axisLine: { lineStyle: { color: "#2a4358" } },
    axisLabel: { color: "#88a8bb", fontSize: 10 },
    splitLine: { show: false },
  },
  yAxis: {
    type: "value",
    name: field.value.unit,
    scale: true,
    nameTextStyle: { color: "#94b4c5" },
    axisLabel: { color: "#88a8bb", fontSize: 10 },
    splitLine: { lineStyle: { color: "#1b3548" } },
  },
  series: [
    {
      id: "telemetry",
      type: "line",
      name: field.value.label,
      showSymbol: points.value.length < 3,
      symbolSize: 4,
      lineStyle: { width: 2, color: "#64c4d0" },
      itemStyle: { color: "#8fdfdf" },
      areaStyle: { color: "#2e8f9c", opacity: 0.1 },
      data: points.value.map((p) => [Date.parse(p.timestamp), p[metric.value]]),
    },
  ],
}));
</script>
<template>
  <section
    class="panel device-trend"
    data-testid="trend-chart"
    :data-count="points.length"
    :data-range="range"
  >
    <div class="trend-heading">
      <div class="panel-title">
        <h3>运行趋势 / {{ deviceId }}</h3>
        <span>TELEMETRY</span>
      </div>
      <div class="operation-tabs" role="group" aria-label="趋势时间范围">
        <button
          v-for="[key, label] in ranges"
          :key="key"
          :aria-pressed="range === key"
          @click="range = key!"
        >
          {{ label }}
        </button>
      </div>
    </div>
    <div class="trend-subhead">
      <div class="operation-tabs" role="tablist" aria-label="趋势指标">
        <button
          v-for="item in fields"
          :key="item.key"
          role="tab"
          :aria-selected="metric === item.key"
          @click="metric = item.key"
        >
          {{ item.label }}
        </button>
      </div>
      <span>{{
        range === "5min"
          ? "WebSocket 实时缓冲 · 最多 300 点"
          : `数据库采样 · 每 ${history?.sampleIntervalSeconds ?? 5} 秒`
      }}</span>
    </div>
    <p v-if="error" class="operation-error" role="alert">
      {{ error }} <button class="twin-control" @click="load">重试</button>
    </p>
    <p v-else-if="loading" class="operation-muted">加载历史数据…</p>
    <p v-else-if="!points.length" class="operation-muted">
      此时间范围暂无采样，数据不会补造；运行后每 5 秒逐步积累。
    </p>
    <ChartCanvas
      :option="option"
      :label="`${deviceId} ${field.label} 趋势图`"
    />
    <p class="operation-muted">
      {{
        history && range !== "5min"
          ? `窗口内 ${history.total} 条记录${history.downsampled ? "，均匀降采样至600点" : ""}`
          : "最近5分钟收到的运行样本；切页保留缓存，仿真Reset清空实时段"
      }}
      · 时间使用实际采样时间 · 软件仿真数据
    </p>
  </section>
</template>
