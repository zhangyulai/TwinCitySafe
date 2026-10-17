import { Box3, MathUtils, Object3D, PerspectiveCamera, Vector3 } from "three";
import type { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CameraTween } from "../animation/CameraTween";

export class CameraManager {
  readonly camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  private controls: OrbitControls | null = null;
  private readonly tween = new CameraTween();
  private readonly target = new Vector3(0, 5, 0);
  private readonly overviewTarget = new Vector3(0, 5, 0);
  private readonly direction = new Vector3(105, 75, 125).normalize();
  private parkBounds = new Box3(
    new Vector3(-61, -1, -50),
    new Vector3(61, 36, 50),
  );
  private readonly objectBounds = new Box3();
  private readonly desiredPosition = new Vector3();
  private readonly desiredTarget = new Vector3();
  private readonly corner = new Vector3();
  private readonly right = new Vector3();
  private readonly up = new Vector3();
  private overview = true;

  constructor() {
    this.frameOverview();
  }

  setParkBounds(bounds: Box3): void {
    if (bounds.isEmpty()) return;
    this.parkBounds.copy(bounds);
    if (this.overview) this.frameOverview();
  }

  get isAnimating(): boolean {
    return this.tween.isActive;
  }

  bindControls(controls: OrbitControls): void {
    this.controls = controls;
    controls.target.copy(this.target);
    controls.update();
  }

  resize(width: number, height: number): void {
    this.camera.aspect = Math.max(1, width) / Math.max(1, height);
    this.camera.updateProjectionMatrix();
    // A fresh overview always includes the full park, including on narrow layouts.
    if (this.overview) {
      this.tween.cancel();
      this.frameOverview();
    }
  }

  focusOnObject(object: Object3D, time = performance.now()): void {
    object.updateWorldMatrix(true, true);
    this.objectBounds.setFromObject(object);
    if (this.objectBounds.isEmpty()) return;
    this.objectBounds.getCenter(this.desiredTarget);
    const distance = Math.max(
      22,
      this.distanceToFit(this.objectBounds, this.desiredTarget, 1.35),
    );
    this.desiredPosition
      .copy(this.direction)
      .multiplyScalar(distance)
      .add(this.desiredTarget);
    this.flyTo(this.desiredPosition, this.desiredTarget, time);
  }

  resetCamera(time = performance.now()): void {
    const distance = this.distanceToFit(
      this.parkBounds,
      this.overviewTarget,
      1.08,
    );
    this.desiredPosition
      .copy(this.direction)
      .multiplyScalar(distance)
      .add(this.overviewTarget);
    this.flyTo(this.desiredPosition, this.overviewTarget, time);
    this.overview = true;
  }

  flyTo(
    position: Vector3,
    target: Vector3,
    time = performance.now(),
    duration = 1000,
  ): void {
    if (this.controls) {
      // Clear residual orbit damping before a scripted flight takes ownership.
      const damping = this.controls.enableDamping;
      this.controls.enableDamping = false;
      this.controls.update();
      this.controls.enableDamping = damping;
      this.target.copy(this.controls.target);
    }
    this.overview = false;
    this.tween.start(
      this.camera.position,
      this.target,
      position,
      target,
      time,
      duration,
    );
  }

  update(time: number): void {
    if (!this.tween.isActive) return;
    this.tween.update(time, this.camera.position, this.target);
    this.controls?.target.copy(this.target);
    this.camera.lookAt(this.target);
  }

  cancel(): void {
    this.tween.cancel();
    this.overview = false;
  }

  dispose(): void {
    this.cancel();
    this.controls = null;
  }

  private frameOverview(): void {
    const distance = this.distanceToFit(
      this.parkBounds,
      this.overviewTarget,
      1.08,
    );
    this.camera.position
      .copy(this.direction)
      .multiplyScalar(distance)
      .add(this.overviewTarget);
    this.target.copy(this.overviewTarget);
    this.camera.lookAt(this.target);
    this.controls?.target.copy(this.target);
    this.controls?.update();
  }

  /** Fit every box corner in camera space, rather than assuming a fixed aspect. */
  private distanceToFit(bounds: Box3, target: Vector3, margin: number): number {
    const tanVertical = Math.tan(MathUtils.degToRad(this.camera.fov) / 2);
    const tanHorizontal = tanVertical * this.camera.aspect;
    this.right.crossVectors(this.camera.up, this.direction).normalize();
    this.up.crossVectors(this.direction, this.right).normalize();
    let distance = 12;
    for (let index = 0; index < 8; index += 1) {
      this.corner
        .set(
          index & 1 ? bounds.max.x : bounds.min.x,
          index & 2 ? bounds.max.y : bounds.min.y,
          index & 4 ? bounds.max.z : bounds.min.z,
        )
        .sub(target);
      const horizontal = Math.abs(this.corner.dot(this.right));
      const vertical = Math.abs(this.corner.dot(this.up));
      const depth = this.corner.dot(this.direction);
      distance = Math.max(
        distance,
        depth +
          margin * Math.max(horizontal / tanHorizontal, vertical / tanVertical),
      );
    }
    return distance;
  }
}
