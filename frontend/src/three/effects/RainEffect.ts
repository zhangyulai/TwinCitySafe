import {
  BufferAttribute,
  BufferGeometry,
  DynamicDrawUsage,
  LineBasicMaterial,
  LineSegments,
} from "three";
import type { WeatherState } from "../../types/realtime";
import { disposeObject } from "../utils/dispose";

/** Fixed particle pool: messages change density/speed; RAF only moves existing vertices. */
export class RainEffect {
  readonly object: LineSegments<BufferGeometry, LineBasicMaterial>;
  readonly capacity = 1800;
  private readonly positions = new Float32Array(this.capacity * 6);
  private readonly attribute: BufferAttribute;
  private particleCount = 0;
  private particleLimit = 1000;
  private weather: WeatherState | null = null;
  private speed = 16;
  private wind = 0;
  private streakLength = 0.75;

  constructor() {
    const geometry = new BufferGeometry();
    for (let index = 0; index < this.capacity; index++) {
      const offset = index * 6;
      // Stable spatial sequence is visual placement only, not simulated telemetry.
      const x = ((index * 43.73) % 118) - 59;
      const y = (index * 17.19) % 65;
      const z = ((index * 31.37) % 96) - 48;
      this.positions.set([x, y, z, x, y + this.streakLength, z], offset);
    }
    this.attribute = new BufferAttribute(this.positions, 3).setUsage(
      DynamicDrawUsage,
    );
    geometry.setAttribute("position", this.attribute);
    geometry.setDrawRange(0, 0);
    const material = new LineBasicMaterial({
      color: 0x86b4d4,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
    });
    this.object = new LineSegments(geometry, material);
    this.object.name = "weather-rain-particles";
    this.object.frustumCulled = false;
    this.object.visible = false;
    this.object.raycast = () => {};
  }

  setParticleLimit(limit: number): void {
    this.particleLimit = Math.min(this.capacity, Math.max(0, limit));
    if (this.weather) this.updateWeather(this.weather);
  }

  updateWeather(weather: WeatherState): void {
    this.weather = weather;
    const intensity = Math.min(1, Math.max(0, weather.rainfall) / 110);
    this.particleCount =
      weather.condition === "rain" ? Math.round(90 + intensity * (this.particleLimit - 90)) : 0;
    this.speed = 16 + intensity * 18;
    this.object.material.opacity=.25+intensity*.3;
    this.wind = Math.min(8, Math.max(0, weather.windSpeed)) * 0.23;
    this.streakLength = 0.7 + intensity * 0.7;
    this.object.geometry.setDrawRange(0, this.particleCount * 2);
    this.object.visible = this.particleCount > 0;
  }

  update(delta: number): void {
    if (!this.object.visible) return;
    for (let index = 0; index < this.particleCount; index++) {
      const offset = index * 6;
      let y = this.positions[offset + 1]! - this.speed * delta;
      let x = this.positions[offset]! + this.wind * delta;
      if (y < 0) y += 65;
      if (x > 59) x -= 118;
      this.positions[offset] = x;
      this.positions[offset + 1] = y;
      this.positions[offset + 3] = x - this.wind * 0.035;
      this.positions[offset + 4] = y + this.streakLength;
    }
    this.attribute.needsUpdate = true;
  }
  get count(): number {
    return this.particleCount;
  }
  dispose(): void {
    disposeObject(this.object);
  }
}
