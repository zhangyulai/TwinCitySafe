<script setup lang="ts">
import type { DeviceState } from "../../../types/realtime";
defineProps<{ device?: DeviceState }>();
const fields = [
  { key: "temperature", label: "温度", unit: "℃", digits: 1 },
  { key: "vibration", label: "振动", unit: "mm/s", digits: 2 },
  { key: "current", label: "电流", unit: "A", digits: 1 },
  { key: "rpm", label: "转速", unit: "rpm", digits: 0 },
  { key: "efficiency", label: "效率", unit: "%", digits: 1 },
  { key: "health", label: "健康指数", unit: "/100", digits: 1 },
] as const;
</script>
<template>
  <section class="operation-metrics" data-testid="device-metrics">
    <div v-for="field in fields" :key="field.key">
      <span>{{ field.label }}</span
      ><strong
        >{{ device?.[field.key].toFixed(field.digits) ?? "—"
        }}<small>{{ field.unit }}</small></strong
      >
    </div>
  </section>
</template>
