import { registerTheme, type EChartsCoreOption } from 'echarts/core';

export const chartThemeName = 'twincity-safe';
export const chartColors = ['#35b9ff', '#ffd166', '#8278ff', '#37d9aa', '#ff7caa'];
const axis = {
  axisLine: { lineStyle: { color: '#225276' } },
  axisTick: { show: false },
  axisLabel: { color: '#7fa8c4', fontSize: 11 },
  nameTextStyle: { color: '#7fa8c4', fontSize: 11 },
  splitLine: { lineStyle: { color: '#163a58', type: 'dashed' } },
};
registerTheme(chartThemeName, {
  color: chartColors,
  backgroundColor: 'transparent',
  textStyle: { color: '#b9d8ee', fontFamily: '"PingFang SC", "Microsoft YaHei", sans-serif' },
  categoryAxis: axis,
  valueAxis: axis,
  timeAxis: axis,
  legend: { textStyle: { color: '#8db9d7', fontSize: 11 }, itemWidth: 16, itemHeight: 7 },
  tooltip: { confine: true, backgroundColor: '#071a2ddd', borderColor: '#277cb0', padding: [9, 12], textStyle: { color: '#d9efff', fontSize: 12 }, extraCssText: 'box-shadow:0 6px 24px #000a1c88;border-radius:5px' },
  line: { lineStyle: { width: 2 }, symbolSize: 5 },
});

// Presentation defaults preserve the caller's domains, units, series and actual observations.
export function chartOptions(option: EChartsCoreOption): EChartsCoreOption {
  // Old page options explicitly set dark-theme label/axis colors. Normalize only
  // presentation properties; series values, units, domains and callbacks are retained.
  function adapt(value: unknown, trail: string[] = []): unknown {
    if (Array.isArray(value)) return value.map(item => adapt(item, trail));
    if (!value || typeof value !== 'object' || Object.getPrototypeOf(value) !== Object.prototype) return value;
    const source = value as Record<string, unknown>;
    return Object.fromEntries(Object.entries(source).map(([key, item]) => {
      const context = trail.join('.');
      if (key === 'backgroundColor' && /tooltip/.test(context)) return [key, '#071a2ddd'];
      if (key === 'borderColor' && /tooltip/.test(context)) return [key, '#277cb0'];
      if (key === 'color' && Array.isArray(item) && /axisLine/.test(context)) return [key, item.map(stop => Array.isArray(stop) && typeof stop[1] === 'string' && /^#[0-3][0-9a-f][0-5][0-9a-f][0-6][0-9a-f]$/i.test(stop[1]) ? [stop[0], '#1b4769'] : stop)];
      if (key === 'color' && typeof item === 'string' && /^#[a-f\d]{3,8}$/i.test(item)) {
        if (/splitLine/.test(context)) return [key, '#163a58'];
        if (/axisLine|axisTick/.test(context)) return [key, '#225276'];
        if (/axisLabel|nameTextStyle|textStyle|detail|title|(^|\.)(label|endLabel)(\.|$)/.test(context)) return [key, '#8db9d7'];
        const strokes: Record<string,string> = { '#64c4d0':'#35b9ff', '#62cbd0':'#35b9ff', '#61c9df':'#35b9ff', '#e7b46b':'#ffd166', '#79cfac':'#37d9aa', '#83b6e4':'#8278ff' };
        if (strokes[item.toLowerCase()]) return [key, strokes[item.toLowerCase()]];
      }
      return [key, adapt(item, [...trail, key])];
    }));
  }
  return { backgroundColor: 'transparent', ...adapt(option) as EChartsCoreOption };
}
