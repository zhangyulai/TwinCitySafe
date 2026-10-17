import { Vector3 } from "three";
import type { Camera, Object3D, Scene } from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { qualitySettings, type SceneQuality } from "../types/quality";

/** Cull secondary DOM labels without altering source data or Three object visibility. */
export class LabelManager {
  private readonly labels: CSS2DObject[] = [];
  private readonly point = new Vector3();
  private lastUpdate = -Infinity;
  private stats = { total: 0, visible: 0, critical: 0 };
  constructor(scene: Scene) {
    scene.traverse(object => { if (object instanceof CSS2DObject) this.labels.push(object); });
  }
  update(now: number, camera: Camera, quality: SceneQuality, selectedBuilding: string | null, hoveredBuilding: string | null, selectedDevice: string | null, affectedBuildings: string[]): void {
    if (now - this.lastUpdate < 250) return;
    this.lastUpdate = now;
    const settings = qualitySettings[quality];
    const secondary: { label: CSS2DObject; distance: number }[] = [];
    let visible = 0, criticalCount = 0, total = 0;
    for (const label of this.labels) {
      const element = label.element;
      let active = true;
      for (let parent: Object3D | null = label; parent; parent = parent.parent) if (!parent.visible) { active = false; break; }
      if (!active) continue;
      total++;
      const building = element.dataset.buildingId, device = element.dataset.deviceId;
      // Four above-ground buildings are core orientation landmarks.  They must
      // remain named on the default medium-quality overview instead of being
      // removed by the secondary-label budget.
      const coreBuilding = ["A-OFFICE", "B-RESEARCH", "C-LAB", "D-SERVICE"].includes(building ?? "");
      const critical = element.classList.contains("flood-scene-label") || element.classList.contains("pipeline-scene-label") || !!element.dataset.entranceId
        || coreBuilding
        || !!building && (building === selectedBuilding || building === hoveredBuilding || affectedBuildings.includes(building))
        || !!device && (device === selectedDevice || ["warning", "offline", "running"].includes(element.dataset.status ?? ""));
      element.style.visibility = "";
      if (critical || quality === "high") { visible++; if (critical) criticalCount++; continue; }
      label.getWorldPosition(this.point);
      secondary.push({ label, distance: this.point.distanceTo(camera.position) });
    }
    secondary.sort((a, b) => a.distance - b.distance);
    secondary.forEach(({ label, distance }, index) => {
      const show = index < settings.labels && (distance <= settings.labelDistance || index === 0);
      label.element.style.visibility = show ? "" : "hidden";
      if (show) visible++;
    });
    this.stats = { total, visible, critical: criticalCount };
  }
  invalidate(): void { this.lastUpdate = -Infinity; }
  debug() { return this.stats; }
}
