import type { Group } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { disposeObject } from "../utils/dispose";

/** Optional asset entry point. M1 creates its park procedurally and does not fetch models. */
export class ModelLoader {
  private readonly loader = new GLTFLoader();
  private disposed = false;

  async load(url: string): Promise<Group> {
    if (this.disposed) throw new Error("ModelLoader has been disposed");
    try {
      const gltf = await this.loader.loadAsync(url);
      if (this.disposed) {
        gltf.scenes.forEach(disposeObject);
        throw new Error("Model load cancelled because its scene was destroyed");
      }
      // Once resolved, the scene manager owns the returned hierarchy and its resources.
      return gltf.scene;
    } catch (error) {
      throw new Error("无法加载三维模型，请检查文件路径、格式和网络连接。", {
        cause: error,
      });
    }
  }
  dispose(): void {
    this.disposed = true;
  }
}
