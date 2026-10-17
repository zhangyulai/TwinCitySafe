<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

type AMapMap = { destroy: () => void; addControl?: (control: unknown) => void; add?: (overlay: unknown | unknown[]) => void };
type AMapConstructor = {
  Map: new (container: HTMLElement, options: Record<string, unknown>) => AMapMap;
  Marker: new (options: Record<string, unknown>) => unknown;
  ControlBar?: new (options?: Record<string, unknown>) => unknown;
  Scale?: new (options?: Record<string, unknown>) => unknown;
};

declare global {
  interface Window {
    AMap?: AMapConstructor;
    _AMapSecurityConfig?: { securityJsCode?: string };
  }
}

const host = ref<HTMLDivElement>();
const state = ref<"loading" | "ready" | "error">("loading");
let map: AMapMap | undefined;
const key = String(import.meta.env.VITE_AMAP_KEY ?? "").trim();
const securityCode = String(import.meta.env.VITE_AMAP_SECURITY_JS_CODE ?? "").trim();
const configured = computed(() => Boolean(key && securityCode));
const zoom = ref(16);
const center = ref({ longitude: 121.38445, latitude: 31.16532 });
const drag = ref<{ x: number; y: number; startX: number; startY: number } | null>(null);

type Tile = { key: string; x: number; y: number; left: number; top: number; src: string };
const worldSize = computed(() => 2 ** zoom.value);
function longitudeToWorld(longitude: number): number { return ((longitude + 180) / 360) * worldSize.value; }
function latitudeToWorld(latitude: number): number {
  const radians = (latitude * Math.PI) / 180;
  return (1 - Math.asinh(Math.tan(radians)) / Math.PI) * worldSize.value / 2;
}
function worldToLongitude(value: number): number { return value / worldSize.value * 360 - 180; }
function worldToLatitude(value: number): number {
  const mercator = Math.PI * (1 - 2 * value / worldSize.value);
  return Math.atan(Math.sinh(mercator)) * 180 / Math.PI;
}
const tiles = computed<Tile[]>(() => {
  const cx = longitudeToWorld(center.value.longitude), cy = latitudeToWorld(center.value.latitude);
  const baseX = Math.floor(cx), baseY = Math.floor(cy), n = worldSize.value;
  const result: Tile[] = [];
  for (let row = -3; row <= 3; row += 1) for (let column = -4; column <= 4; column += 1) {
    const rawX = baseX + column, rawY = baseY + row;
    if (rawY < 0 || rawY >= n) continue;
    const x = ((rawX % n) + n) % n;
    result.push({
      key: `${zoom.value}/${x}/${rawY}`,
      x, y: rawY,
      left: (column - (cx - baseX)) * 256,
      top: (row - (cy - baseY)) * 256,
      src: `https://tile.openstreetmap.org/${zoom.value}/${x}/${rawY}.png`,
    });
  }
  return result;
});
const markers = computed(() => {
  const cx = longitudeToWorld(center.value.longitude), cy = latitudeToWorld(center.value.latitude);
  return [
    { id: "scope", title: "园区仿真范围", longitude: 121.38445, latitude: 31.16532 },
    { id: "p01", title: "P01 备用泵", longitude: 121.38295, latitude: 31.16562 },
    { id: "p02", title: "P02 备用泵", longitude: 121.38414, latitude: 31.16505 },
    { id: "p03", title: "P03 排水泵", longitude: 121.38522, latitude: 31.16452 },
  ].map((marker) => ({
    ...marker,
    style: { left: `calc(50% + ${(longitudeToWorld(marker.longitude) - cx) * 256}px)`, top: `calc(50% + ${(latitudeToWorld(marker.latitude) - cy) * 256}px)` },
  }));
});
function zoomBy(delta: number): void {
  const next = Math.max(13, Math.min(18, zoom.value + delta));
  if (next === zoom.value) return;
  zoom.value = next;
}
function onWheel(event: WheelEvent): void { event.preventDefault(); zoomBy(event.deltaY > 0 ? -1 : 1); }
function onPointerDown(event: PointerEvent): void {
  if (configured.value) return;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  drag.value = { x: event.clientX, y: event.clientY, startX: longitudeToWorld(center.value.longitude), startY: latitudeToWorld(center.value.latitude) };
}
function onPointerMove(event: PointerEvent): void {
  if (!drag.value || configured.value) return;
  const x = drag.value.startX - (event.clientX - drag.value.x) / 256;
  const y = drag.value.startY - (event.clientY - drag.value.y) / 256;
  center.value = { longitude: worldToLongitude(x), latitude: Math.max(-85, Math.min(85, worldToLatitude(y))) };
}
function onPointerUp(): void { drag.value = null; }

function loadAmap(): Promise<AMapConstructor> {
  if (window.AMap) return Promise.resolve(window.AMap);
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-amap-jsapi="2"]');
    if (existing) {
      existing.addEventListener("load", () => window.AMap ? resolve(window.AMap) : reject(new Error("AMap API 未初始化")), { once: true });
      existing.addEventListener("error", () => reject(new Error("AMap API 加载失败")), { once: true });
      return;
    }
    window._AMapSecurityConfig = { securityJsCode: securityCode };
    const script = document.createElement("script");
    script.dataset.amapJsapi = "2";
    script.async = true;
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&plugin=AMap.ControlBar,AMap.Scale`;
    script.onload = () => window.AMap ? resolve(window.AMap) : reject(new Error("AMap API 未初始化"));
    script.onerror = () => reject(new Error("AMap API 网络加载失败"));
    document.head.append(script);
  });
}

async function initialise(): Promise<void> {
  if (!configured.value) { state.value = "ready"; return; }
  if (!host.value) { state.value = "error"; return; }
  try {
    const AMap = await loadAmap();
    await nextTick();
    if (!host.value) return;
    map = new AMap.Map(host.value, {
      viewMode: "3D", center: [121.38445, 31.16532], zoom: 16.6, pitch: 50, rotation: -12,
      mapStyle: "amap://styles/darkblue", showBuildingBlock: true, buildingAnimation: true,
      features: ["bg", "road", "building", "point"],
    });
    if (AMap.ControlBar) map.addControl?.(new AMap.ControlBar({ position: { right: "14px", top: "78px" } }));
    if (AMap.Scale) map.addControl?.(new AMap.Scale({ position: { left: "14px", bottom: "14px" } }));
    const points = [
      { position: [121.38295, 31.16562], title: "P01 备用泵", offset: [-22, -28] },
      { position: [121.38414, 31.16505], title: "P02 备用泵", offset: [-22, -28] },
      { position: [121.38522, 31.16452], title: "P03 排水泵", offset: [-22, -28] },
      { position: [121.38445, 31.16532], title: "园区仿真范围", offset: [-35, -33] },
    ];
    map.add?.(points.map((point) => new AMap.Marker({
      position: point.position, title: point.title, anchor: "bottom-center", offset: point.offset,
      content: `<div class="amap-twin-marker"><i></i><span>${point.title}</span></div>`,
    })));
    state.value = "ready";
  } catch (cause) { console.warn("AMap basemap failed:", cause); state.value = "error"; }
}

onMounted(() => { void initialise(); });
onBeforeUnmount(() => { map?.destroy(); map = undefined; });
</script>

<template>
  <div ref="host" class="amap-basemap" aria-label="漕河泾真实 GIS 底图" @wheel="onWheel" @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerUp">
    <template v-if="!configured">
      <div class="osm-tile-stage" :class="{ 'is-dragging': drag }">
        <img v-for="tile in tiles" :key="tile.key" class="osm-tile" :src="tile.src" :alt="`OpenStreetMap ${tile.x}/${tile.y}`" draggable="false" :style="{ left: `calc(50% + ${tile.left}px)`, top: `calc(50% + ${tile.top}px)` }" />
      </div>
      <div v-for="marker in markers" :key="marker.id" class="osm-twin-mark" :style="marker.style"><i></i><span>{{ marker.title }}</span></div>
      <div class="osm-controls"><button aria-label="放大地图" @click.stop="zoomBy(1)">+</button><button aria-label="缩小地图" @click.stop="zoomBy(-1)">−</button><small>缩放 {{ zoom }}</small></div>
      <a class="osm-attribution" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>
    </template>
    <div v-if="state === 'loading'" class="amap-basemap__notice">正在加载真实 GIS 底图…</div>
    <div v-else-if="state === 'error'" class="amap-basemap__notice amap-basemap__notice--error">真实 GIS 底图暂不可用</div>
    <div class="amap-basemap__badge"><i></i>{{ configured ? '高德地图' : 'OpenStreetMap' }} · 漕河泾园区周边</div>
  </div>
</template>
