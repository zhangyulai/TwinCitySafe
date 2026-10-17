import {
  AmbientLight,
  Color,
  DirectionalLight,
  Fog,
  HemisphereLight,
  Object3D,
  Scene,
} from "three";
import { disposeObject } from "../utils/dispose";
import type { WeatherState } from "../../types/realtime";

export class SceneManager {
  readonly scene = new Scene();
  private readonly sun = new DirectionalLight(0xc6e4ff, 2.4);
  private readonly ambient = new AmbientLight(0xbad5e9, 0.92);
  private readonly hemisphere = new HemisphereLight(0xb4ddf3, 0x233541, 1.65);
  private readonly targetIntensity = {
    sun: 2.4,
    ambient: 0.92,
    hemisphere: 1.65,
  };
  private disposed = false;
  private storm=0;
  private stormTarget=0;
  private readonly clearSky=new Color(0x0a1d2b);
  private readonly stormSky=new Color(0x060e18);

  constructor() {
    this.scene.background = new Color(0x0a1d2b);
    this.scene.fog = new Fog(0x0a1d2b, 180, 520);
    this.sun.position.set(65, 110, 55);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024);
    this.sun.shadow.camera.left = -88;
    this.sun.shadow.camera.right = 88;
    this.sun.shadow.camera.top = 88;
    this.sun.shadow.camera.bottom = -88;
    this.sun.shadow.camera.near = 1;
    this.sun.shadow.camera.far = 250;
    this.sun.shadow.normalBias = 0.18;
    this.sun.shadow.bias = -0.0001;
    this.scene.add(this.ambient, this.hemisphere);
    this.scene.add(this.sun);
  }

  updateWeather(weather: WeatherState): void {
    const cloudy = weather.condition === "cloudy";
    const raining = weather.condition === "rain";
    const intensity = Math.min(1, Math.max(0, weather.rainfall) / 110);
    this.stormTarget=intensity;
    this.targetIntensity.sun = raining
      ? 1.3 - intensity * 0.3
      : cloudy
        ? 1.7
        : 2.4;
    this.targetIntensity.ambient = raining ? 0.66-intensity*.10 : cloudy ? 0.78 : 0.92;
    this.targetIntensity.hemisphere = raining ? 1.18 : cloudy ? 1.4 : 1.65;
  }

  /** Static asset lighting when historical weather was not recorded. */
  resetReplayLighting(): void {
    this.stormTarget = 0;
    this.targetIntensity.sun = 2.4;
    this.targetIntensity.ambient = 0.92;
    this.targetIntensity.hemisphere = 1.65;
    this.update(20);
  }

  update(delta: number): void {
    const smoothing = 1 - Math.exp(-delta * 2.5);
    this.storm+=(this.stormTarget-this.storm)*smoothing;
    (this.scene.background as Color).copy(this.clearSky).lerp(this.stormSky,this.storm);
    const fog=this.scene.fog as Fog;fog.near=180-this.storm*70;fog.far=520-this.storm*180;fog.color.copy(this.scene.background as Color);
    this.sun.intensity +=
      (this.targetIntensity.sun - this.sun.intensity) * smoothing;
    this.ambient.intensity +=
      (this.targetIntensity.ambient - this.ambient.intensity) * smoothing;
    this.hemisphere.intensity +=
      (this.targetIntensity.hemisphere - this.hemisphere.intensity) * smoothing;
  }

  setShadowSize(size: number): void {
    if (!size || this.sun.shadow.mapSize.x === size) return;
    this.sun.shadow.mapSize.set(size, size);
    // Reuse the target; allocation changes only on an explicit quality switch.
    this.sun.shadow.map?.setSize(size, size);
    this.sun.shadow.needsUpdate = true;
  }

  get shadowSize(): number { return this.sun.shadow.mapSize.x; }

  getLightingState() {
    return {
      sun: this.sun.intensity,
      ambient: this.ambient.intensity,
      hemisphere: this.hemisphere.intensity,
    };
  }

  add(...objects: Object3D[]): void {
    this.scene.add(...objects);
  }
  remove(object: Object3D): void {
    this.scene.remove(object);
  }
  getObjectByName(name: string): Object3D | undefined {
    return this.scene.getObjectByName(name);
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.sun.shadow.dispose();
    disposeObject(this.scene);
    this.scene.background = null;
    this.scene.fog = null;
  }
}
