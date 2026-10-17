import { Object3D, Raycaster, Vector2 } from "three";
import type { Group, Intersection, PerspectiveCamera } from "three";
import type { BuildingEntry } from "../types/scene";
import type { PipelineEntry } from "../pipeline/PipelineManager";
import type { CampusEquipment } from "../device/CampusEquipmentManager";

interface InteractionCallbacks {
  hover: (object: Group | null) => void;
  select: (object: Group | null) => void;
  focus: (object: Group) => void;
  pipelineSelect?: (id: string) => void;
  valveSelect?: (id: string) => void;
  pipelineHover?: (id: string|null) => void;
  deviceSelect?: (id: string) => void;
  equipmentSelect?: (equipment: CampusEquipment | null) => void;
}
type PickResult =
  | { kind: "building"; object: Group }
  | { kind: "pipeline"; id: string }
  | { kind: "valve"; id: string }
  | { kind: "device"; id: string }
  | { kind: "equipment"; equipment: CampusEquipment }
  | null;

export class InteractionManager {
  private readonly raycaster = new Raycaster();
  private readonly pointer = new Vector2();
  private readonly hits: Intersection[] = [];
  private readonly listeners = new AbortController();
  private down: { x: number; y: number; pointerId: number } | null = null;
  private hovered: Group | null = null;
  private dragging = false;
  private eligible: (entry: BuildingEntry) => boolean = () => true;
  private pipelines: PipelineEntry[] = [];
  private pipelinePicking = false;
  private valves: Group[] = [];
  setValves(valves:Group[]):void {this.valves=valves;}
  private devices: Group[] = [];
  private equipment: Group[] = [];
  setDevices(devices: Group[]): void {
    this.devices = devices;
  }
  setEquipment(equipment: Group[]): void { this.equipment = equipment; }

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly camera: PerspectiveCamera,
    private readonly entries: BuildingEntry[],
    private readonly callbacks: InteractionCallbacks,
  ) {
    const options = { signal: this.listeners.signal };
    canvas.addEventListener("pointerdown", this.onDown, options);
    canvas.addEventListener("pointermove", this.onMove, options);
    canvas.addEventListener("pointerup", this.onUp, options);
    canvas.addEventListener("pointercancel", this.onLeave, options);
    canvas.addEventListener("pointerleave", this.onLeave, options);
    canvas.addEventListener("dblclick", this.onDoubleClick, options);
  }

  setPipelines(entries: PipelineEntry[]): void {
    this.pipelines = entries;
  }
  setPipelinePicking(enabled: boolean): void {
    this.pipelinePicking = enabled;
  }
  setFilter(eligible: (entry: BuildingEntry) => boolean): void {
    this.eligible = eligible;
    this.setHover(null);
  }
  private isVisible(object: Object3D): boolean {
    for (let parent: Object3D | null = object; parent; parent = parent.parent)
      if (!parent.visible) return false;
    return true;
  }

  private pick(event: MouseEvent): PickResult {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.set(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      (-(event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.camera.updateMatrixWorld();
    this.raycaster.setFromCamera(this.pointer, this.camera);
    this.hits.length = 0;
    this.raycaster.intersectObjects(this.equipment.filter((item) => this.isVisible(item)), true, this.hits);
    for (const hit of this.hits) {
      for (let object: Object3D | null = hit.object; object; object = object.parent) {
        const equipment = object.userData.equipment as CampusEquipment | undefined;
        if (equipment) return { kind: "equipment", equipment };
      }
    }
    if (this.pipelinePicking) {
      const hits=this.raycaster.intersectObjects(this.valves.filter(v=>this.isVisible(v)),true);
      for(const hit of hits){let o:Object3D|null=hit.object;while(o){if(o.userData.valveId)return {kind:"valve",id:String(o.userData.valveId)};o=o.parent;}}

      this.hits.length = 0;
      this.raycaster.intersectObjects(
        this.devices.filter((d) => this.isVisible(d)),
        true,
        this.hits,
      );
      for (const hit of this.hits) {
        if (!this.isVisible(hit.object)) continue;
        for (
          let object: Object3D | null = hit.object;
          object;
          object = object.parent
        ) {
          if (this.devices.includes(object as Group))
            return { kind: "device", id: String(object.userData.id) };
        }
      }
    }
    // Pipes win only when the ray hits a real visible pipe in underground mode.
    // This prevents the parking floor behind a thin pipe from swallowing its selection.
    if (this.pipelinePicking) {
      this.hits.length = 0;
      this.raycaster.intersectObjects(
        this.pipelines
          .filter((entry) => this.isVisible(entry.object))
          .map((entry) => entry.object),
        true,
        this.hits,
      );
      for (const hit of this.hits) {
        if (!this.isVisible(hit.object)) continue;
        for (
          let object: Object3D | null = hit.object;
          object;
          object = object.parent
        ) {
          const entry = this.pipelines.find(
            (candidate) => candidate.object === object,
          );
          if (entry) return { kind: "pipeline", id: entry.id };
        }
      }
    }
    const candidates = this.entries.filter(
      (entry) => this.isVisible(entry.object) && this.eligible(entry),
    );
    this.hits.length = 0;
    this.raycaster.intersectObjects(
      candidates.map((entry) => entry.object),
      true,
      this.hits,
    );
    for (const hit of this.hits) {
      if (!this.isVisible(hit.object)) continue;
      for (
        let object: Object3D | null = hit.object;
        object;
        object = object.parent
      ) {
        const entry = candidates.find(
          (candidate) => candidate.object === object,
        );
        if (entry) return { kind: "building", object: entry.object };
      }
    }
    return null;
  }

  private setHover(object: Group | null): void {
    this.canvas.style.cursor = object ? "pointer" : "grab";
    if (this.hovered === object) return;
    this.hovered = object;
    this.callbacks.hover(object);
  }
  private updateHover(result: PickResult): void {
    this.callbacks.pipelineHover?.(result?.kind === "pipeline" ? result.id : null);
    this.setHover(result?.kind === "building" ? result.object : null);
    if (result?.kind === "pipeline" || result?.kind === "device" || result?.kind === "valve" || result?.kind === "equipment")
      this.canvas.style.cursor = "pointer";
  }
  private readonly onDown = (event: PointerEvent): void => {
    if (event.button !== 0) return;
    this.down = {
      x: event.clientX,
      y: event.clientY,
      pointerId: event.pointerId,
    };
    this.dragging = false;
  };
  private readonly onMove = (event: PointerEvent): void => {
    if (
      this.down &&
      Math.hypot(event.clientX - this.down.x, event.clientY - this.down.y) > 5
    )
      this.dragging = true;
    if (event.buttons || this.dragging) {
      this.setHover(null);
      this.canvas.style.cursor = "grabbing";
      return;
    }
    this.updateHover(this.pick(event));
  };
  private readonly onUp = (event: PointerEvent): void => {
    const down = this.down;
    this.down = null;
    const result = this.pick(event);
    if (
      down?.pointerId === event.pointerId &&
      !this.dragging &&
      event.button === 0 &&
      Math.hypot(event.clientX - down.x, event.clientY - down.y) <= 5
    ) {
      if (result?.kind === "valve") this.callbacks.valveSelect?.(result.id);
      else if (result?.kind === "device") this.callbacks.deviceSelect?.(result.id);
      else if (result?.kind === "equipment") this.callbacks.equipmentSelect?.(result.equipment);
      else if (result?.kind === "pipeline")
        this.callbacks.pipelineSelect?.(result.id);
      else
        this.callbacks.select(
          result?.kind === "building" ? result.object : null,
        );
    }
    this.dragging = false;
    this.updateHover(result);
  };
  private readonly onLeave = (): void => {
    this.callbacks.pipelineHover?.(null);
    this.down = null;
    this.dragging = false;
    this.setHover(null);
  };
  private readonly onDoubleClick = (event: MouseEvent): void => {
    const result = this.pick(event);
    if (result?.kind === "building") this.callbacks.focus(result.object);
  };
  dispose(): void {
    this.listeners.abort();
    this.down = null;
    this.hits.length = 0;
    this.pipelines = [];
    this.devices = [];
    this.equipment = [];
    this.canvas.style.cursor = "";
  }
}
