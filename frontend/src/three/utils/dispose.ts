import {
  BufferGeometry,
  InstancedMesh,
  Material,
  Object3D,
  Texture,
} from "three";

// Dispose shared geometry/materials only once; CSS labels own detached DOM elements.
export function disposeObject(root: Object3D): void {
  const geometries = new Set<BufferGeometry>();
  const materials = new Set<Material>();
  const textures = new Set<Texture>();
  root.traverse((object) => {
    const renderable = object as Object3D & {
      geometry?: BufferGeometry;
      material?: Material | Material[];
      element?: HTMLElement;
    };
    if (object instanceof InstancedMesh) object.dispose();
    if (renderable.geometry) geometries.add(renderable.geometry);
    if (renderable.material) {
      for (const material of Array.isArray(renderable.material)
        ? renderable.material
        : [renderable.material])
        materials.add(material);
    }
    renderable.element?.remove();
  });
  for (const material of materials) {
    for (const value of Object.values(material))
      if (value instanceof Texture) textures.add(value);
    material.dispose();
  }
  textures.forEach((texture) => texture.dispose());
  geometries.forEach((geometry) => geometry.dispose());
  root.clear();
  root.removeFromParent();
}
