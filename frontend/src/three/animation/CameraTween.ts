import { Vector3 } from "three";

/** Interpolates eye and orbit target together; the caller owns the animation loop. */
export class CameraTween {
  private readonly fromPosition = new Vector3();
  private readonly fromTarget = new Vector3();
  private readonly toPosition = new Vector3();
  private readonly toTarget = new Vector3();
  private startTime = 0;
  private duration = 1000;
  private active = false;

  get isActive(): boolean {
    return this.active;
  }

  start(
    fromPosition: Vector3,
    fromTarget: Vector3,
    toPosition: Vector3,
    toTarget: Vector3,
    time: number,
    duration = 1000,
  ): void {
    this.fromPosition.copy(fromPosition);
    this.fromTarget.copy(fromTarget);
    this.toPosition.copy(toPosition);
    this.toTarget.copy(toTarget);
    this.startTime = time;
    this.duration = Math.max(0, duration);
    this.active = true;
  }

  update(time: number, position: Vector3, target: Vector3): boolean {
    if (!this.active) return false;
    const progress =
      this.duration === 0
        ? 1
        : Math.min(1, Math.max(0, (time - this.startTime) / this.duration));
    const eased =
      progress < 0.5 ? 4 * progress ** 3 : 1 - (-2 * progress + 2) ** 3 / 2;
    position.lerpVectors(this.fromPosition, this.toPosition, eased);
    target.lerpVectors(this.fromTarget, this.toTarget, eased);
    this.active = progress < 1;
    return this.active;
  }

  cancel(): void {
    this.active = false;
  }
}
