<script setup lang="ts">
import type { DeviceAsset } from "../../../types/operation";
import type { DeviceState } from "../../../types/realtime";
import { deviceStatusLabels } from "../../../types/realtime";
import { parkAssetArea, parkBuildingName } from "../../../config/park";
defineProps<{ asset: DeviceAsset; live?: DeviceState }>();
</script>
<template>
  <section class="panel device-summary" data-testid="device-summary">
    <div class="panel-title">
      <h3>{{ asset.deviceName }}</h3>
      <span>{{ asset.deviceCode }} / ASSET</span>
    </div>
    <p>
      {{ parkAssetArea(asset.areaId) }} ·
      {{ live ? deviceStatusLabels[live.status] : asset.status }} ·
      {{ parkBuildingName(asset.buildingId) }}
    </p>
    <dl>
      <div>
        <dt>累计运行</dt>
        <dd>{{ (live?.runtimeHours ?? asset.runtimeHours).toFixed(1) }} h</dd>
      </div>
      <div>
        <dt>上次维护</dt>
        <dd>{{ asset.lastMaintenance }}</dd>
      </div>
      <div>
        <dt>额定转速</dt>
        <dd>{{ asset.ratedRpm }} rpm</dd>
      </div>
      <div>
        <dt>额定功率</dt>
        <dd>{{ asset.ratedPower }} kW</dd>
      </div>
      <div>
        <dt>额定电流 / 流量</dt>
        <dd>{{ asset.ratedCurrent }} A / {{ asset.ratedCapacity }} m³/h</dd>
      </div>
      <div>
        <dt>安装日期</dt>
        <dd>{{ asset.installDate }}</dd>
      </div>
    </dl>
  </section>
</template>
