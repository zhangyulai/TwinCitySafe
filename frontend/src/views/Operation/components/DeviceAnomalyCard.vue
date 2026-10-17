<script setup lang="ts">
import { computed } from "vue";
import ChartCanvas from "./ChartCanvas.vue";
import { anomalyLabels, type DeviceAnalysis } from "../../../types/operation";
const props = defineProps<{ analysis?: DeviceAnalysis | null }>();
const option = computed(() => ({
  animation: false,
  grid: { left: 40, right: 38, top: 6, bottom: 4 },
  xAxis: { type: "value", max: 100, show: false },
  yAxis: {
    type: "category",
    inverse: true,
    data: props.analysis?.contributions.map((v) => v.label) ?? [],
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: "#92b0c0", fontSize: 10 },
  },
  series: [
    {
      type: "bar",
      barWidth: 7,
      itemStyle: { color: "#67acbd", borderRadius: 3 },
      label: {
        show: true,
        position: "right",
        color: "#bbd6df",
        fontSize: 10,
        formatter: "{c}%",
      },
      data:
        props.analysis?.contributions.map((v) =>
          Math.round(v.contribution * 100),
        ) ?? [],
    },
  ],
}));
</script>
<template>
  <section
    class="panel device-anomaly"
    data-testid="anomaly-card"
    :data-score="analysis?.anomalyScore"
    :data-level="analysis?.level"
  >
    <div class="panel-title">
      <h3>异常检测</h3>
      <span>ISOLATION FOREST</span>
    </div>
    <div class="anomaly-score">
      <strong>{{ analysis?.anomalyScore?.toFixed(2) ?? "—" }}</strong
      ><span :class="`anomaly-level ${analysis?.level}`">{{
        analysis ? anomalyLabels[analysis.level] : "等待数据"
      }}</span>
    </div>
    <p class="operation-muted">分数越高偏离越明显 · 非故障概率</p>
    <h4>偏离度贡献 / 非 SHAP</h4>
    <ChartCanvas
      v-if="analysis?.contributions.length"
      :option="option"
      label="相对基线偏离度贡献条形图"
    />
    <p v-else class="operation-muted">当前工况暂无贡献分析</p>
    <p class="anomaly-explanation">{{ analysis?.explanation }}</p>
    <p
      v-if="analysis?.activeAlarmId"
      class="active-alarm"
      data-testid="active-alarm"
    >
      ● 活动告警 · 持续异常去重记录
    </p>
  </section>
</template>
