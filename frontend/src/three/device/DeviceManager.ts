import {
  BoxGeometry,
  CylinderGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  SphereGeometry,
  RingGeometry,
  MeshBasicMaterial,
  DoubleSide,
} from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import type { SceneMode } from "../types/scene";
import {
  deviceStatusLabels,
  type DeviceState,
  type DeviceStatus,
} from "../../types/realtime";
import { disposeObject } from "../utils/dispose";

const statusColors: Record<DeviceStatus, number> = {
  standby: 0x4a9eb6,
  running: 0x52b890,
  warning: 0xd59547,
  offline: 0x687887,
};
interface DeviceVisual {
  object: Group;
  material: MeshStandardMaterial;
  indicator: MeshStandardMaterial;
  label: HTMLDivElement;
  state: DeviceState | null;
  ring: Mesh<RingGeometry, MeshBasicMaterial>;
}

/** Materials are private per device; changing P03 cannot recolor the other pumps. */
export class DeviceManager {
  readonly group = new Group();
  private readonly devices = new Map<string, DeviceVisual>();
  constructor() {
    this.group.name = "underground-pump-devices";
    const baseGeometry = new BoxGeometry(2.9, 0.3, 2.3);
    const pumpGeometry = new CylinderGeometry(0.58, 0.68, 1.5, 12);
    const motorGeometry = new CylinderGeometry(0.37, 0.37, 0.48, 10);
    const indicatorGeometry = new SphereGeometry(0.17, 8, 6);
    const ringGeometry = new RingGeometry(1.5, 1.68, 32);
    const baseMaterial = new MeshStandardMaterial({
      color: 0x29495d,
      roughness: 0.7,
    });
    const motorMaterial = new MeshStandardMaterial({
      color: 0x7ea6b4,
      metalness: 0.5,
      roughness: 0.4,
    });
    ["P01", "P02", "P03"].forEach((id, index) => {
      const device = new Group();
      device.name = `device-${id.toLowerCase()}`;
      device.position.set((index - 1) * 10, -5.45, 23);
      device.userData = {
        id,
        name: `${id} 排水泵`,
        type: "drainage-pump",
        buildingId: "B2-PARKING",
        demonstration: true,
      };
      const pumpMaterial = new MeshStandardMaterial({
        color: statusColors.standby,
        metalness: 0.4,
        roughness: 0.4,
      });
      const indicatorMaterial = new MeshStandardMaterial({
        color: statusColors.standby,
        emissive: statusColors.standby,
        emissiveIntensity: 0.15,
      });
      const base = new Mesh(baseGeometry, baseMaterial);
      const pump = new Mesh(pumpGeometry, pumpMaterial);
      pump.name = `device-${id.toLowerCase()}-body`;
      pump.position.y = 0.9;
      const motor = new Mesh(motorGeometry, motorMaterial);
      motor.position.y = 1.85;
      const indicator = new Mesh(indicatorGeometry, indicatorMaterial);
      indicator.position.set(0, 2.17, 0);
      const ring = new Mesh(
        ringGeometry,
        new MeshBasicMaterial({
          color: 0xd59547,
          transparent: true,
          opacity: 0.5,
          side: DoubleSide,
          depthWrite: false,
        }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.22;
      ring.visible = false;
      ring.name = `${id}-anomaly-ring`;
      ring.raycast = () => {};
      device.add(base, pump, motor, indicator, ring);
      const element = document.createElement("div");
      element.className = "twin-label twin-label--device";
      element.style.pointerEvents = "none";
      element.dataset.deviceId = id;
      element.textContent = `${id} · 等待数据`;
      const label = new CSS2DObject(element);
      label.position.set(0, 3, 0);
      device.add(label);
      this.group.add(device);
      this.devices.set(id, {
        object: device,
        material: pumpMaterial,
        indicator: indicatorMaterial,
        label: element,
        state: null,
        ring,
      });
    });
    this.setMode("above");
  }

  updateDeviceState(state: DeviceState): void {
    const device = this.devices.get(state.id);
    if (!device) return;
    device.state = { ...state };
    device.object.userData.status = state.status;
    const level = state.analysis?.level;
    const operating = state.status === "running" || state.status === "warning";
    const color =
      operating && level === "critical"
        ? 0xd96767
        : state.status === "warning"
          ? statusColors.warning
          : operating && level === "attention"
            ? 0xd7c163
            : statusColors[state.status];
    device.ring.visible =
      operating && ((state.startupProgress??1)<1 ||
      (level === "warning" ||
        level === "critical" ||
        state.status === "warning"));
    device.ring.material.color.setHex(color);
    const glow =
      state.status === "running"
        ? 0.24
        : state.status === "warning"
          ? 0.18
          : state.status === "standby"
            ? 0.05
            : 0;
    device.material.color.setHex(color);
    device.material.emissive.setHex(color);
    device.material.emissiveIntensity = glow;
    device.indicator.color.setHex(color);
    device.indicator.emissive.setHex(color);
    device.indicator.emissiveIntensity =
      state.status === "offline" ? 0 : glow + 0.35;
    device.label.textContent = `${state.id} · ${operating&&(state.startupProgress??1)<1?`启动中 ${Math.round((state.startupProgress??0)*100)}%`:deviceStatusLabels[state.status]}`;
    device.label.dataset.status = state.status;
    device.label.style.color = `#${device.material.color.getHexString()}`;
    device.label.style.borderColor = `#${device.material.color.getHexString()}`;
  }

  applyReplayStates(states: Partial<DeviceState>[] = []): void {
    for(const [id,visual] of this.devices){const state=states.find(s=>s.id===id);
      if(state?.status && Object.hasOwn(statusColors,state.status)){this.updateDeviceState(state as DeviceState);continue;}
      visual.state=null;visual.object.userData.status="unknown";visual.ring.visible=false;
      visual.material.color.setHex(0x687887);visual.material.emissive.setHex(0);visual.indicator.color.setHex(0x687887);visual.indicator.emissive.setHex(0);
      visual.label.textContent=`${id} · 历史未记录`;visual.label.dataset.status="unknown";visual.label.style.color="#8997a2";visual.label.style.borderColor="#687887";
    }
  }
  getObject(id: string): Group | undefined {
    return this.devices.get(id)?.object;
  }
  getObjects(): Group[] {
    return [...this.devices.values()].map((d) => d.object);
  }
  update(time: number): void {
    for (const device of this.devices.values())
      if (device.ring.visible) {
        const pulse = (Math.sin(time * 0.004) + 1) / 2;
        device.ring.material.opacity = 0.25 + pulse * 0.4;
        device.ring.scale.setScalar(1 + pulse * 0.2);
        device.material.emissiveIntensity = 0.16 + pulse * 0.2;
      }
  }
  getDebugState() {
    return [...this.devices.entries()].map(([id, device]) => ({
      ...device.state,
      id,
      color: `#${device.material.color.getHexString()}`,
      emissive: `#${device.material.emissive.getHexString()}`,
      emissiveIntensity: device.material.emissiveIntensity,
      visible: this.group.visible && device.object.visible,
      pulseVisible: device.ring.visible,
    }));
  }
  setMode(mode: SceneMode): void {
    this.group.visible = mode === "underground";
  }
  dispose(): void {
    disposeObject(this.group);
    this.devices.clear();
  }
}
