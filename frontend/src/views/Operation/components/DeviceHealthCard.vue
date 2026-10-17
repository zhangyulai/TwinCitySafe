<script setup lang="ts">
import { computed } from "vue";
import ChartCanvas from "./ChartCanvas.vue";
import type { DeviceAnalysis } from "../../../types/operation";
const props = defineProps<{ analysis?: DeviceAnalysis | null }>();
const option = computed(() => ({
  animation: false,
  series: [
    {
      type: "gauge",
      startAngle: 220,
      endAngle: -40,
      min: 0,
      max: 100,
      radius: "94%",
      center: ["50%", "60%"],
      pointer: { show: false },
      progress: {
        show: true,
        width: 9,
        itemStyle: {
          color:
            !props.analysis || props.analysis.healthScore >= 80
              ? "#61cbb2"
              : props.analysis.healthScore >= 60
                ? "#dabb68"
                : "#df8669",
        },
      },
      axisLine: { lineStyle: { width: 9, color: [[1, "#20394b"]] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: false },
      detail: {
        offsetCenter: [0, "-2%"],
        fontSize: 32,
        fontFamily: "sans-serif",
        color: "#d5eaf0",
        formatter: (value: number) => value.toFixed(1),
      },
      data: [{ value: props.analysis?.healthScore ?? 0 }],
    },
  ],
}));
</script>
<template>
  <section
    class="panel device-health"
    data-testid="health-card"
    :data-value="analysis?.healthScore"
  >
    <div class="panel-title">
      <h3>健康指数</h3>
      <span>HEALTH INDEX</span>
    </div>
    <ChartCanvas v-if="analysis" :option="option" label="设备健康指数仪表" /><div v-else class="health-empty">—<small>等待健康数据</small></div>
    <p>
      <strong>{{ analysis?.healthGrade ?? "等待数据" }}</strong
      ><span>0–100 · 规则加权 / 平滑</span>
    </p>
  </section>
</template>
