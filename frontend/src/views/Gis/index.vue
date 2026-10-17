<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  BillboardGraphics, BoundingSphere, Cartesian2, Cartesian3, Color, ColorMaterialProperty, ConstantProperty, Entity, GeoJsonDataSource, ImageMaterialProperty,
  HeadingPitchRange, HeightReference, HorizontalOrigin, JulianDate, LabelGraphics, LabelStyle, Math as CesiumMath, OpenStreetMapImageryProvider,
  ScreenSpaceEventHandler, ScreenSpaceEventType, VerticalOrigin, Viewer, WallGraphics,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { useRealtimeStore } from '../../store/useRealtimeStore';
import './gis.css';

type LayerId = 'buildings' | 'roads' | 'water' | 'amenities' | 'assets';
type Action = { label: string; path: string };
type Picked = { title: string; type: string; source: string; note: string; action?: Action } | null;
type PositionedEvent = { position: Cartesian2 };
const host = ref<HTMLElement | null>(null);
const viewerReady = ref(false), baseMapReady = ref(true), selected = ref<Picked>(null);
const router = useRouter(), realtime = useRealtimeStore();
const layers = ref<Record<LayerId, boolean>>({ buildings: true, roads: true, water: true, amenities: false, assets: true });
const layerLabels: Array<{ id: LayerId; label: string; note: string }> = [
  { id: 'buildings', label: '参数化园区建筑', note: '真实轮廓 · 程序立面' },
  { id: 'roads', label: '道路与步行系统', note: '公开道路中心线' },
  { id: 'water', label: '水体', note: '公开水面要素' },
  { id: 'amenities', label: '公共设施', note: '公开设施面' },
  { id: 'assets', label: '仿真资产映射', note: '非测绘设备与管网' },
];
let viewer: Viewer | undefined;
let vectorSource: GeoJsonDataSource | undefined;
let interaction: ScreenSpaceEventHandler | undefined;
const assetEntities: Record<string, ReturnType<Viewer['entities']['add']>> = {};
const facadeCache = new Map<string, HTMLCanvasElement>();
const parkBounds = new BoundingSphere(Cartesian3.fromDegrees(121.3843, 31.1656, 0), 760);

type BuildingProfile = { floors: number; height: number; family: number; source: string; note: string };
const knownBuildingProfiles: Record<string, Pick<BuildingProfile, 'floors' | 'source' | 'note'>> = {
  // OSM's 20 号楼 record has an explicit 28-floor / 120m tag.  It is kept as
  // map-source data instead of being replaced by the generic office estimate.
  '1156899170': { floors: 28, source: 'OpenStreetMap 明确高度属性', note: '公开地图记录为 28 层、120 m。' },
};

const risk = computed(() => realtime.state?.flood?.scenarioId ? realtime.state.flood.riskScore : null);
const p03 = computed(() => realtime.getDeviceById('P03'));
const statusText = computed(() => risk.value === null ? '日常监测' : `内涝场景 · 风险 ${risk.value.toFixed(1)}`);
const assetColor = computed(() => risk.value !== null && risk.value >= 60 ? Color.fromCssColorString('#ff775e') : p03.value?.status === 'warning' ? Color.fromCssColorString('#ffbf5d') : Color.fromCssColorString('#39e3c2'));

function property(entity: Entity, name: string): unknown {
  return entity.properties?.[name]?.getValue?.();
}
function layerOf(entity: Entity): string | undefined {
  const value = property(entity, 'layer');
  return typeof value === 'string' ? value : undefined;
}
function stableNumber(value: string): number {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) result = Math.imul(result ^ value.charCodeAt(index), 16777619);
  return Math.abs(result >>> 0);
}
function buildingProfile(entity: Entity): BuildingProfile {
  const osmId = String(property(entity, 'osmId') ?? entity.id ?? 'building');
  const explicitHeight = Number(property(entity, 'height') ?? 0);
  const explicitLevels = Number(property(entity, 'levels') ?? 0);
  const known = knownBuildingProfiles[osmId];
  const floors = Number.isFinite(explicitLevels) && explicitLevels > 0 ? explicitLevels : known?.floors ?? 5 + (stableNumber(osmId) % 9);
  const height = Number.isFinite(explicitHeight) && explicitHeight > 0 ? explicitHeight : Math.round(floors * 3.6 * 10) / 10;
  const source = Number.isFinite(explicitHeight) && explicitHeight > 0 || Number.isFinite(explicitLevels) && explicitLevels > 0
    ? 'OpenStreetMap 公开建筑属性'
    : known?.source ?? '公开园区常见层数范围参数化';
  const note = Number.isFinite(explicitHeight) && explicitHeight > 0
    ? `公开属性高度 ${height} m${explicitLevels > 0 ? `，${explicitLevels} 层` : ''}。`
    : known?.note ?? `未公开具体层数；按园区常见 5–13 层研发办公建筑范围生成 ${floors} 层、${height} m 的近似体量。`;
  return { floors, height, family: stableNumber(osmId) % 4, source, note };
}
function facadeTexture(profile: BuildingProfile): HTMLCanvasElement {
  const key = `${profile.family}-${profile.floors}`;
  const cached = facadeCache.get(key);
  if (cached) return cached;
  const canvas = document.createElement('canvas');
  canvas.width = 320; canvas.height = 720;
  const context = canvas.getContext('2d')!;
  const palettes = [
    { wall: '#163e59', frame: '#266a87', glass: '#76d9ef', glow: '#b9f6ff' },
    { wall: '#234255', frame: '#54788b', glass: '#8cd8df', glow: '#d9fbff' },
    { wall: '#293b4c', frame: '#52687b', glass: '#75c4df', glow: '#d4f5ff' },
    { wall: '#19485a', frame: '#39778b', glass: '#76e0ca', glow: '#cefff5' },
  ][profile.family];
  context.fillStyle = palettes.wall; context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = '#0d2434'; context.fillRect(0, 0, canvas.width, 18);
  context.fillStyle = palettes.frame;
  const floors = Math.max(4, Math.min(18, profile.floors));
  const floorHeight = (canvas.height - 44) / floors;
  for (let floor = 0; floor < floors; floor += 1) {
    const top = 24 + floor * floorHeight;
    context.fillStyle = floor % 2 ? '#102c3e' : '#15364a'; context.fillRect(0, top, canvas.width, floorHeight - 4);
    for (let column = 0; column < 6; column += 1) {
      const x = 12 + column * 51;
      context.fillStyle = (floor + column + profile.family) % 5 === 0 ? palettes.glow : palettes.glass;
      context.fillRect(x, top + 7, 35, Math.max(7, floorHeight - 15));
      context.strokeStyle = palettes.frame; context.lineWidth = 2; context.strokeRect(x, top + 7, 35, Math.max(7, floorHeight - 15));
    }
    context.fillStyle = palettes.frame; context.fillRect(0, top + floorHeight - 4, canvas.width, 4);
  }
  context.fillStyle = '#0b202f'; context.fillRect(0, canvas.height - 12, canvas.width, 12);
  facadeCache.set(key, canvas); return canvas;
}
function roofColor(profile: BuildingProfile): Color {
  const colors = ['#176783', '#285f72', '#334f62', '#176b72'];
  return Color.fromCssColorString(colors[profile.family] ?? colors[0]).withAlpha(.96);
}
function styleVectorFeatures(): void {
  if (!vectorSource) return;
  for (const entity of vectorSource.entities.values) {
    const layer = layerOf(entity);
    entity.show = !!layer && layers.value[layer as LayerId] !== false;
    if (entity.polygon) {
      const building = layer === 'buildings';
      const water = layer === 'water';
      const amenity = layer === 'amenities';
      const profile = building ? buildingProfile(entity) : undefined;
      entity.polygon.material = building && profile
        ? new ColorMaterialProperty(roofColor(profile))
        : new ColorMaterialProperty(water ? Color.fromCssColorString('#18b8e8').withAlpha(.6) : amenity ? Color.fromCssColorString('#3fbd80').withAlpha(.44) : Color.fromCssColorString('#2b7899').withAlpha(.35));
      entity.polygon.outline = new ConstantProperty(true);
      entity.polygon.outlineColor = new ConstantProperty(building ? Color.fromCssColorString('#55d9ff').withAlpha(.9) : Color.fromCssColorString('#4edec0').withAlpha(.75));
      if (building) {
        const height = profile!.height;
        entity.polygon.height = new ConstantProperty(height);
        entity.polygon.extrudedHeight = undefined;
        const hierarchy = entity.polygon.hierarchy?.getValue(JulianDate.now());
        if (hierarchy?.positions?.length) {
          entity.wall = new WallGraphics({
            positions: new ConstantProperty(hierarchy.positions),
            minimumHeights: new ConstantProperty(hierarchy.positions.map(() => 0)),
            maximumHeights: new ConstantProperty(hierarchy.positions.map(() => height)),
            material: new ImageMaterialProperty({ image: facadeTexture(profile!), repeat: new Cartesian2(1, Math.max(1, profile!.floors / 4)), transparent: false }),
          });
        }
      }
    }
    if (entity.polyline) {
      entity.polyline.width = new ConstantProperty(layer === 'roads' ? 2.2 : 2.8);
      entity.polyline.material = new ColorMaterialProperty(layer === 'roads' ? Color.fromCssColorString('#7dbbdf').withAlpha(.82) : Color.fromCssColorString('#49d9e8').withAlpha(.9));
    }
  }
}
function addAsset(id: string, name: string, position: [number, number], note: string, action?: Action): void {
  if (!viewer) return;
  const entity = viewer.entities.add({
    id, position: Cartesian3.fromDegrees(position[0], position[1], 18),
    billboard: new BillboardGraphics({ image: makeMarker(), width: 22, height: 22, verticalOrigin: VerticalOrigin.BOTTOM, heightReference: HeightReference.NONE }),
    label: new LabelGraphics({ text: name, font: '12px "Microsoft YaHei", sans-serif', fillColor: Color.fromCssColorString('#e5f9ff'), outlineColor: Color.fromCssColorString('#042037'), outlineWidth: 3, style: LabelStyle.FILL_AND_OUTLINE, horizontalOrigin: HorizontalOrigin.LEFT, verticalOrigin: VerticalOrigin.CENTER, pixelOffset: new Cartesian3(16, -9, 0), showBackground: true, backgroundColor: Color.fromCssColorString('#06223bdd'), backgroundPadding: new Cartesian3(7, 4, 0) }),
    properties: { layer: 'assets', name, note, actionPath: action?.path ?? '', actionLabel: action?.label ?? '' },
  });
  assetEntities[id] = entity;
}
function makeMarker(): HTMLCanvasElement {
  const canvas = document.createElement('canvas'); canvas.width = 48; canvas.height = 48;
  const context = canvas.getContext('2d')!;
  context.beginPath(); context.arc(24, 24, 14, 0, Math.PI * 2); context.fillStyle = '#35e5c0'; context.shadowBlur = 13; context.shadowColor = '#2cdfff'; context.fill();
  context.beginPath(); context.arc(24, 24, 6, 0, Math.PI * 2); context.fillStyle = '#e9ffff'; context.fill(); return canvas;
}
function addSimulationAssets(): void {
  addAsset('P01', 'P01 备用泵', [121.383706, 31.164905], '软件仿真资产映射至 1 号楼附近；位置仅用于演示空间联动。', { label: '查看设备运维', path: '/operation?device=P01' });
  addAsset('P02', 'P02 备用泵', [121.386006, 31.165624], '软件仿真资产映射至 6 号楼附近；不代表真实设备位置。', { label: '查看设备运维', path: '/operation?device=P02' });
  addAsset('P03', 'P03 排水泵', [121.387827, 31.165755], '软件仿真资产映射至 9 号楼附近；设备状态来自本系统软件仿真。', { label: '查看设备运维', path: '/operation?device=P03' });
  addAsset('B2-PARKING', 'B2 内涝推演区', [121.389155, 31.166506], '内涝水量平衡、风险预测与应急推演的局部数字孪生入口。', { label: '查看内涝推演', path: '/simulation' });
}
function applyAssetStyle(): void {
  for (const entity of Object.values(assetEntities)) {
    entity.show = layers.value.assets;
    if (entity.billboard) entity.billboard.color = new ConstantProperty(assetColor.value);
  }
}
function selectedEntity(entity: Entity): void {
  const buildingProfileInfo = layerOf(entity) === 'buildings' ? buildingProfile(entity) : undefined;
  const source = entity.id === 'P01' || entity.id === 'P02' || entity.id === 'P03' || entity.id === 'B2-PARKING'
    ? '本项目软件仿真资产'
    : buildingProfileInfo ? `${buildingProfileInfo.source} + 程序立面` : 'OpenStreetMap 公开基础图层';
  const name = String(property(entity, 'name') ?? entity.id ?? '园区要素');
  const layer = String(property(entity, 'layer') ?? '要素');
  const actionPath = String(property(entity, 'actionPath') ?? '');
  const actionLabel = String(property(entity, 'actionLabel') ?? '');
  const note = String(property(entity, 'note') ?? (layer === 'buildings'
    ? `真实 GIS 轮廓；${buildingProfileInfo?.note ?? '建筑高度和立面为程序生成近似，不是实景摄影或 BIM。'}`
    : layer === 'roads' ? '公开道路中心线，仅用于空间参照。' : '公开 GIS 基础要素。'));
  selected.value = { title: name, type: layer === 'assets' ? '仿真资产映射' : layer, source, note, action: actionPath ? { path: actionPath, label: actionLabel } : undefined };
}
function onPick(event: PositionedEvent): void {
  const picked = viewer?.scene.pick(event.position) as { id?: unknown } | undefined;
  if (picked?.id instanceof Entity) selectedEntity(picked.id); else selected.value = null;
}
async function createMap(): Promise<void> {
  await nextTick(); if (!host.value) return;
  viewer = new Viewer(host.value, { animation: false, baseLayerPicker: false, fullscreenButton: false, geocoder: false, homeButton: false, infoBox: false, navigationHelpButton: false, sceneModePicker: false, selectionIndicator: false, timeline: false, terrain: undefined, baseLayer: false });
  viewer.scene.backgroundColor = Color.fromCssColorString('#020c18');
  viewer.scene.globe.baseColor = Color.fromCssColorString('#071b2d');
  if (viewer.scene.skyBox) viewer.scene.skyBox.show = false;
  if (viewer.scene.sun) viewer.scene.sun.show = false;
  if (viewer.scene.moon) viewer.scene.moon.show = false;
  try { viewer.imageryLayers.addImageryProvider(new OpenStreetMapImageryProvider({ url: 'https://tile.openstreetmap.org/' })); } catch { baseMapReady.value = false; }
  vectorSource = await GeoJsonDataSource.load('/gis/caohejing-keji-oasis.geojson');
  await viewer.dataSources.add(vectorSource); styleVectorFeatures(); addSimulationAssets(); applyAssetStyle();
  interaction = new ScreenSpaceEventHandler(viewer.scene.canvas); interaction.setInputAction(onPick, ScreenSpaceEventType.LEFT_CLICK);
  viewer.camera.flyToBoundingSphere(parkBounds, { duration: 0, offset: new HeadingPitchRange(CesiumMath.toRadians(8), CesiumMath.toRadians(-58), 2350) });
  viewerReady.value = true;
}
function flyToPark(): void { viewer?.camera.flyToBoundingSphere(parkBounds, { duration: .8, offset: new HeadingPitchRange(CesiumMath.toRadians(8), CesiumMath.toRadians(-58), 2350) }); }
function flyToAssets(): void { viewer?.camera.flyTo({ destination: Cartesian3.fromDegrees(121.3868, 31.1656, 1150), orientation: { heading: CesiumMath.toRadians(12), pitch: CesiumMath.toRadians(-69), roll: 0 }, duration: .8 }); }
function openAction(): void { if (selected.value?.action) void router.push(selected.value.action.path); }
watch(layers, () => { styleVectorFeatures(); applyAssetStyle(); }, { deep: true });
watch(assetColor, applyAssetStyle);
onMounted(() => void createMap());
onBeforeUnmount(() => { interaction?.destroy(); interaction = undefined; viewer?.destroy(); viewer = undefined; });
</script>

<template>
  <section class="gis-page" data-testid="gis-page">
    <header class="section-heading gis-heading">
      <div><span class="eyebrow">CAOHEJING TECH OASIS · GIS TWIN</span><h2>漕河泾科技绿洲 GIS 总览</h2><p>真实园区轮廓、公开建筑参数与程序化立面叠加展示</p></div>
      <div class="gis-status"><i></i><b>{{ statusText }}</b><small>EPSG:4326 / WGS 84</small></div>
    </header>
    <div class="gis-layout">
      <aside class="gis-panel gis-layers"><div class="gis-panel-title"><h3>空间图层</h3><span>公开 GIS</span></div>
        <label v-for="item in layerLabels" :key="item.id"><input v-model="layers[item.id]" type="checkbox"><span><b>{{ item.label }}</b><small>{{ item.note }}</small></span><i></i></label>
        <div class="gis-actions"><button @click="flyToPark">定位园区全貌</button><button @click="flyToAssets">定位仿真资产</button></div>
        <p class="gis-mini-note">底图要素来自 OpenStreetMap；点击对象可查看来源与属性说明。</p>
      </aside>
      <main class="gis-map-shell"><div ref="host" class="gis-map" :class="{ ready: viewerReady }" aria-label="漕河泾科技绿洲三维 GIS 地图"></div><div class="gis-map-title"><b>漕河泾科技绿洲 · 一至六期</b><span>真实建筑轮廓 / 参数化体量与立面</span></div><div class="gis-map-legend"><span class="building"></span>参数化建筑 <span class="road"></span>道路 <span class="water"></span>水体 <span class="asset"></span>仿真资产</div><div v-if="!baseMapReady" class="gis-tile-notice">在线底图不可用，正在使用本地公开矢量图层。</div></main>
      <aside class="gis-panel gis-details"><div class="gis-panel-title"><h3>要素详情</h3><span>{{ selected ? '已选中' : '点击地图' }}</span></div>
        <template v-if="selected"><h4>{{ selected.title }}</h4><dl><div><dt>类型</dt><dd>{{ selected.type }}</dd></div><div><dt>数据来源</dt><dd>{{ selected.source }}</dd></div></dl><p>{{ selected.note }}</p><button v-if="selected.action" @click="openAction">{{ selected.action.label }} →</button></template>
        <div v-else class="gis-empty"><i>⌖</i><b>选择园区要素</b><p>点击建筑、道路或仿真资产，可查看其空间数据来源与业务关联。</p></div>
        <div class="gis-data-card"><b>模型说明</b><p>建筑轮廓、道路和水体来自公开 GIS。已公开层数/高度直接采用；其余建筑按园区常见 5–13 层范围生成体量和程序立面。它们不是实景摄影、测绘或 BIM。</p><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap · ODbL 1.0 ↗</a></div>
      </aside>
    </div>
  </section>
</template>
