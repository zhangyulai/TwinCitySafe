import {
  ACESFilmicToneMapping,
  PCFSoftShadowMap,
  SRGBColorSpace,
  WebGLRenderer,
} from "three";
import { CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";

export class RendererManager {
  readonly renderer: WebGLRenderer;
  readonly labels: CSS2DRenderer;
  private disposed = false;
  private pixelRatioLimit = 1.5;

  constructor(container: HTMLElement) {
    // Some integrated GPUs and remote/virtual desktop browsers reject a
    // high-performance, antialiased context even though they can render a
    // normal WebGL2 canvas.  Keep the preferred presentation path first, and
    // retry once with a conservative context before reporting the scene as
    // unavailable.
    this.renderer = this.createRenderer();
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.pixelRatioLimit));
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFSoftShadowMap;
    this.renderer.domElement.className = "twin-scene-canvas";
    this.renderer.domElement.setAttribute("aria-label", "智慧园区三维交互场景");
    this.renderer.domElement.style.display = "block";

    this.labels = new CSS2DRenderer();
    this.labels.domElement.className = "twin-label-layer";
    Object.assign(this.labels.domElement.style, {
      position: "absolute",
      inset: "0",
      pointerEvents: "none",
      overflow: "hidden",
    });
    this.labels.domElement.setAttribute("aria-hidden", "true");
    container.append(this.renderer.domElement, this.labels.domElement);
    this.resize(container.clientWidth, container.clientHeight);
  }

  private createRenderer(): WebGLRenderer {
    const preferred = {
      antialias: true,
      alpha: true,
      powerPreference: "high-performance" as const,
    };
    try {
      return new WebGLRenderer(preferred);
    } catch (preferredError) {
      console.warn("高性能 WebGL 上下文不可用，已切换兼容渲染配置。", preferredError);
      try {
        return new WebGLRenderer({
          antialias: false,
          alpha: true,
          powerPreference: "default",
          precision: "mediump",
          failIfMajorPerformanceCaveat: false,
        });
      } catch (fallbackError) {
        console.error("兼容 WebGL 上下文创建失败。", fallbackError);
        throw fallbackError;
      }
    }
  }

  setPixelRatioLimit(limit: number): void {
    this.pixelRatioLimit = limit;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, limit));
  }

  resize(width: number, height: number): void {
    if (this.disposed) return;
    const safeWidth = Math.max(1, width);
    const safeHeight = Math.max(1, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.pixelRatioLimit));
    this.renderer.setSize(safeWidth, safeHeight);
    this.labels.setSize(safeWidth, safeHeight);
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.renderer.setAnimationLoop(null);
    this.renderer.renderLists.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
    this.labels.domElement.replaceChildren();
    this.labels.domElement.remove();
    // Explicitly release the context when the dashboard is unmounted.
    // A lost context no longer exposes extensions; do not lose it a second time.
    if (!this.renderer.getContext().isContextLost())
      this.renderer.forceContextLoss();
  }
}
