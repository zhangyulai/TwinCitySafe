<script setup lang="ts">
import {ref,watch} from 'vue';
import {useManagedChart} from '../../../charts/useManagedChart';
import {use,type EChartsCoreOption} from 'echarts/core';
import {LineChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,MarkLineComponent,MarkAreaComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import type {ReplaySnapshot,ReplayGap} from '../../../types/review';
use([LineChart,GridComponent,TooltipComponent,MarkLineComponent,MarkAreaComponent,CanvasRenderer]);
const props=defineProps<{snapshots:ReplaySnapshot[];gaps:ReplayGap[];currentTime:number;metric:string;label:string;unit:string;startTime:number}>();
const emit=defineEmits<{seek:[time:number]}>();const host=ref<HTMLDivElement>();let lastCursor=-Infinity;
function value(snapshot:ReplaySnapshot):number|null{let current:unknown=snapshot.scene_state;for(const key of props.metric.split('.'))current=current&&typeof current==='object'?(current as Record<string,unknown>)[key]:undefined;return typeof current==='number'&&Number.isFinite(current)?current:null;}
function option():EChartsCoreOption{
 const points:(number|null)[][]=props.snapshots.map(s=>[s.simulation_time/60,value(s)]);
 props.gaps.forEach(g=>points.push([(g.from_time+g.to_time)/120,null]));points.sort((a,b)=>Number(a[0])-Number(b[0]));
 return {animation:false,tooltip:{trigger:'axis',valueFormatter:(v:unknown)=>typeof v==='number'?v.toFixed(3):'未记录'},grid:{left:62,right:24,top:28,bottom:38},xAxis:{type:'value',name:'仿真 min',min:props.startTime/60,axisLabel:{color:'#95adc4'},splitLine:{show:false}},yAxis:{type:'value',name:props.unit,axisLabel:{color:'#95adc4'},splitLine:{lineStyle:{color:'#22374c'}}},series:[{id:'history',name:props.label,type:'line',showSymbol:false,connectNulls:false,lineStyle:{color:'#62cbd0',width:2},data:points,markLine:{silent:true,symbol:'none',lineStyle:{color:'#ffc16d',type:'solid',width:2},label:{show:false},data:[{xAxis:props.currentTime/60}]},markArea:{silent:true,itemStyle:{color:'rgba(211,141,87,.15)'},label:{show:false},data:props.gaps.map(g=>[{xAxis:g.from_time/60},{xAxis:g.to_time/60}])}}]};
}
function cursor(){if(!getChart()||Math.abs(props.currentTime-lastCursor)<.10)return;lastCursor=props.currentTime;render({series:[{id:'history',markLine:{data:[{xAxis:props.currentTime/60}]}}]},false);}
const {error,render,retry,getChart}=useManagedChart(host,option,chart=>{
 chart.getZr().on('click',e=>{if(!chart.containPixel('grid',[e.offsetX,e.offsetY]))return;const coordinates=chart.convertFromPixel({gridIndex:0},[e.offsetX,e.offsetY]);if(Array.isArray(coordinates)&&Number.isFinite(coordinates[0]))emit('seek',coordinates[0]*60);});
 if(import.meta.env.DEV&&host.value)Object.defineProperty(host.value,'__reviewChartDebug',{get:()=>({currentTime:props.currentTime,metric:props.metric,series:getChart()?.getOption().series}),configurable:true});
});
watch(()=>[props.snapshots,props.gaps,props.metric],()=>{lastCursor=-Infinity;render();});watch(()=>props.currentTime,cursor);
</script><template><div class="managed-chart"><div ref="host" class="review-chart" :aria-label="label" role="img" data-testid="replay-chart" :data-cursor="currentTime"></div><div v-if="error" class="chart-error" role="status"><span>{{error}}</span><button type="button" @click="retry">重新加载图表</button></div></div></template>
