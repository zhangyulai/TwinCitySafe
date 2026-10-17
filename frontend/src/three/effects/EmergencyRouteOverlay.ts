import { BufferGeometry, Float32BufferAttribute, Group, Line, LineBasicMaterial, Mesh, MeshBasicMaterial, RingGeometry, Vector3 } from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import type { SceneMode } from "../types/scene";
import { disposeObject } from "../utils/dispose";

/**
 * A deterministic command overlay for the emergency presentation mode. It is
 * deliberately separate from physical simulation: routes are visual response
 * guidance for the software demo, not a real evacuation command system.
 */
export class EmergencyRouteOverlay {
  readonly group = new Group();
  private rescuePath = [new Vector3(14.5, .68, 10), new Vector3(0, .68, 0), new Vector3(-36, .68, -10), new Vector3(-63, .68, -37), new Vector3(-96, .68, -76)];
  private readonly pulses: Mesh[] = [];
  private readonly incident: Mesh;
  private readonly incidentLabel: CSS2DObject;
  private readonly rescueLine: Line;
  private elapsed = 0;
  private running = false;
  private speed = 1;

  constructor() {
    this.group.name = "emergency-command-overlay";
    this.incident = new Mesh(new RingGeometry(3.1, 3.75, 36), new MeshBasicMaterial({ color: 0xef6c67, transparent: true, opacity: 0.9, depthWrite: false }));
    this.incident.rotation.x = -Math.PI / 2;
    this.incident.position.set(14.5, 0.48, 10);
    this.incident.name = "emergency-incident-marker";
    this.incidentLabel = this.label("事故位置 · B2 东入口", new Vector3(14.5, 1.2, 10), "#ff958e");
    this.group.add(this.incident, this.incidentLabel);

    this.rescueLine = this.addRoute(
      this.rescuePath,
      0xffc96a,
      "推荐救援路线",
      new Vector3(-37, 1, -10),
    );
    for (let index = 0; index < 5; index += 1) {
      const pulse = new Mesh(new RingGeometry(.45, .78, 16), new MeshBasicMaterial({ color: 0xffd36b, transparent: true, opacity: .9, depthWrite: false }));
      pulse.rotation.x = -Math.PI / 2; pulse.name = `emergency-route-pulse-${index + 1}`; this.pulses.push(pulse); this.group.add(pulse);
    }
    this.addRoute(
      [new Vector3(14.5, .52, 10), new Vector3(33, .52, 22), new Vector3(63, .52, 37), new Vector3(97, .52, 57)],
      0x62ebd1,
      "人员疏散路径 A",
      new Vector3(63, 1, 37),
    );
    this.addRoute(
      [new Vector3(14.5, .54, 10), new Vector3(-9, .54, 26), new Vector3(-42, .54, 52), new Vector3(-97, .54, 72)],
      0x72d8ff,
      "人员疏散路径 B",
      new Vector3(-42, 1, 52),
    );
    this.group.visible = false;
  }

  private addRoute(points: Vector3[], color: number, text: string, labelPosition: Vector3): Line {
    const vertices: number[] = [];
    for (const point of points) vertices.push(point.x, point.y, point.z);
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new Float32BufferAttribute(vertices, 3));
    const line = new Line(geometry, new LineBasicMaterial({ color, transparent: true, opacity: 0.95 }));
    line.name = `emergency-route-${text}`;
    this.group.add(line, this.label(text, labelPosition, `#${color.toString(16).padStart(6, "0")}`));
    return line;
  }

  private label(text: string, position: Vector3, color: string): CSS2DObject {
    const element = document.createElement("div");
    element.className = "twin-label emergency-route-label";
    element.style.color = color;
    element.style.borderColor = color;
    element.style.pointerEvents = "none";
    element.textContent = text;
    const label = new CSS2DObject(element);
    label.position.copy(position);
    return label;
  }

  setMode(mode: SceneMode): void { this.group.visible = mode === "emergency"; }
  /** Move the command overlay to the building chosen as the simulated incident. */
  setIncident(position: Vector3, name: string): void {
    const source = new Vector3(position.x, .68, position.z);
    this.incident.position.set(source.x, .48, source.z);
    this.incidentLabel.position.set(source.x, 1.2, source.z);
    this.incidentLabel.element.textContent = `事故位置 · ${name}`;
    this.rescuePath = [
      source,
      new Vector3(source.x * .55, .68, source.z * .46),
      new Vector3(-36, .68, -10),
      new Vector3(-63, .68, -37),
      new Vector3(-96, .68, -76),
    ];
    const vertices: number[] = [];
    for (const point of this.rescuePath) vertices.push(point.x, point.y, point.z);
    this.rescueLine.geometry.setAttribute("position", new Float32BufferAttribute(vertices, 3));
    this.rescueLine.geometry.computeBoundingSphere();
    this.reset();
  }
  start(): void { this.running = true; }
  pause(): void { this.running = false; }
  reset(): void { this.running = false; this.elapsed = 0; this.update(0); }
  setSpeed(speed: number): void { this.speed = Math.max(.5, Math.min(5, speed)); }
  get isRunning(): boolean { return this.running; }
  update(delta: number): void {
    if (this.running) this.elapsed += delta * this.speed;
    this.pulses.forEach((pulse, index) => {
      const progress = (this.elapsed * .22 + index / this.pulses.length) % 1;
      const scaled = progress * (this.rescuePath.length - 1); const segment = Math.min(this.rescuePath.length - 2, Math.floor(scaled));
      pulse.position.copy(this.rescuePath[segment]!).lerp(this.rescuePath[segment + 1]!, scaled - segment);
      (pulse.material as MeshBasicMaterial).opacity = .55 + .35 * Math.sin((this.elapsed + index) * 4) ** 2;
    });
  }
  dispose(): void { disposeObject(this.group); }
}
