<script setup lang="ts">
import { ref, watch } from 'vue';
import { use, type EChartsCoreOption } from 'echarts/core';
import { LineChart, BarChart, GaugeChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { useManagedChart } from '../../../charts/useManagedChart';
use([LineChart, BarChart, GaugeChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);
const props = defineProps<{ option: EChartsCoreOption; label: string }>();
const host = ref<HTMLDivElement>();
const { error, render, retry, getChart } = useManagedChart(host, () => props.option, () => {
  if (import.meta.env.DEV && host.value) Object.defineProperty(host.value, '__chartDebug', { get: () => ({ series: getChart()?.getOption().series ?? [] }), configurable: true });
});
watch(() => props.option, () => render());
</script>
<template>
  <div class="managed-chart">
    <div ref="host" class="operation-chart" :aria-label="label" role="img"></div>
    <div v-if="error" class="chart-error" role="status"><span>{{ error }}</span><button type="button" @click="retry">重新加载图表</button></div>
  </div>
</template>
