<script setup lang="ts">
import {computed,ref} from 'vue';
import type {PipelineAsset,PipelineType,ValveAsset} from '../../../types/pipeline';
import {typeLabels,statusLabels} from '../../../types/pipeline';
import type {PipelineState} from '../../../types/realtime';
const props=defineProps<{assets:PipelineAsset[];states:PipelineState[];selected:string;category:string;valves:ValveAsset[]}>();
const emit=defineEmits<{'select':[id:string];'category':[category:string];'valve':[id:string]}>();
const search=ref(''),status=ref('');
const rows=computed(()=>props.assets.filter(e=>(!props.category||props.category==='valves'||e.pipelineType===props.category)&&e.id.toLowerCase().includes(search.value.toLowerCase())&&(!status.value||(props.states.find(s=>s.id===e.id)?.status??e.status)===status.value)));
function live(id:string){return props.states.find(s=>s.id===id);}
</script>
<template><section class="panel pipeline-list"><h3>管网资产 <small>{{assets.length}} 管段</small></h3><nav class="pipe-categories"><button v-for="c in ['', 'water','drainage','fire','valves']" :key="c" :aria-pressed="category===c" @click="emit('category',c)">{{c==='valves'?'阀门':c?typeLabels[c as PipelineType]:'全部'}}</button></nav><input v-model="search" aria-label="搜索管段" placeholder="搜索管段编号"/><select v-model="status" aria-label="管段状态筛选"><option value="">全部状态</option><option v-for="(label,key) in statusLabels" :key="key" :value="key">{{label}}</option></select><div class="pipe-list-scroll" v-if="category==='valves'"><button class="pipe-row" v-for="v in valves.filter(v=>v.id.toLowerCase().includes(search.toLowerCase()))" :key="v.id" @click="emit('valve',v.id)"><strong>{{v.id}}</strong><span>{{v.status==='open'?'开启':v.status==='closed'?'关闭':'故障'}} · {{v.valveType}}</span></button></div><div class="pipe-list-scroll" v-else><button v-for="e in rows" :key="e.id" class="pipe-row" :data-pipeline-id="e.id" :aria-pressed="selected===e.id" @click="emit('select',e.id)"><strong>{{e.id}} <small>{{typeLabels[e.pipelineType]}}</small></strong><span>{{live(e.id)?.pressure.toFixed(3)??'—'}} MPa · {{live(e.id)?.flow.toFixed(1)??'—'}} m³/h</span><em>{{statusLabels[live(e.id)?.status??e.status]}}</em></button><p v-if="!rows.length">暂无匹配管段</p></div></section></template>
