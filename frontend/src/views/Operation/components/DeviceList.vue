<script setup lang="ts">
import { ref, computed } from "vue";
import type { DeviceAsset } from "../../../types/operation";
import type { DeviceState } from "../../../types/realtime";
import { deviceStatusLabels } from "../../../types/realtime";
const props = defineProps<{
  assets: DeviceAsset[];
  devices: DeviceState[];
  selected: string;
  loading: boolean;
}>();
const emit = defineEmits<{ select: [id: string] }>();
const keyword = ref(""),
  category = ref(""),
  status = ref("");
const categories = [
  ["", "全部"],
  ["pump", "排水泵"],
  ["valve", "阀门"],
  ["fan", "风机"],
  ["distribution_box", "配电"],
  ["fire_device", "消防"],
];
const rows = computed(() =>
  props.assets
    .map((asset) => ({
      asset,
      live: props.devices.find((d) => d.id === asset.id),
    }))
    .filter(
      ({ asset, live }) =>
        (!category.value || asset.deviceType === category.value) &&
        (!keyword.value.trim() ||
          (asset.deviceCode + asset.deviceName)
            .toLowerCase()
            .includes(keyword.value.trim().toLowerCase())) &&
        (!status.value ||
          status.value === (live?.status ?? asset.status) ||
          (status.value === "normal" &&
            ["running", "standby"].includes(live?.status ?? asset.status))),
    ),
);
</script>
<template>
  <aside class="panel device-list">
    <div class="panel-title">
      <h3>设备资产</h3>
      <span>{{ assets.length }} DEVICES</span>
    </div>
    <input
      v-model="keyword"
      aria-label="搜索设备"
      placeholder="搜索编号 / 设备名称"
      class="operation-input"
    />
    <div class="device-categories" role="group" aria-label="设备分类">
      <button
        v-for="[key, label] in categories"
        :key="key"
        :aria-pressed="category === key"
        @click="category = key!"
      >
        {{ label }}
      </button>
    </div>
    <select v-model="status" aria-label="设备状态过滤" class="operation-input">
      <option value="">全部状态</option>
      <option value="normal">正常</option>
      <option value="running">运行</option>
      <option value="standby">待机</option>
      <option value="warning">预警</option>
      <option value="offline">离线</option>
    </select>
    <p v-if="loading" class="operation-muted">加载资产中…</p>
    <p v-else-if="!rows.length" class="operation-empty">
      没有匹配设备。请选择已配置的设备分类或清空搜索条件。
    </p>
    <div class="device-list-items">
      <button
        v-for="{ asset, live } in rows"
        :key="asset.id"
        :data-testid="`device-${asset.id}`"
        :class="['device-list-item', { selected: selected === asset.id }]"
        :aria-pressed="selected === asset.id"
        @click="emit('select', asset.id)"
      >
        <div>
          <strong>{{ asset.deviceCode }}</strong
          ><span :class="`device-dot ${live?.status}`"></span>
        </div>
        <p>{{ asset.deviceName }}</p>
        <small
          >{{ live ? deviceStatusLabels[live.status] : asset.status
          }}<b
            >HI {{ (live?.health ?? asset.healthScore).toFixed(1) }}</b
          ></small
        >
      </button>
    </div>
    <p class="operation-muted device-provenance">
      软件仿真资产<br />B2 · 排水机房
    </p>
  </aside>
</template>
