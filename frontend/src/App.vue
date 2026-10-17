<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { navigation } from './router';
import { useRealtimeStore } from './store/useRealtimeStore';
import { useServiceStore } from './store/useServiceStore';
import { useDemoStore } from './store/useDemoStore';
import DemoControls from './components/shell/DemoControls.vue';
import SystemDrawer from './components/shell/SystemDrawer.vue';
import AboutDialog from './components/shell/AboutDialog.vue';
import PageBoundary from './components/shell/PageBoundary.vue';
import WorkspaceIcon from './components/shell/WorkspaceIcon.vue';
import { floodLevelLabels } from './types/flood';
const realtime=useRealtimeStore(),service=useServiceStore(),demo=useDemoStore(),router=useRouter();
const drawer=ref(false),about=ref(false),clock=ref(new Date()),routeLoading=ref(false),fullscreenError=ref('');
const route=useRoute();
const currentPage=computed(()=>navigation.find(item=>item.path===route.path)?.label??'综合态势');
let ticker:ReturnType<typeof setInterval>|undefined,healthTimer:ReturnType<typeof setInterval>|undefined;
const removeBefore=router.beforeEach(()=>{routeLoading.value=true;});const removeAfter=router.afterEach(()=>{routeLoading.value=false;});
const removeError=router.onError(()=>{routeLoading.value=false;});
const incident=computed(()=>!realtime.state?'等待连接':realtime.state.flood?.scenarioId?`暴雨内涝 · ${floodLevelLabels[realtime.state.flood.riskLevel]}`:realtime.state.leak?.scenarioId?`管网泄漏 · ${floodLevelLabels[realtime.state.leak.riskLevel as keyof typeof floodLevelLabels] ?? realtime.state.leak.riskLevel}`:'系统正常');
const incidentPath=computed(()=>realtime.state?.leak?.scenarioId?'/pipeline?mode=leak':'/simulation');
async function showStatus(){drawer.value=true;await Promise.all([service.checkHealth(),demo.check()]);}
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();fullscreenError.value='';}catch{fullscreenError.value='浏览器未允许全屏，请使用浏览器全屏快捷键。';}}
onMounted(()=>{realtime.connect();void service.checkHealth();void demo.check();demo.setEnabled(demo.enabled);ticker=setInterval(()=>clock.value=new Date(),1000);healthTimer=setInterval(()=>{void service.checkHealth();void demo.check();},30000);});
onBeforeUnmount(()=>{clearInterval(ticker);clearInterval(healthTimer);realtime.disconnect();removeBefore();removeAfter();removeError();});
</script>
<template><div class="app-shell workspace">
  <a class="skip-link" href="#workspace-main">跳转到页面内容</a>
  <aside class="workspace-sidebar">
    <RouterLink to="/dashboard" class="workspace-brand" aria-label="孪城智安首页"><span class="workspace-monogram">孪</span><div><h1>孪城智安</h1><small>TwinCitySafe</small></div></RouterLink>
    <div class="command-center-title"><span>数字孪生 · 实时协同 · 安全闭环</span><strong>智慧园区综合指挥中心</strong><i></i></div>
    <div class="workspace-project"><span class="workspace-project-icon">园</span><div><strong>智慧园区</strong><small>数字孪生工作空间</small></div><span class="workspace-project-dot"></span></div>
    <p class="workspace-nav-label">园区安全管理</p>
    <nav class="workspace-navigation" aria-label="主导航"><RouterLink v-for="item in navigation" :key="item.path" :to="item.path" :title="item.label"><WorkspaceIcon :name="item.path.slice(1)"/><span>{{item.label}}</span><i></i></RouterLink></nav>
    <div class="workspace-sidebar-bottom"><div class="workspace-environment"><span></span><div><strong>软件仿真环境</strong><small>监测 · 研判 · 处置 · 复盘</small></div></div><button @click="about=true">关于平台 <span>↗</span></button></div>
  </aside>
  <div class="workspace-body">
  <header class="workspace-header"><div class="workspace-breadcrumb"><span>园区安全工作台</span><span>/</span><strong>{{currentPage}}</strong></div>
    <div class="workspace-header-meta"><span data-testid="realtime-connection" class="workspace-connection" :class="realtime.connectionStatus"><i></i>{{realtime.connectionStatus==='connected'?'实时连接正常':realtime.connectionStatus==='connecting'?'正在连接':'实时连接断开'}}</span><time>{{clock.toLocaleDateString('zh-CN',{month:'2-digit',day:'2-digit'})}}<b>{{clock.toLocaleTimeString('zh-CN',{hour12:false})}}</b></time><button class="workspace-status-button" @click="showStatus">系统状态 <i :class="service.status.toLowerCase()"></i></button></div>
  </header>
  <div class="workspace-content">
  <div class="workspace-utility"><RouterLink :to="incident==='系统正常'?'/dashboard':incidentPath" class="workspace-incident" :class="{active:incident!=='系统正常'}"><i></i>{{incident}}</RouterLink><span class="workspace-scope">园区运维与安全协同平台</span><div class="workspace-tools"><button data-testid="demo-toggle" :class="{selected:demo.enabled}" @click="demo.setEnabled(!demo.enabled)">{{demo.enabled?'演示模式已开启':'演示模式'}}</button><button @click="fullscreen">全屏展示</button></div></div>
  <p v-if="fullscreenError" role="status" class="fullscreen-message">{{fullscreenError}}</p>
  <DemoControls/>
  <div v-if="routeLoading" class="route-loading" role="status">正在加载页面…</div>
  <main id="workspace-main" tabindex="-1"><PageBoundary><RouterView/></PageBoundary></main>
  <footer class="app-footer"><span>TwinCitySafe · 软件数字孪生演示平台</span><span>监测 · 预测 · 推演 · 处置 · 复盘</span></footer>
  </div></div><SystemDrawer :open="drawer" @close="drawer=false"/><AboutDialog :open="about" @close="about=false"/>
</div></template>
<style scoped>
.fullscreen-message { margin-top: 12px; font-size: 12px; color: #946315; text-align: right; }
.route-loading { position: fixed; left: 50%; top: 88px; z-index: 60; transform: translateX(-50%); background: linear-gradient(135deg, #08233d, #0b3553); border: 1px solid #168fd0; padding: 10px 20px; border-radius: 5px; color: #9eeaff; box-shadow: 0 8px 26px #000a; letter-spacing: .04em; }
</style>
