import type { PerspectiveCamera } from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export class ControlsManager {
  readonly controls: OrbitControls;

  constructor(camera: PerspectiveCamera, element: HTMLElement) {
    this.controls = new OrbitControls(camera, element);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.075;
    this.controls.minDistance = 12;
    this.controls.maxDistance = 300;
    this.controls.minPolarAngle = 0.12;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.055;
    this.controls.rotateSpeed = 0.65;
    this.controls.zoomSpeed = 0.85;
    this.controls.panSpeed = 0.75;
    this.controls.screenSpacePanning = false;
  }

  update(): void {
    this.controls.update();
  }
  dispose(): void {
    this.controls.dispose();
  }
}
