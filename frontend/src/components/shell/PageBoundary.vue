<script setup lang="ts">
import { onErrorCaptured, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
const route = useRoute(), failed = ref(false), generation = ref(0);
onErrorCaptured(() => { failed.value = true; return false; });
watch(() => route.path, () => { failed.value = false; generation.value++; });
function retry() { failed.value = false; generation.value++; }
</script>
<template><section v-if="failed" class="panel page-failure" role="alert"><h2>当前页面暂时无法显示</h2><p>请检查系统状态并重试。</p><button @click="retry">重新加载页面模块</button><RouterLink to="/dashboard">返回综合态势</RouterLink></section><slot v-else :key="generation" /></template>
<style scoped>.page-failure{margin:24px 0;padding:40px;display:grid;gap:20px}.page-failure button{width:max-content}</style>
