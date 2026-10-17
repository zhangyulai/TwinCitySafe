import { Vector2 } from "three";
import type { Object3D, PerspectiveCamera, Scene, WebGLRenderer } from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { OutlinePass } from "three/addons/postprocessing/OutlinePass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

export class EffectManager {
  private readonly composer: EffectComposer;
  private readonly renderPass: RenderPass;
  private readonly outline: OutlinePass;
  private readonly output = new OutputPass();
  private postprocessing = true;
  private pixelRatioLimit = 1.5;
  private preview: Object3D[] = [];
  private selected: Object3D | null = null;
  private hovered: Object3D | null = null;

  constructor(
    private readonly renderer: WebGLRenderer,
    private readonly scene: Scene,
    private readonly camera: PerspectiveCamera,
  ) {
    this.composer = new EffectComposer(renderer);
    // Limit offscreen buffers too; the base canvas still respects the DPR <= 2 requirement.
    this.composer.setPixelRatio(Math.min(renderer.getPixelRatio(), this.pixelRatioLimit));
    this.renderPass = new RenderPass(scene, camera);
    this.outline = new OutlinePass(new Vector2(1, 1), scene, camera);
    this.outline.edgeGlow = 0;
    this.outline.edgeThickness = 1;
    this.outline.pulsePeriod = 0;
    this.outline.hiddenEdgeColor.set(0x163e4a);
    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.outline);
    this.composer.addPass(this.output);
  }
  setHover(object: Object3D | null): void {
    this.hovered = object;
    this.updateOutline();
  }
  setSelected(object: Object3D | null): void {
    this.selected = object;
    this.updateOutline();
  }
  setPreview(objects:Object3D[]):void {this.preview=objects;this.updateOutline();}
  private updateOutline(): void {
    if(this.preview.length){this.outline.selectedObjects=this.preview;this.outline.visibleEdgeColor.set(0x6baeff);this.outline.edgeStrength=3;return;}
    const object = this.selected ?? this.hovered;
    this.outline.selectedObjects = object ? [object] : [];
    this.outline.visibleEdgeColor.set(this.selected ? 0x74ecf1 : 0x5fabb7);
    this.outline.edgeStrength = this.selected ? 3 : 1.3;
  }
  private clearTrace: (() => void) | null = null;
  setTraceHighlight(apply:()=>void, clear:()=>void):void { this.clearTraceHighlight();apply();this.clearTrace=clear; }
  clearTraceHighlight():void {this.clearTrace?.();this.clearTrace=null;}
  setQuality(postprocessing: boolean, pixelRatio: number): void {
    this.postprocessing = postprocessing;
    this.pixelRatioLimit = Math.min(pixelRatio, 1.5);
  }
  debug() { return { enabled: this.postprocessing, active: this.postprocessing && this.outline.selectedObjects.length > 0, selectedObjects: this.outline.selectedObjects.length, pixelRatioLimit: this.pixelRatioLimit }; }
  resize(width: number, height: number): void {
    this.composer.setPixelRatio(Math.min(this.renderer.getPixelRatio(), this.pixelRatioLimit));
    this.composer.setSize(width, height);
  }
  render(delta: number): void {
    // Skip postprocessing entirely when no highlight is visible.
    if (this.postprocessing && this.outline.selectedObjects.length) this.composer.render(delta);
    else this.renderer.render(this.scene, this.camera);
  }
  dispose(): void {
    this.clearTraceHighlight();
    this.preview=[];
    this.outline.selectedObjects = [];
    this.renderPass.dispose();
    this.outline.dispose();
    this.output.dispose();
    this.composer.dispose();
    this.selected = this.hovered = null;
  }
}
