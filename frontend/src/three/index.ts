import {LeakEffect} from "./effects/LeakEffect";
import type {LeakPreview} from "../types/leak";
import {EmergencyBarrier} from "./effects/EmergencyBarrier";
import { EmergencyRouteOverlay } from "./effects/EmergencyRouteOverlay";
import { RiskHeatmap } from "./effects/RiskHeatmap";
import { CampusEquipmentManager, type CampusEquipment } from "./device/CampusEquipmentManager";
import { PowerLineOverlay } from "./pipeline/PowerLineOverlay";
import {FloodRiskEffect} from "./effects/FloodRiskEffect";
import { Box3, Mesh, Vector3 } from "three";
import type { Group, Material } from "three";
import { SceneManager } from "./core/SceneManager";
import { CameraManager } from "./core/CameraManager";
import { RendererManager } from "./core/RendererManager";
import { LabelManager } from "./core/LabelManager";
import { qualitySettings, type SceneQuality } from "./types/quality";
import { ControlsManager } from "./core/ControlsManager";
import { BuildingManager } from "./building/BuildingManager";
import { PipelineManager } from "./pipeline/PipelineManager";
import { DeviceManager } from "./device/DeviceManager";
import { ParkEnvironment } from "./environment/ParkEnvironment";
import { GeoCampusManager } from "./environment/GeoCampusManager";
import { EffectManager } from "./effects/EffectManager";
import { RainEffect } from "./effects/RainEffect";
import { WaterSurface } from "./environment/WaterSurface";
import type { DeviceState, PipelineState, WeatherState, ParkRealtimeState } from "../types/realtime";
import { InteractionManager } from "./interaction/InteractionManager";
import type { BuildingMetadata, SceneMode, SceneStats } from "./types/scene";

// Keep the focused, original park as the default presentation. The extended
// public OSM context remains an opt-in deployment capability.
const GIS_CONTEXT_ENABLED = import.meta.env.VITE_ENABLE_GIS_CONTEXT === "true";

export type { BuildingMetadata, SceneMode, SceneStats } from "./types/scene";
import type {PipelineNetwork,PipelineType} from "../types/pipeline";
interface SceneCallbacks {
  valveSelect?: (id:string)=>void;
  deviceSelect?: (id: string | null) => void;
  equipmentSelect?: (equipment: CampusEquipment | null) => void;
  pipelineSelect?: (id: string | null) => void;
  select: (metadata: BuildingMetadata | null) => void;
  mode: (mode: SceneMode) => void;
  cruise: (running: boolean) => void;
  stats: (stats: SceneStats) => void;
  basemapSource?: (source: "local" | "online") => void;
  error: (message: string) => void;
}
const cruiseStops = [
  {
    position: new Vector3(20, 45, 115),
    target: new Vector3(0, 3, 12),
    mode: "above" as const,
  },
  {
    position: new Vector3(-74, 49, 22),
    target: new Vector3(-27, 13, -22),
    mode: "above" as const,
  },
  {
    position: new Vector3(69, 42, 30),
    target: new Vector3(25, 10, -22),
    mode: "above" as const,
  },
  {
    position: new Vector3(-68, 42, 82),
    target: new Vector3(-29, 7, 20),
    mode: "above" as const,
  },
  {
    position: new Vector3(52, 55, 72),
    target: new Vector3(0, -4, 10),
    mode: "underground" as const,
  },
];

/** Scene lifecycle and manager coordination only; geometry lives in dedicated managers. */
export class DigitalTwin {
  private selectedDeviceId: string | null = null;
  private sceneManager!: SceneManager;
  private rendererManager!: RendererManager;
  private labelManager!: LabelManager;
  private quality: SceneQuality = "high";
  private cameraManager!: CameraManager;
  private controlsManager!: ControlsManager;
  private buildings!: BuildingManager;
  private pipelines!: PipelineManager;
  private devices!: DeviceManager;
  private equipment!: CampusEquipmentManager;
  private powerLines!: PowerLineOverlay;
  private environment!: ParkEnvironment;
  private geoCampus!: GeoCampusManager;
  private effects!: EffectManager;
  private rain!: RainEffect;
  private water!: WaterSurface;
  private floodEffect!:FloodRiskEffect;
  private barrier!:EmergencyBarrier;
  private emergencyRoutes!: EmergencyRouteOverlay;
  private heatmap!: RiskHeatmap;
  private leakEffect!:LeakEffect;
  private leakScenario:string|null=null;
  private leakConfirmed=false;
  private leakPreview:LeakPreview|undefined;
  private emergencyPreview:string[]=[];
  private realtimeState: ParkRealtimeState | null = null;
  private dataMode:'live'|'replay'='live';
  private replayState:Record<string,unknown>|null=null;
  private replayTime=0;private replayPlaying=false;private replayIncidentId:string|null=null;
  private replayType='';private replayAutoCamera=true;private replayFocus:string|null=null;
  private get animationRunning():boolean{return this.dataMode==='replay'?this.replayPlaying:(this.realtimeState?.running??true);}

  private selectedPipelineId: string | null = null;
  private interaction!: InteractionManager;
  private observer?: ResizeObserver;
  private readonly listeners = new AbortController();
  private frame = 0;
  private disposed = false;
  private started = false;
  private previousTime = 0;
  private sampleTime = 0;
  private frames = 0;
  private stats: SceneStats = { fps: 0, drawCalls: 0, triangles: 0 };
  private mode: SceneMode = "above";
  private selected: Group | null = null;
  private hovered: Group | null = null;
  private cruising = false;
  private cruiseIndex = 0;
  private nextStopAt = 0;

  constructor(
    private readonly container: HTMLElement,
    private readonly callbacks: SceneCallbacks,
  ) {
    try {
      this.sceneManager = new SceneManager();
      this.rendererManager = new RendererManager(container);
      this.cameraManager = new CameraManager();
      this.controlsManager = new ControlsManager(
        this.cameraManager.camera,
        this.rendererManager.renderer.domElement,
      );
      this.cameraManager.bindControls(this.controlsManager.controls);
      this.buildings = new BuildingManager();
      this.environment = new ParkEnvironment();
      this.geoCampus = new GeoCampusManager(
        () => { if (GIS_CONTEXT_ENABLED && this.mode !== "underground") this.environment.group.visible = false; },
        (source) => this.callbacks.basemapSource?.(source),
      );
      this.geoCampus.setContextEnabled(GIS_CONTEXT_ENABLED);
      this.pipelines = new PipelineManager();
      this.devices = new DeviceManager();
      this.equipment = new CampusEquipmentManager();
      this.powerLines = new PowerLineOverlay();
      this.rain = new RainEffect();
      this.water = new WaterSurface();
      this.floodEffect = new FloodRiskEffect();
      this.barrier = new EmergencyBarrier();
      this.emergencyRoutes = new EmergencyRouteOverlay();
      this.heatmap = new RiskHeatmap();
      this.leakEffect=new LeakEffect();
      this.sceneManager.add(
        this.environment.group,
        this.geoCampus.group,
        this.buildings.group,
        this.pipelines.group,
        this.devices.group,
        this.equipment.group,
        this.powerLines.group,
        this.rain.object,
        this.water.mesh,
        this.floodEffect.group,
        this.barrier.group,
        this.emergencyRoutes.group,
        this.heatmap.group,
        this.leakEffect.group,
      );
      this.effects = new EffectManager(
        this.rendererManager.renderer,
        this.sceneManager.scene,
        this.cameraManager.camera,
      );
      this.labelManager = new LabelManager(this.sceneManager.scene);
      this.interaction = new InteractionManager(
        this.rendererManager.renderer.domElement,
        this.cameraManager.camera,
        [...this.buildings.entries, ...this.environment.entries],
        {
          hover: (object) => {
            this.hovered = object;
            this.buildings.setHover(object);
            this.environment.setHover(object);
            this.effects.setHover(object);
          },
          select: (object) => this.select(object),
          valveSelect: (id)=> {this.focusPipelineNode(id);this.callbacks.valveSelect?.(id);},
          pipelineHover: (id)=>this.pipelines.setHover(id),
          pipelineSelect: (id) => this.selectPipeline(id),
          deviceSelect: (id) => this.focusDevice(id, true),
          equipmentSelect: (equipment) => {
            this.clearSelection();
            this.callbacks.equipmentSelect?.(equipment);
          },
          focus: (object) => {
            this.stopCruise();
            this.cameraManager.focusOnObject(object);
          },
        },
      );
      this.interaction.setPipelines(this.pipelines.entries);
      this.interaction.setDevices(this.devices.getObjects());
      this.interaction.setEquipment(this.equipment.getObjects());
      const canvas = this.rendererManager.renderer.domElement;
      canvas.setAttribute("aria-label", "智慧园区三维场景");
      canvas.addEventListener("webglcontextlost", this.onContextLost, {
        signal: this.listeners.signal,
      });
      this.controlsManager.controls.addEventListener(
        "start",
        this.onUserControl,
      );
      document.addEventListener("visibilitychange", this.onVisibilityChange, {
        signal: this.listeners.signal,
      });
      this.observer = new ResizeObserver(this.resize);
      this.observer.observe(container);
      this.applyMode("above");
      this.setQuality(this.quality);
      this.resize();
      this.rendererManager.renderer.info.autoReset = false;
      // Static park: shadows only need recomputation when the visible mode changes.
      this.rendererManager.renderer.shadowMap.autoUpdate = false;
      this.rendererManager.renderer.shadowMap.needsUpdate = true;
      if (import.meta.env.DEV)
        Object.defineProperty(container, "__twinDebug", {
          configurable: true,
          get: () => this.debugSnapshot(),
        });
    } catch (error) {
      this.dispose();
      throw error;
    }
  }

  start(): void {
    if (this.disposed || this.started) return;
    this.started = true;
    this.resume();
  }
  private resume(): void {
    if (this.disposed || !this.started || document.hidden || this.frame) return;
    this.previousTime = this.sampleTime = performance.now();
    this.frames = 0;
    this.frame = requestAnimationFrame(this.tick);
  }
  private readonly tick = (now: number): void => {
    this.frame = 0;
    if (this.disposed || document.hidden) return;
    if (this.cruising && now >= this.nextStopAt) this.nextCruiseStop(now);
    const delta = Math.min(Math.max((now - this.previousTime) / 1000, 0), 0.1);
    this.sceneManager.update(delta);
    if(this.dataMode==='live'||this.replayPlaying)this.rain.update(delta);
    this.devices.update(this.dataMode==='replay'?this.replayTime*1000:now);
    this.equipment.update(now);
    this.water.update(delta,this.animationRunning);
    this.floodEffect.update(delta,this.animationRunning);
    this.leakEffect.update(delta,this.animationRunning);
    this.emergencyRoutes.update(delta);
    this.pipelines.update(delta, this.animationRunning);
    this.cameraManager.update(now);
    this.controlsManager.update();
    const affectedBuildings = this.dataMode === 'replay'
      ? ((this.replayState?.leak as { affectedBuildings?: { buildingId: string }[] } | undefined)?.affectedBuildings ?? []).map(building => building.buildingId)
      : this.realtimeState?.leak?.affectedBuildings.map(building => building.buildingId) ?? [];
    this.labelManager.update(now, this.cameraManager.camera, this.quality, this.selected?.userData.buildingId ?? null, this.hovered?.userData.buildingId ?? null, this.selectedDeviceId, affectedBuildings);
    const renderer = this.rendererManager.renderer;
    renderer.info.reset();
    this.effects.render(delta);
    this.rendererManager.labels.render(
      this.sceneManager.scene,
      this.cameraManager.camera,
    );
    this.previousTime = now;
    this.frames++;
    if (now - this.sampleTime >= 1000) {
      this.stats = {
        fps: Math.round((this.frames * 1000) / (now - this.sampleTime)),
        drawCalls: renderer.info.render.calls,
        triangles: renderer.info.render.triangles,
      };
      this.callbacks.stats(this.stats);
      this.frames = 0;
      this.sampleTime = now;
    }
    this.frame = requestAnimationFrame(this.tick);
  };
  private readonly resize = (): void => {
    if (this.disposed) return;
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight);
    this.rendererManager.resize(width, height);
    this.cameraManager.resize(width, height);
    this.effects.resize(width, height);
  };
  setQuality(quality: SceneQuality): void {
    this.quality = quality;
    const settings = qualitySettings[quality];
    this.rendererManager.setPixelRatioLimit(settings.pixelRatio);
    this.sceneManager.setShadowSize(settings.shadowSize);
    this.rendererManager.renderer.shadowMap.enabled = settings.shadowSize > 0 && this.mode !== "underground";
    this.rendererManager.renderer.shadowMap.needsUpdate = true;
    this.effects.setQuality(settings.postprocessing, settings.pixelRatio);
    this.rain.setParticleLimit(settings.rainCapacity);
    this.labelManager.invalidate();
    this.resize();
  }
  private readonly onVisibilityChange = (): void => {
    if (document.hidden) {
      cancelAnimationFrame(this.frame);
      this.frame = 0;
      this.stopCruise();
      this.cameraManager.cancel();
    } else this.resume();
  };
  private readonly onUserControl = (): void => {
    if(this.dataMode==='replay')this.replayAutoCamera=false;
    this.stopCruise();
    this.cameraManager.cancel();
  };
  private readonly onContextLost = (event: Event): void => {
    event.preventDefault();
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.started = false;
    this.stopCruise();
    this.callbacks.error("三维渲染连接已中断，请重新加载场景。");
  };

  applyRealtimeState(state: ParkRealtimeState): void {
    if (this.disposed || this.dataMode==='replay') return;
    this.realtimeState = state;
    this.sceneManager.updateWeather(state.weather);
    this.rain.updateWeather(state.weather);
    if(state.flood?.scenarioId)this.water.updateFlood(state.flood);
    else this.water.updateLevel(state.environment.b2WaterLevel);
    if(state.flood)this.floodEffect.apply(state.flood);
    this.heatmap.setRiskData([
      { position: [-29, -22], riskLevel: .18 }, { position: [25, -22], riskLevel: .28 }, { position: [-29, 20], riskLevel: .45 },
      { position: [28, 20], riskLevel: .22 }, { position: [0, 10], riskLevel: Math.min(1, Math.max(.15, (state.flood?.riskScore ?? 15) / 100)) },
      { position: [62, -26], riskLevel: .34 }, { position: [-63, 28], riskLevel: .26 },
    ]);
    this.barrier.apply(!!state.flood?.entranceClosed);
    const leak=state.leak;
    this.buildings.setLeakImpact(leak?.scenarioId?leak.affectedBuildings.map(b=>b.buildingId):[]);
    this.pipelines.setLeakRanks(leak?.scenarioId?leak.suspectedSegments.map(s=>s.pipeline_id):[]);
    const suspect=leak?.confirmedAt?leak.suspectedSegments[0]?.pipeline_id:null;
    const entry=this.pipelines.entries.find(e=>e.id===suspect);
    this.leakEffect.apply(suspect??null,entry?.representative.geometry.parameters.path.getPoint(.5),leak?.estimatedLeakFlow??0);
    if(leak?.scenarioId!==this.leakScenario){this.leakScenario=leak?.scenarioId??null;this.leakConfirmed=false;if(this.leakScenario)this.focusLeakRegion();}
    if(leak?.confirmedAt&&!this.leakConfirmed&&entry){this.leakConfirmed=true;this.selectPipeline(entry.id);}

    this.buildings.setFloodRisk(state.flood?.scenarioId ? state.flood.riskScore : null);
    for (const device of state.devices) this.devices.updateDeviceState(device);
    this.pipelines.updateValves(state.valves);
    for (const pipeline of state.pipelines)
      this.pipelines.updatePipelineState(pipeline);
  }

  setReplayContext(incidentId:string|null,type:string,time:number,playing:boolean):void {
    const switched=this.replayIncidentId!==incidentId;this.dataMode='replay';this.realtimeState=null;
    this.replayIncidentId=incidentId;this.replayType=type;this.replayTime=time;this.replayPlaying=playing;
    if(switched){this.replayAutoCamera=true;this.replayFocus=null;this.effects.setPreview([]);this.pipelines.setTrace([]);this.clearSelection();if(type==='FLOOD')this.focusFlood();else this.focusLeakRegion();}
  }
  applyReplayState(state:Record<string,unknown>|null):void {
    if(this.disposed||this.dataMode!=='replay')return;
    this.replayState=state;const data=state??{};
    const f=(data.flood??{}) as Record<string,unknown>,l=(data.leak??{}) as Record<string,unknown>;
    const numeric=(v:unknown):number|null=>typeof v==='number'&&Number.isFinite(v)?v:null;
    const weather=(data.weather??{}) as Partial<WeatherState>,rainfall=numeric(weather.rainfall)??numeric(f.rainfall);
    if(rainfall!==null){const visualWeather={...weather,rainfall,condition:weather.condition??(rainfall>0?'rain':'clear'),windSpeed:numeric(weather.windSpeed)??0} as WeatherState;this.rain.updateWeather(visualWeather);this.sceneManager.updateWeather(visualWeather);this.sceneManager.update(20);}else {this.rain.object.visible=false;this.sceneManager.resetReplayLighting();}
    const water=numeric(f.waterLevel),area=numeric(f.waterArea),effective=numeric(f.effectiveArea)??numeric((data.rendering_basis as Record<string,unknown>|undefined)?.park_effective_area_m2),risk=numeric(f.riskScore);
    this.water.applyReplay(water,area,effective);
    this.floodEffect.applyReplay(this.replayType==='FLOOD'&&water!==null&&area!==null&&effective!==null&&risk!==null?{scenarioId:this.replayIncidentId,waterLevel:water,waterArea:area,effectiveArea:effective,riskScore:risk}:null);
    this.barrier.apply(f.entranceClosed===true);this.barrier.group.visible=this.mode==='underground'&&typeof f.entranceClosed==='boolean';
    this.buildings.setFloodRisk(this.replayType==='FLOOD'?risk:null);
    const suspects=Array.isArray(l.suspectedSegments)?l.suspectedSegments as {pipeline_id:string;score:number}[]:[];
    const affected=Array.isArray(l.affectedBuildings)?l.affectedBuildings as {buildingId:string}[]:[];
    this.buildings.setLeakImpact(affected.map(b=>b.buildingId));this.pipelines.setLeakRanks(suspects.map(p=>p.pipeline_id));
    this.devices.applyReplayStates(Array.isArray(data.devices)?data.devices as Partial<DeviceState>[]:[]);
    this.pipelines.applyReplayStates(Array.isArray(data.pipelines)?data.pipelines as Partial<PipelineState>[]:[],Array.isArray(data.valves)?data.valves as ParkRealtimeState['valves']:[]);
    const leakFlow=numeric(l.estimatedLeakFlow),suspect=suspects[0]?.pipeline_id,entry=this.pipelines.entries.find(e=>e.id===suspect);
    this.leakEffect.apply(leakFlow!==null&&suspect?suspect:null,entry?.representative.geometry.parameters.path.getPoint(.5),leakFlow??0);
  }
  cueReplayCamera(id:string|undefined):void {
    if(this.dataMode!=='replay'||!this.replayAutoCamera||!id||id===this.replayFocus)return;
    if(id==='B2-PARKING'||id==='B2')this.focusFlood();else if(this.devices.getObject(id))this.focusDevice(id);else if(this.pipelines.getObject(id))this.selectPipeline(id);else return;this.replayFocus=id;
  }
  focusLeakRegion():void {this.setMode('underground');this.clearSelection();this.cameraManager.flyTo(new Vector3(45,55,90),new Vector3(0,-5,0));}
  previewLeak(option:LeakPreview|undefined):void {
    this.leakPreview=option;
    const objects=[...(option?.valves??[]).flatMap(id=>{const o=this.pipelines.getObject(id);return o?[o]:[];}),...(option?.affectedBuildings??[]).flatMap(b=>{const o=this.buildings.getById(b.buildingId)?.object;return o?[o]:[];})];
    this.effects.setPreview(objects);this.pipelines.setTrace(option?.isolatedEdges??[],true);
  }
  previewEmergency(targets:string[]):void {
    this.emergencyPreview=[...targets];
    if(targets.length&&this.mode!=='underground')this.focusFlood();
    this.effects.setPreview(targets.flatMap(id=>{const o=this.devices.getObject(id);return o?[o]:[];}));
    this.barrier.setPreview(targets.includes('B2-EAST'));
  }
  focusFlood(mode:SceneMode="underground"):void {this.setMode(mode);this.clearSelection();this.cameraManager.flyTo(new Vector3(45,39,68),new Vector3(0,-4,10));}
  focusDevice(id: string, notify = false): void {
    const object = this.devices.getObject(id);
    if (!object) return;
    this.stopCruise();
    this.clearSelection();
    this.setMode("underground");
    this.selectedDeviceId = id;
    this.buildings.setDeviceFocus(true);
    this.environment.group.visible = false;
    this.cameraManager.focusOnObject(object);
    if (notify) this.callbacks.deviceSelect?.(id);
  }

  loadPipelines(network:PipelineNetwork):void {
    this.pipelines.load(network);this.interaction.setPipelines(this.pipelines.entries);this.interaction.setValves(this.pipelines.valves);
    if(this.dataMode==='replay')this.applyReplayState(this.replayState);else if(this.realtimeState)this.applyRealtimeState(this.realtimeState);
  }
  filterPipelines(types:PipelineType[]):void {this.pipelines.filter(types);}
  tracePipelines(ids:string[],affected=false):void {this.effects.setTraceHighlight(()=>this.pipelines.setTrace(ids,affected),()=>this.pipelines.setTrace([]));}
  clearTraceHighlight():void {this.effects.clearTraceHighlight();}
  focusPipelineNode(id:string):void {
    this.setMode("underground");this.stopCruise();const p=this.pipelines.focusNode(id);if(!p)return;
    this.cameraManager.flyTo(p.clone().add(new Vector3(25,28,32)),p);this.pipelines.setSelected(id);
  }
  selectPipeline(id: string): void {
    if(this.mode!=="underground")this.setMode("underground");
    this.selectedDeviceId = null;
    this.callbacks.deviceSelect?.(null);
    this.stopCruise();
    this.cameraManager.cancel();
    this.selected = this.hovered = null;
    this.buildings.setSelected(null);
    this.buildings.setHover(null);
    this.environment.setSelected(null);
    this.environment.setHover(null);
    this.effects.setSelected(null);
    this.effects.setHover(null);
    this.callbacks.select(null);
    this.selectedPipelineId = id;
    this.pipelines.setSelected(id);
    const object=this.pipelines.getObject(id);if(object){const target=new Box3().setFromObject(object).getCenter(new Vector3());this.cameraManager.flyTo(target.clone().add(new Vector3(40,42,50)),target);}
    this.callbacks.pipelineSelect?.(id);
  }

  private select(object: Group | null): void {
    this.buildings.setDeviceFocus(false);
    this.environment.group.visible = !GIS_CONTEXT_ENABLED || !this.geoCampus.isReady;
    this.selectedDeviceId = null;
    this.callbacks.deviceSelect?.(null);
    this.stopCruise();
    this.selectedPipelineId = null;
    this.pipelines.setSelected(null);
    this.callbacks.pipelineSelect?.(null);
    this.selected = object;
    this.buildings.setSelected(object);
    this.environment.setSelected(object);
    this.effects.setSelected(object);
    const entry = [...this.buildings.entries, ...this.environment.entries].find((item) => item.object === object);
    this.callbacks.select(entry?.metadata ?? null);
    if (object && this.mode === "emergency") {
      this.emergencyRoutes.setIncident(object.getWorldPosition(new Vector3()), entry?.metadata.name ?? "事故建筑");
      this.emergencyRoutes.start();
    }
    if (object) this.cameraManager.focusOnObject(object);
  }
  selectById(id: string): void {
    this.select(this.buildings.getById(id)?.object ?? this.environment.entries.find((entry) => entry.metadata.id === id)?.object ?? null);
  }
  clearSelection(): void {
    this.select(null);
  }
  startEmergencyRouteDemo(speed = 1): void { this.emergencyRoutes.setSpeed(speed); this.setMode("emergency"); this.emergencyRoutes.start(); }
  pauseEmergencyRouteDemo(): void { this.emergencyRoutes.pause(); }
  resetEmergencyRouteDemo(): void { this.emergencyRoutes.reset(); }
  focusSelected(): void {
    if (this.selected) {
      this.stopCruise();
      this.cameraManager.focusOnObject(this.selected);
    }
  }
  resetCamera(): void {
    this.stopCruise();
    this.clearSelection();
    this.cameraManager.resetCamera();
  }
  setMode(mode: SceneMode): void {
    this.stopCruise();
    this.cameraManager.cancel();
    this.applyMode(mode);
  }
  private applyMode(mode: SceneMode): void {
    this.buildings.setDeviceFocus(false);
    this.environment.group.visible = !GIS_CONTEXT_ENABLED || !this.geoCampus.isReady;
    this.selectedDeviceId = null;
    this.callbacks.deviceSelect?.(null);
    this.mode = mode;
    this.buildings.setMode(mode);
    this.environment.setMode(mode);
    this.geoCampus.setMode(mode);
    this.pipelines.setMode(mode);
    this.devices.setMode(mode);
    this.water.setMode(mode);
    this.floodEffect.setMode(mode);
    this.barrier.setMode(mode);
    this.emergencyRoutes.setMode(mode);
    this.leakEffect.setMode(mode);
    this.powerLines.setMode(mode);
    this.heatmap.setMode(mode);
    this.interaction.setPipelinePicking(mode === "underground");
    if (mode !== "underground" && this.selectedPipelineId) {
      this.selectedPipelineId = null;
      this.pipelines.setSelected(null);
      this.callbacks.pipelineSelect?.(null);
    }
    this.interaction.setFilter(
      (entry) => mode !== "underground" || entry.metadata.type === "parking",
    );
    this.hovered = null;
    if (
      this.selected &&
      (!this.selected.visible ||
        (mode === "underground" &&
          this.selected.name !== "underground-parking-b2"))
    ) {
      this.selected = null;
      this.buildings.setSelected(null);
      this.environment.setSelected(null);
      this.effects.setSelected(null);
      this.callbacks.select(null);
    }
    this.rendererManager.renderer.shadowMap.enabled = mode !== "underground" && qualitySettings[this.quality].shadowSize > 0;
    this.rendererManager.renderer.shadowMap.needsUpdate = true;
    if(this.dataMode==='replay')this.applyReplayState(this.replayState);
    this.callbacks.mode(mode);
  }
  toggleCruise(): void {
    if (this.cruising) {
      this.stopCruise();
      this.cameraManager.cancel();
      return;
    }
    this.clearSelection();
    this.hovered = null;
    this.buildings.setHover(null);
    this.environment.setHover(null);
    this.effects.setHover(null);
    this.cruising = true;
    this.cruiseIndex = 0;
    this.callbacks.cruise(true);
    this.nextCruiseStop(performance.now());
  }
  private nextCruiseStop(now: number): void {
    const stop = cruiseStops[this.cruiseIndex % cruiseStops.length]!;
    this.applyMode(stop.mode);
    this.cameraManager.flyTo(stop.position, stop.target, now, 1100);
    this.nextStopAt = now + 2800; // 1.1s flight + 1.7s dwell, no timers to leak.
    this.cruiseIndex++;
  }
  private stopCruise(): void {
    if (!this.cruising) return;
    this.cruising = false;
    this.callbacks.cruise(false);
  }

  /** Read-only development diagnostics for browser smoke tests; absent from production builds. */
  private debugSnapshot() {
    const camera = this.cameraManager.camera;
    const rect = this.container.getBoundingClientRect();
    const point = new Vector3();
    const box = new Box3();
    this.sceneManager.scene.updateMatrixWorld(true);
    const materials=new Set<Material>();
    this.sceneManager.scene.traverse(o=>{if(o instanceof Mesh){for(const m of Array.isArray(o.material)?o.material:[o.material])materials.add(m);}});
    return {
      quality: this.quality,
      profile: {
        pixelRatio: this.rendererManager.renderer.getPixelRatio(),
        shadow: { enabled: this.rendererManager.renderer.shadowMap.enabled, size: this.sceneManager.shadowSize, autoUpdate: this.rendererManager.renderer.shadowMap.autoUpdate },
        postprocessing: this.effects.debug(),
        labels: this.labelManager.debug(),
        rainCapacity: this.rain.capacity,
        rainBudget: qualitySettings[this.quality].rainCapacity,
        contextActive: !this.rendererManager.renderer.getContext().isContextLost(),
      },
      materialCount:materials.size,
      mode: this.mode,
      selectedPipelineId: this.selectedPipelineId,
      selectedDeviceId: this.selectedDeviceId,
      selectedId: this.selected?.userData.buildingId ?? null,
      hoveredId: this.hovered?.userData.buildingId ?? null,
      cameraPosition: camera.position.toArray(),
      target: this.controlsManager.controls.target.toArray(),
      isAnimating: this.cameraManager.isAnimating,
      cruising: this.cruising,
      ...this.stats,
      geometries: this.rendererManager.renderer.info.memory.geometries,
      textures: this.rendererManager.renderer.info.memory.textures,
      objects: this.buildings.entries.map(({ object, metadata }) => {
        box.setFromObject(object).getCenter(point).project(camera);
        let opacity = 1;
        object.traverse((child) => {
          if (child instanceof Mesh && child.name.includes("body")) {
            const material = child.material as Material;
            opacity = material.opacity;
          }
        });
        return {
          id: metadata.id,
          name: metadata.name,
          screen: {
            x: rect.left + ((point.x + 1) * rect.width) / 2,
            y: rect.top + ((1 - point.y) * rect.height) / 2,
          },
          visible: object.visible,
          opacity,
        };
      }),
      dataMode:this.dataMode,replay:{incidentId:this.replayIncidentId,type:this.replayType,time:this.replayTime,playing:this.replayPlaying,autoCamera:this.replayAutoCamera,state:this.replayState,valves:this.pipelines.valves.map(v=>({id:v.name,status:v.userData.replayStatus??'unknown'}))},
      live: {
        weather: this.realtimeState ? { ...this.realtimeState.weather } : null,
        lighting: this.sceneManager.getLightingState(),
        waterLevel: this.water.waterLevel,
        waterY: this.water.mesh.position.y,
        waterScale: this.water.areaScale,
        flood: this.floodEffect.debug(),
        emergency: {barrier:this.barrier.debug(),preview:this.emergencyPreview},
        leak:{affectedBuildings:this.realtimeState?.leak?.affectedBuildings.map(b=>b.buildingId)??[],...this.leakEffect.debug(),preview:this.leakPreview??null,suspects:this.realtimeState?.leak?.suspectedSegments??[]},
        waterVisible: this.water.mesh.visible,
        rainVisible: this.rain.object.visible,
        rainParticleCount: this.rain.count,
        deviceStates: this.devices.getDebugState().map((device) => {
          const object = this.devices.getObject(device.id)!;
          object.getWorldPosition(point);
          point.y += 1;
          point.project(camera);
          return {
            ...device,
            screen: {
              x: rect.left + ((point.x + 1) * rect.width) / 2,
              y: rect.top + ((1 - point.y) * rect.height) / 2,
            },
          };
        }),
        pipelines: this.pipelines.entries.map((entry) => {
          entry.representative.geometry.parameters.path.getPoint(0.5, point);
          entry.representative.localToWorld(point).project(camera);
          return {
            ...entry.state,
            id: entry.id,
            type: entry.type,
            color: "#"+entry.material.color.getHexString(),
            emissiveIntensity: entry.material.emissiveIntensity,
            visible: this.pipelines.group.visible && entry.object.visible,
            screen: {
              x: rect.left + ((point.x + 1) * rect.width) / 2,
              y: rect.top + ((1 - point.y) * rect.height) / 2,
            },
          };
        }),
      },
      devices: this.devices.group.children.map((child) => child.name),
      pipelineCount: this.pipelines.entries.length,
      pipelineMaterials: this.pipelines.entries.length + this.pipelines.valves.length,
      flowOffsets: this.pipelines.entries.map(e=>({id:e.id,offset:e.offset.value,speed:e.speed})),
    };
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.started = false;
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.listeners.abort();
    this.observer?.disconnect();
    this.controlsManager?.controls.removeEventListener(
      "start",
      this.onUserControl,
    );
    this.interaction?.dispose();
    this.cameraManager?.dispose();
    this.controlsManager?.dispose();
    this.effects?.dispose();
    this.buildings?.dispose();
    this.environment?.dispose();
    this.geoCampus?.dispose();
    this.pipelines?.dispose();
    this.devices?.dispose();
    this.equipment?.dispose();
    this.powerLines?.dispose();
    this.rain?.dispose();
    this.water?.dispose();
    this.floodEffect?.dispose();
    this.barrier?.dispose();
    this.emergencyRoutes?.dispose();
    this.heatmap?.dispose();
    this.leakEffect?.dispose();
    this.realtimeState = null;
    this.sceneManager?.dispose();
    this.rendererManager?.dispose();
    this.selected = this.hovered = null;
    this.cruising = false;
    if (import.meta.env.DEV)
      Reflect.deleteProperty(this.container, "__twinDebug");
  }
}
