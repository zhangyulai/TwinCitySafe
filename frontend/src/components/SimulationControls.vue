<script setup lang="ts">
import { computed, ref } from "vue";
import { isAxiosError } from "axios";
import { simulationApi } from "../api/realtime";
import { useRealtimeStore } from "../store/useRealtimeStore";
import type {
  DeviceStatus,
  ParkRealtimeState,
  WeatherCondition,
} from "../types/realtime";
import { faultLabels, type FaultProfile } from "../types/operation";
import { deviceStatusLabels } from "../types/realtime";
const realtime = useRealtimeStore();
const open = ref(false);
const busy = ref(false);
const feedback = ref("");
const failed = ref(false);
const disabled = computed(
  () => busy.value || realtime.connectionStatus !== "connected",
);
const weatherOptions: { value: WeatherCondition; label: string }[] = [
  { value: "clear", label: "Clear" },
  { value: "cloudy", label: "Cloudy" },
  { value: "rain", label: "Rain" },
];
const deviceOptions: DeviceStatus[] = [
  "standby",
  "running",
  "warning",
  "offline",
];
async function run(action: () => Promise<ParkRealtimeState>): Promise<void> {
  if (disabled.value) return;
  busy.value = true;
  feedback.value = "";
  failed.value = false;
  try {
    realtime.applyRealtimeState(await action());
    feedback.value = "控制已应用，参数将平滑过渡。";
  } catch (error) {
    failed.value = true;
    feedback.value = isAxiosError(error)
      ? `仿真控制失败（${error.response?.status ?? "连接异常"}），请重试。`
      : "仿真控制失败，请重试。";
  } finally {
    busy.value = false;
  }
}
function changeDevice(id: string, event: Event): void {
  const target = event.target as HTMLSelectElement;
  const status = target.value as DeviceStatus;
  // Keep the controlled select at confirmed state until the server acknowledges it.
  target.value = realtime.getDeviceById(id)?.status ?? "standby";
  void run(() => simulationApi.device(id, status));
}
function changeFault(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const fault = target.value as FaultProfile;
  target.value = realtime.getDeviceById("P03")?.fault ?? "normal";
  void run(() => simulationApi.fault("P03", fault));
}
function changeSpeed(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const speed = Number(target.value);
  target.value = String(realtime.state?.speed ?? 1);
  void run(() => simulationApi.speed(speed));
}
</script>
<template>
  <div class="simulation-controls-wrap">
    <button class="twin-control" :aria-expanded="open" @click="open = !open">
      仿真控制
    </button>
    <section
      v-if="open"
      class="simulation-controls"
      data-testid="simulation-controls"
      aria-label="开发仿真控制"
    >
      <div class="simulation-controls-heading">
        <h3>仿真控制</h3>
        <span>仅开发模式</span
        ><button aria-label="关闭仿真控制" @click="open = false">×</button>
      </div>
      <p class="muted">控制软件仿真源；当前数据不来自传感器。</p>
      <div class="simulation-weather">
        <span>Weather</span>
        <div>
          <button
            v-for="option in weatherOptions"
            :key="option.value"
            class="twin-control"
            :class="{ active: realtime.weather?.condition === option.value }"
            :aria-pressed="realtime.weather?.condition === option.value"
            :disabled="disabled"
            @click="run(() => simulationApi.weather(option.value))"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
      <label
        v-for="id in ['P01', 'P02', 'P03']"
        :key="id"
        class="simulation-select"
        ><span>{{ id }} 排水泵</span
        ><select
          :aria-label="`${id} 状态`"
          :value="realtime.getDeviceById(id)?.status ?? 'standby'"
          :disabled="disabled"
          @change="changeDevice(id, $event)"
        >
          <option v-for="value in deviceOptions" :key="value" :value="value">
            {{ value }} · {{ deviceStatusLabels[value] }}
          </option>
        </select></label
      >
      <label class="simulation-select"
        ><span>P03 故障工况</span>
        <select
          aria-label="P03 故障工况"
          :value="realtime.getDeviceById('P03')?.fault ?? 'normal'"
          :disabled="disabled"
          @change="changeFault"
        >
          <option v-for="(label, key) in faultLabels" :key="key" :value="key">
            {{ label }} · {{ key }}
          </option>
        </select>
      </label>
      <label class="simulation-select"
        ><span>模拟速度</span
        ><select
          aria-label="模拟速度"
          :value="realtime.state?.speed ?? 1"
          :disabled="disabled"
          @change="changeSpeed"
        >
          <option
            v-for="speed in [0.25, 1, 2, 5, 10]"
            :key="speed"
            :value="speed"
          >
            {{ speed }}×
          </option>
        </select></label
      >
      <div class="simulation-buttons">
        <button
          class="twin-control"
          :disabled="disabled"
          @click="run(simulationApi.start)"
        >
          Start</button
        ><button
          class="twin-control"
          :disabled="disabled"
          @click="run(simulationApi.stop)"
        >
          Stop</button
        ><button
          class="twin-control"
          :disabled="disabled"
          @click="run(simulationApi.reset)"
        >
          Reset</button
        ><span>{{ realtime.state?.running ? "运行中" : "已暂停" }}</span>
      </div>
      <p class="simulation-control-note">
        速度改变模拟时间推进；推送频率保持 1 Hz。Reset
        恢复初始参数并保留启停状态。
      </p>
      <p
        v-if="feedback"
        class="simulation-feedback"
        :class="{ failed }"
        role="status"
      >
        {{ feedback }}
      </p>
    </section>
  </div>
</template>
