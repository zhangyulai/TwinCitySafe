<script setup lang="ts">
import type { MaintenanceAdvice } from "../../../types/operation";
defineProps<{ advice?: MaintenanceAdvice }>();
</script>
<template>
  <section
    class="panel maintenance-card"
    data-testid="maintenance-advice"
    :data-priority="advice?.priority"
  >
    <div class="panel-title">
      <h3>运维建议</h3>
      <span>{{ advice?.priority ?? "—" }}</span>
    </div>
    <h4>{{ advice?.title ?? "等待分析" }}</h4>
    <p>{{ advice?.message }}</p>
    <small>模板建议 · 不自动执行设备控制</small>
  </section>
</template>
