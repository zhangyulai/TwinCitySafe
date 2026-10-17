<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useDemoStore } from '../../store/useDemoStore';
import { useRealtimeStore } from '../../store/useRealtimeStore';
import { leakStageLabels } from '../../types/leak';
import { floodStageLabels } from '../../types/flood';
const demo = useDemoStore(), rt = useRealtimeStore(), router = useRouter(), route = useRoute();
const scenario = ref<'flood' | 'leak'>('flood');
const active = computed(() => rt.state?.flood?.scenarioId ? 'flood' : rt.state?.leak?.scenarioId ? 'leak' : null);
const current = computed(() => active.value === 'flood' ? rt.state?.flood : active.value === 'leak' ? rt.state?.leak : null);
const score = computed(() => current.value?.riskScore ?? 0);
const stage = computed(() => active.value === 'flood' ? floodStageLabels[rt.state!.flood!.stage] : leakStageLabels[rt.state?.leak?.currentStage ?? ''] ?? '持续监测');
const phase = computed(() => route.path === '/review' ? 4 : !active.value ? 0 : active.value === 'flood' ? rt.state?.emergency ? 3 : score.value >= 60 ? 2 : 1 : rt.state?.leak?.execution ? 3 : rt.state?.leak?.confirmedAt ? 2 : 1);
const guide = computed(() => !active.value ? '选择一类事故启动，或进入历史档案查看完整闭环。' : active.value === 'flood' ? rt.state?.emergency ? '观察雨势与排水变化；风险稳定后，在事件复盘完成工单并人工关闭。' : score.value >= 60 ? '暂停时钟，比较方案并主动选择；确认执行后继续时钟。' : '观察 P03 状态与积水变化，进入风险研判查看未来预测。' : rt.state?.leak?.execution ? '观察隔离后流量与供水影响；稳定后完成工单并人工关闭。' : rt.state?.leak?.confirmedAt ? '暂停时钟，比较阀门隔离范围，人工选择并确认执行。' : '观察压力与流量残差，等待定位排名和异常确认。');
async function start(value = scenario.value) {
  demo.setEnabled(true); scenario.value = value;
  if (active.value) { demo.error = '当前已有活动事故。请完成并关闭，或使用演示重置后再启动。'; return; }
  if (!window.confirm(`启动${value === 'flood' ? '暴雨内涝' : '管网泄漏'}软件演示？系统将以 10× 仿真时间运行，处置方案仍需人工选择与确认。`)) return;
  if (await demo.control('start', { scenario: value, confirmed: true })) await router.push(value === 'flood' ? '/simulation' : '/pipeline?mode=leak');
}
async function reset() { if (window.confirm('将重置当前软件演示状态，但不会删除历史事故档案。')) await demo.control('reset', { confirmed: true }); }
function quickStart(event: Event) { const value = (event as CustomEvent).detail?.scenario; if (value === 'flood' || value === 'leak') void start(value); }
onMounted(() => window.addEventListener('twincity-demo-start', quickStart));
onBeforeUnmount(() => window.removeEventListener('twincity-demo-start', quickStart));
</script>
<template>
  <div v-if="active" class="incident-strip" :class="{high:score>=60}" data-testid="incident-banner">
    <RouterLink :to="active==='flood'?'/simulation':'/pipeline?mode=leak'"><b>{{active==='flood'?'暴雨内涝':'管网泄漏'}}</b> · {{stage}} · 规则风险 {{score.toFixed(1)}} · T+{{((current?.elapsedSimulationSeconds??0)/60).toFixed(1)}} min <span>查看事故 →</span></RouterLink>
    <span class="data-badge">软件仿真</span>
  </div>
  <section v-if="demo.enabled" class="demo-console" data-testid="demo-controls" aria-label="比赛演示控制">
    <div class="demo-actions"><b>演示控制</b><label>事故场景 <select v-model="scenario" aria-label="演示场景"><option value="flood">暴雨内涝</option><option value="leak">管网泄漏</option></select></label>
      <button data-testid="demo-start" :disabled="demo.busy||!!active||demo.readiness?.demo_enabled===false" @click="start()">启动演示</button>
      <label>速度 <select aria-label="演示速度" :value="rt.state?.speed??1" :disabled="demo.busy" @change="demo.control('speed',{speed:Number(($event.target as HTMLSelectElement).value)})"><option v-for="s in [1,2,5,10]" :key="s" :value="s">{{s}}×</option></select></label>
      <button data-testid="demo-pause" :disabled="demo.busy" @click="demo.control(rt.state?.running?'pause':'resume')">{{rt.state?.running?'暂停':'继续'}}</button><button data-testid="demo-reset" :disabled="demo.busy" @click="reset">重置演示</button>
      <span class="demo-clock">{{rt.state?.running?'时钟运行中':'时钟已暂停'}}</span><button class="quiet" @click="demo.setEnabled(false)">收起</button>
    </div>
    <div class="demo-guidance"><ol aria-label="安全闭环"><li v-for="(step,i) in ['监测','预测 / 定位','方案推演','人工处置','历史复盘']" :key="step" :class="{current:i===phase,done:i<phase}">{{i+1}} {{step}}</li></ol><p>{{guide}}</p><RouterLink :to="!active?'/review':active==='flood'&&phase===1?'/risk':phase===3?'/review':active==='leak'?'/pipeline?mode=leak':'/simulation'">下一步 →</RouterLink></div>
    <p v-if="demo.readiness?.demo_enabled===false" class="control-error">当前服务未开放演示控制，请使用比赛启动脚本。</p>
    <p v-if="demo.error" class="control-error" role="alert">{{demo.error}}</p><p v-else-if="demo.notice" class="control-notice" role="status">{{demo.notice}}</p>
  </section>
</template>
<style scoped>
.incident-strip{display:flex;justify-content:space-between;gap:16px;background:#07312f;border-left:3px solid #29c99a;padding:8px 14px;margin-top:10px;font-size:12px;color:#a8dfd5}.incident-strip.high{border-color:#ffb25e;background:#322514}.incident-strip a{flex:1;color:#bfefff}.incident-strip a span{margin-left:14px;color:#d6f7ff}.data-badge{font-size:10px;color:#91c9e5}.demo-console{margin-top:12px;border:1px solid #1b6692;border-radius:3px;background:linear-gradient(90deg,#061b31,#082642);box-shadow:inset 0 0 18px #087db51f;padding:12px 16px;color:#b8e0f4}.demo-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:12px}.demo-actions b{color:#a9e7ff}.demo-actions label{display:flex;align-items:center;gap:6px;color:#9dcae2}.demo-actions button,.demo-actions select{color:#c9efff;background:linear-gradient(180deg,#0a2947,#071d34);border:1px solid #2479aa;border-radius:3px;padding:6px 10px;box-shadow:inset 0 0 10px #0b86c51f}.demo-actions button{cursor:pointer}.demo-actions button:disabled{opacity:.45;cursor:default}.demo-clock{margin-left:auto;color:#74aecd}.demo-actions .quiet{background:transparent;border-color:transparent;box-shadow:none}.demo-guidance{display:flex;align-items:center;gap:18px;margin-top:10px;font-size:11px;color:#78abc8}.demo-guidance ol{padding:0;display:flex;gap:10px;list-style:none;margin:0;flex-shrink:0}.demo-guidance li.current{color:#55d9ff}.demo-guidance li.done{color:#42e1ae}.demo-guidance p{line-height:1.6;flex:1}.demo-guidance a{white-space:nowrap;color:#69d8ff}.control-error{margin-top:9px;color:#ffb06a;font-size:12px}.control-notice{margin-top:9px;color:#4be0b3;font-size:11px}@media(max-width:1450px){.demo-guidance{flex-wrap:wrap;gap:8px 16px}.demo-guidance p{min-width:450px}}@media(max-width:760px){.demo-guidance p{min-width:0;flex-basis:100%}.demo-guidance ol{flex-wrap:wrap}}
</style>
