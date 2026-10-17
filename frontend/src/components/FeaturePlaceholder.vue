<script setup lang="ts">
defineProps<{
  title: string;
  english: string;
  description: string;
  milestone: string;
}>();
</script>
<template>
  <section class="feature-placeholder panel">
    <span class="eyebrow">{{ english }}</span>
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
    <div class="placeholder-mark">⌘</div>
    <el-tag effect="plain">规划阶段 · {{ milestone }}</el-tag>
    <p class="muted">
      当前已建立页面路由与布局，业务功能将在后续里程碑逐步开放。
    </p>
    <RouterLink to="/dashboard" class="back-link">返回综合态势 →</RouterLink>
  </section>
</template>
