<script setup lang="ts">
import { computed, ref } from 'vue';
import { api } from '../../api/client';
import { useDemoStore } from '../../store/useDemoStore';
import { useRealtimeStore } from '../../store/useRealtimeStore';
const props=defineProps<{open:boolean}>();const emit=defineEmits<{close:[]}>();
const demo=useDemoStore(),rt=useRealtimeStore(),testing=ref(false),checks=ref<{name:string;ok:boolean;message:string}[]>([]);
const fields=[['backend','后端服务'],['database','数据库'],['websocket','实时发布服务'],['anomaly_model','设备异常模型'],['risk_model','风险预测模型'],['pipeline_graph','管网拓扑']] as const;
const browserStatus=computed(()=>{void props.open;const host=document.querySelector('[data-testid="twin-scene"]') as HTMLElement & {__twinDebug?:{contextLost?:boolean}} | null;return !host?'当前页面无需三维场景':host.__twinDebug?.contextLost?'图形上下文已丢失':host.querySelector('canvas')?'三维画布已挂载':'场景加载中 / 请查看场景提示';});
async function selfCheck(){
 if(testing.value)return;testing.value=true;checks.value=[];
 await demo.check();
 const endpoints=[['基础健康','/health'],['实时快照','/realtime/state'],['管网拓扑','/pipelines/network'],['历史档案','/incidents?limit=1']] as const;
 const results=await Promise.allSettled(endpoints.map(async([name,url])=>{await api.get(url);return name}));
 checks.value=results.map((r,i)=>({name:endpoints[i]![0],ok:r.status==='fulfilled',message:r.status==='fulfilled'?'响应正常':'未能读取，请检查服务状态'}));
 checks.value.push({name:'浏览器 WebSocket',ok:rt.connectionStatus==='connected',message:rt.connectionStatus==='connected'?'已连接':'等待重新连接'});
 const canvas=document.querySelector('[data-testid="twin-scene"] canvas') as HTMLCanvasElement|null;
 const gl=canvas?(canvas.getContext('webgl2')??canvas.getContext('webgl')):null;
 checks.value.push({name:'Three.js 图形上下文',ok:!canvas||!!gl&&!gl.isContextLost(),message:!canvas?'当前页面未创建三维场景':gl&&!gl.isContextLost()?'可用':'不可用，可在场景内重试'});
 testing.value=false;
}
</script>
<template><div v-if="open" class="drawer-backdrop" @click.self="emit('close')"><section class="system-drawer" role="dialog" aria-modal="true" aria-labelledby="readiness-title" @keydown.esc="emit('close')"><header><div><h2 id="readiness-title">系统运行状态</h2><p>只读检测 · 不改变事故状态</p></div><button aria-label="关闭系统状态" @click="emit('close')">×</button></header><div class="readiness-summary" data-testid="system-readiness">{{!demo.readiness?'尚未连接就绪服务':demo.readiness.ready?'系统就绪':demo.readiness.degraded?'部分能力降级':'需要检查运行环境'}}</div><ul class="status-list"><li v-for="[key,label] in fields" :key="key"><span>{{label}}</span><strong :class="{ok:demo.readiness?.[key]?.available}">{{demo.readiness?.[key]?.available?'可用':'未就绪'}}</strong><p>{{demo.readiness?.[key]?.message??'尚未获取检测结果'}}</p></li><li><span>浏览器实时连接</span><strong :class="{ok:rt.connectionStatus==='connected'}">{{rt.connectionStatus==='connected'?'已连接':'等待连接'}}</strong><p>后端发布状态与当前浏览器连接分别检查。</p></li><li><span>Three.js</span><p>{{browserStatus}}</p></li></ul><div class="drawer-actions"><button :disabled="demo.checking" @click="demo.check">刷新状态</button><button data-testid="system-self-check" :disabled="testing" @click="selfCheck">{{testing?'正在检测…':'系统自检'}}</button></div><ul v-if="checks.length" class="self-check-results" data-testid="self-check-results"><li v-for="check in checks" :key="check.name" :class="{ok:check.ok}">{{check.ok?'✓':'!'}} {{check.name}}：{{check.message}}</li></ul><p class="drawer-note">模型不可用时保留物理预测。软件数字孪生演示不用于真实安全决策。</p></section></div></template>
<style scoped>
.drawer-backdrop{position:fixed;inset:0;z-index:90;background:#020910b3;display:flex;justify-content:flex-end;backdrop-filter:blur(2px)}
.system-drawer{width:min(480px,100vw);padding:24px;background:linear-gradient(180deg,#08233f 0%,#05172c 100%);border-left:1px solid #2386bc;overflow:auto;box-shadow:-14px 0 46px #00101ddd,inset 1px 0 #40d4ff2b;color:#bfe7fa;scrollbar-color:#2679a8 #06182b}
.system-drawer header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1a5d86;padding-bottom:16px}.system-drawer h2{font-size:20px;color:#d9f5ff;text-shadow:0 0 12px #21bff866}.system-drawer header p,.drawer-note{font-size:12px;color:#75afd0;margin-top:10px;line-height:1.8}.system-drawer button{background:linear-gradient(180deg,#0b3b60,#082642);border:1px solid #2b90c2;color:#c9f0ff;border-radius:3px;padding:7px 12px;cursor:pointer;box-shadow:inset 0 0 12px #26c7f51f}.system-drawer button:hover{background:linear-gradient(180deg,#0d527d,#093451);border-color:#54dbff;color:#f0fdff}.system-drawer header button{min-width:38px;padding:7px 10px;font-weight:700;font-size:16px}
.system-drawer .readiness-summary{padding:16px;background:linear-gradient(90deg,#092d4d,#08223b)!important;border:1px solid #1d6c9d;margin:20px 0;border-radius:3px;color:#62d5ff!important;box-shadow:inset 0 0 20px #0f8cc51c}.status-list{padding:0;margin:0;list-style:none}.status-list li{display:grid;grid-template-columns:1fr auto;gap:6px;border-bottom:1px solid #174c70;padding:12px 0;font-size:13px}.status-list li>span{color:#84bfdc}.status-list strong{color:#ffbd69;font-size:12px}.status-list p{grid-column:1/-1;color:#669fc0;line-height:1.6;font-size:11px;overflow-wrap:anywhere}.status-list .ok,.self-check-results .ok{color:#42e1ae}.drawer-actions{display:flex;gap:10px;margin:20px 0}.self-check-results{padding:0;list-style:none;font-size:12px;line-height:2;color:#ffbd69}.drawer-note{border-top:1px solid #174c70;padding-top:14px}
</style>
