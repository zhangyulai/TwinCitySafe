import { Group, Mesh, MeshBasicMaterial, SphereGeometry } from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { disposeObject } from "../utils/dispose";

export type CampusEquipmentType = "camera" | "hydrant" | "sensor";
export interface CampusEquipment { id: string; name: string; type: CampusEquipmentType; position: [number, number, number]; status: "正常" | "预警"; realtime: string; }
const labels: Record<CampusEquipmentType, string> = { camera: "摄像头", hydrant: "消防栓", sensor: "环境传感器" };
const icons: Record<CampusEquipmentType, string> = { camera: "◉", hydrant: "✚", sensor: "⌁" };

/** CSS2D symbols plus small mesh proxies for scene-space picking. */
export class CampusEquipmentManager {
  readonly group = new Group(); readonly items: CampusEquipment[] = [];
  private readonly objects = new Map<string, Group>(); private readonly labels = new Map<string, HTMLDivElement>();
  constructor() {
    this.group.name = "campus-equipment-points"; const positions = this.createPositions();
    positions.slice(0, 20).forEach((position, index) => this.add(this.make("camera", index + 1, position)));
    positions.slice(20, 35).forEach((position, index) => this.add(this.make("hydrant", index + 1, position)));
    positions.slice(35, 65).forEach((position, index) => this.add(this.make("sensor", index + 1, position)));
  }
  private createPositions(): [number, number, number][] {
    // Keep the three inventories contiguous: 20 cameras, 15 hydrants, then
    // 30 environmental sensors. Their locations follow perimeter roads,
    // internal fire lanes, and public-space corridors respectively.
    const cameras: [number, number, number][] = [
      [-91, 4.8, -70], [-72, 4.8, -70], [-50, 4.8, -70], [-24, 4.8, -70], [0, 4.8, -70], [27, 4.8, -70], [53, 4.8, -70], [78, 4.8, -70], [93, 4.8, -70],
      [94, 4.8, -50], [94, 4.8, -25], [94, 4.8, 0], [94, 4.8, 25], [94, 4.8, 50], [-88, 4.8, 68], [-55, 4.8, 68], [-22, 4.8, 68], [12, 4.8, 68], [48, 4.8, 68], [84, 4.8, 68],
    ];
    const hydrants: [number, number, number][] = [
      [-88, .8, -48], [-88, .8, -16], [-88, .8, 17], [-88, .8, 50], [-60, .8, -50], [-35, .8, -29], [-10, .8, -8], [16, .8, 12], [42, .8, 34], [71, .8, 52],
      [-55, .8, 45], [-28, .8, 39], [3, .8, 44], [35, .8, -42], [70, .8, -28],
    ];
    const sensors: [number, number, number][] = [];
    for (const z of [-47, -23, 1, 25, 49])
      for (const x of [-72, -43, -14, 15, 44, 73]) sensors.push([x, 2.5, z]);
    return [...cameras, ...hydrants, ...sensors];
  }
  private make(type: CampusEquipmentType, ordinal: number, position: [number, number, number]): CampusEquipment {
    const status = type === "sensor" && ordinal === 7 ? "预警" : "正常";
    const realtime = type === "camera" ? "在线 · 1080P 视频流" : type === "hydrant" ? "压力 0.62 MPa" : `温度 ${(23 + (ordinal % 5) * .6).toFixed(1)} °C · PM2.5 ${18 + ordinal % 9}`;
    return { id: `${type}-${String(ordinal).padStart(2, "0")}`, name: `${labels[type]} ${String(ordinal).padStart(2, "0")}`, type, position, status, realtime };
  }
  private add(item: CampusEquipment): void {
    const object = new Group(); object.name = `equipment-${item.id}`; object.position.set(...item.position); object.userData.equipment = item;
    const proxy = new Mesh(new SphereGeometry(.7, 8, 6), new MeshBasicMaterial({ color: item.status === "预警" ? 0xf4b264 : 0x55d9ff, transparent: true, opacity: .08, depthWrite: false })); proxy.userData.equipment = item; object.add(proxy);
    const element = document.createElement("div"); element.className = `campus-equipment-icon campus-equipment-icon--${item.type}`; element.dataset.assetId = item.id; element.textContent = icons[item.type]; element.title = item.name;
    const label = new CSS2DObject(element); label.position.y = item.type === "camera" ? .5 : 1.1; object.add(label);
    this.group.add(object); this.items.push(item); this.objects.set(item.id, object); this.labels.set(item.id, element);
  }
  update(time: number): void { for (const item of this.items) { if (item.type !== "sensor") continue; const label = this.labels.get(item.id); if (label) label.style.opacity = item.status === "预警" ? `${.75 + (Math.sin(time * .005) + 1) * .12}` : "1"; } }
  getObjects(): Group[] { return [...this.objects.values()]; }
  get(id: string): CampusEquipment | undefined { return this.items.find((item) => item.id === id); }
  dispose(): void { disposeObject(this.group); this.items.length = 0; this.objects.clear(); this.labels.clear(); }
}
