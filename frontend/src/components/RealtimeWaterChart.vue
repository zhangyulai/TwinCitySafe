<script setup lang="ts">
import { ref, watch } from 'vue';
import { use, type EChartsCoreOption } from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { WaterSample } from '../store/useRealtimeStore';
import { useManagedChart } from '../charts/useManagedChart';
use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);
const props = defineProps<{ samples: WaterSample[] }>();
const host = ref<HTMLDivElement>();
function option(): EChartsCoreOption {
  return {
    animation: false, grid: { left: 38, right: 10, top: 24, bottom: 23 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', boundaryGap: false, data: props.samples.map(s => `${s.time.toFixed(0)}s`), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'cm', min: 0, max: (extent: { max: number }) => Math.max(3, Math.ceil(extent.max * 1.15)), splitNumber: 3, axisLabel: { fontSize: 10 } },
    series: [{ type: 'line', name: 'B2 水位', showSymbol: props.samples.length < 3, symbolSize: 4, data: props.samples.map(s => s.water), lineStyle: { color: '#62cbd0', width: 2 }, itemStyle: { color: '#79d8df' }, areaStyle: { color: '#245a70', opacity: .15 } }],
  };
}
const { error, render, retry } = useManagedChart(host, option);
watch(() => props.samples, () => render());
</script>
<template><div class="managed-chart"><div ref="host" class="realtime-water-chart" aria-label="B2 地下停车场最近 60 个采样水位图"></div><div v-if="error" class="chart-error" role="status"><span>{{ error }}</span><button type="button" @click="retry">重新加载图表</button></div></div></template>
