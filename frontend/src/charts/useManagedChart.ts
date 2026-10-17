import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue';
import { init, type EChartsType, type EChartsCoreOption } from 'echarts/core';
import { chartOptions, chartThemeName } from './theme';

/** One chart per mounted host. A rendering failure remains local to this chart. */
export function useManagedChart(host: Ref<HTMLElement | undefined>, getOption: () => EChartsCoreOption, setup?: (chart: EChartsType) => void) {
  let chart: EChartsType | undefined;
  let observer: ResizeObserver | undefined;
  let disposed = false;
  const error = ref('');
  function guarded(action: () => void) {
    try { action(); error.value = ''; }
    catch { error.value = '图表暂时无法显示，其他指标仍可查看。'; }
  }
  function render(option?: EChartsCoreOption, replace = true) {
    if (disposed || !chart) return;
    guarded(() => chart!.setOption(chartOptions(option ?? getOption()), { notMerge: replace, lazyUpdate: true }));
  }
  function retry() {
    if (disposed || !host.value) return;
    observer?.disconnect();
    chart?.dispose();
    chart = undefined;
    guarded(() => {
      chart = init(host.value!, chartThemeName, { renderer: 'canvas', devicePixelRatio: Math.min(window.devicePixelRatio, 1.5) });
      chart.setOption(chartOptions(getOption()));
      setup?.(chart);
      observer = new ResizeObserver(() => { if (chart && !disposed) guarded(() => chart!.resize()); });
      observer.observe(host.value!);
    });
  }
  onMounted(retry);
  onBeforeUnmount(() => { disposed = true; observer?.disconnect(); chart?.dispose(); chart = undefined; });
  return { error, render, retry, getChart: () => chart };
}
