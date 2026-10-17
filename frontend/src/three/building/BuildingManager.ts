import {
  BoxGeometry,
  Box3,
  Vector3,
  MeshBasicMaterial,
  Color,
  EdgesGeometry,
  Group,
  InstancedMesh,
  LineBasicMaterial,
  LineSegments,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  Object3D,
} from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { buildingMetadata } from "./metadata";
import { riskColors, riskLabels, type BuildingAssetData, type BuildingEntry, type SceneMode } from "../types/scene";
import { disposeObject } from "../utils/dispose";

interface Surface {
  material: MeshStandardMaterial;
  color: Color;
  emissive: Color;
  opacity: number;
  entry: BuildingEntry;
  tint: boolean;
}
interface Block {
  x: number;
  z: number;
  width: number;
  depth: number;
  height: number;
  bottom?: number;
}

/** Owns buildings, their identity, mock metadata and material states. */
export class BuildingManager {
  private leakBuildings=new Set<string>();
  setLeakImpact(ids:string[]):void {if([...this.leakBuildings].join()===ids.join())return;this.leakBuildings=new Set(ids);this.applyAppearance();}
  private floodRisk:number|null=null;
  setFloodRisk(score:number|null):void {if(this.floodRisk===score)return;this.floodRisk=score;if(this.mode==='risk')this.applyAppearance();}
  private deviceFocus = false;
  setDeviceFocus(enabled: boolean): void {
    this.deviceFocus = enabled;
    this.applyAppearance();
  }
  readonly group = new Group();
  readonly entries: BuildingEntry[] = [];
  private readonly surfaces: Surface[] = [];
  private readonly outlines: {
    material: LineBasicMaterial;
    entry: BuildingEntry;
  }[] = [];
  private readonly labels = new Map<Group, CSS2DObject>();
  private readonly boxGeometry = new BoxGeometry(1, 1, 1);
  private readonly edgeGeometry = new EdgesGeometry(this.boxGeometry);
  private mode: SceneMode = "above";
  private hovered: Group | null = null;
  private selected: Group | null = null;

  constructor() {
    this.group.name = "park-buildings";
    const definitions = [
      {
        position: [-27, -22],
        blocks: [
          { x: -3, z: -1, width: 16, depth: 16, height: 32 },
          { x: 8, z: 3, width: 8, depth: 12, height: 22 },
        ],
        height: 32,
      },
      {
        position: [25, -22],
        blocks: [
          { x: -7, z: 0, width: 9, depth: 20, height: 24 },
          { x: 7, z: 0, width: 9, depth: 20, height: 21 },
          { x: 0, z: -6, width: 8, depth: 8, height: 15 },
        ],
        height: 24,
      },
      {
        position: [-29, 20],
        blocks: [
          { x: -5, z: 0, width: 12, depth: 17, height: 18 },
          { x: 7, z: 3, width: 10, depth: 11, height: 12 },
        ],
        height: 18,
      },
      {
        position: [28, 20],
        blocks: [
          { x: 0, z: -3, width: 22, depth: 11, height: 12 },
          { x: -7, z: 5, width: 8, depth: 9, height: 8 },
          { x: 7, z: 5, width: 8, depth: 9, height: 8 },
        ],
        height: 12,
      },
    ];
    definitions.forEach((definition, index) => {
      const object = new Group();
      const metadata = { ...buildingMetadata[index]! };
      const entry = { object, metadata };
      object.name = `building-${metadata.id.toLowerCase()}`;
      object.position.set(definition.position[0]!, 0, definition.position[1]!);
      object.userData = { buildingId: metadata.id, metadata };
      this.entries.push(entry);
      this.group.add(object);
      this.buildSurface(entry, definition.blocks, definition.height);
    });
    this.buildParking();
    this.batchStaticGeometry();
    for(const entry of this.entries){
      if(entry.metadata.type==='parking')continue;
      entry.object.updateWorldMatrix(true,true);
      const bounds=new Box3().setFromObject(entry.object),size=bounds.getSize(new Vector3()),center=bounds.getCenter(new Vector3());
      const proxy=new Mesh(new BoxGeometry(size.x,size.y,size.z),new MeshBasicMaterial({color:0x447c96,transparent:true,opacity:.16,depthWrite:false}));
      proxy.name='underground-building-envelope';proxy.userData.undergroundEnvelope=true;proxy.position.copy(entry.object.worldToLocal(center));proxy.visible=false;entry.object.add(proxy);
    }
    this.entries.forEach((entry) => this.attachBuildingAsset(entry));
    this.setMode("above");
  }

  getById(id: string): BuildingEntry | undefined {
    return this.entries.find((entry) => entry.metadata.id === id);
  }
  setHover(object: Group | null): void {
    this.hovered = object;
    this.applyAppearance();
  }
  setSelected(object: Group | null): void {
    this.selected = object;
    this.applyAppearance();
  }
  setMode(mode: SceneMode): void {
    this.mode = mode;
    this.applyAppearance();
  }

  private material(
    entry: BuildingEntry,
    color: number,
    emissive = 0x000000,
    tint = true,
  ): MeshStandardMaterial {
    const material = new MeshStandardMaterial({
      color,
      emissive,
      roughness: 0.48,
      metalness: 0.42,
      emissiveIntensity: 0.56,
    });
    this.surfaces.push({
      material,
      color: new Color(color),
      emissive: new Color(emissive),
      opacity: 1,
      entry,
      tint,
    });
    return material;
  }

  private box(
    parent: Group,
    material: MeshStandardMaterial,
    width: number,
    height: number,
    depth: number,
    x: number,
    y: number,
    z: number,
    entry?: BuildingEntry,
  ): Mesh {
    const mesh = new Mesh(this.boxGeometry, material);
    mesh.position.set(x, y, z);
    mesh.scale.set(width, height, depth);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    if (entry) {
      const outlineMaterial = new LineBasicMaterial({
        color: 0x37d7ff,
        transparent: true,
        opacity: 0.82,
      });
      const edges = new LineSegments(this.edgeGeometry, outlineMaterial);
      edges.position.copy(mesh.position);
      edges.scale.copy(mesh.scale);
      // Lines are decoration, not separate pickable building surfaces.
      edges.raycast = () => {};
      parent.add(edges);
      this.outlines.push({ material: outlineMaterial, entry });
    }
    return mesh;
  }

  private buildSurface(
    entry: BuildingEntry,
    blocks: Block[],
    height: number,
  ): void {
    const { object } = entry;
    const body = this.material(entry, 0x123d61, 0x0a3153);
    const base = this.material(entry, 0x174d71, 0x082b4b);
    const roof = this.material(entry, 0x0c2948, 0x061d35);
    const trim = this.material(entry, 0x27d4ff, 0x087da7, false);
    const glass = this.material(entry, 0x65e5ff, 0x119ed0);
    glass.roughness = 0.16;
    glass.metalness = 0.58;
    glass.emissiveIntensity = 0.9;
    this.box(object, base, 26, 0.8, 23, 0, 0.4, 0, entry);
    this.box(object, roof, 24, 1.2, 21, 0, 1.35, 0);
    const windows: Matrix4[] = [];
    const transformer = new Object3D();
    for (const block of blocks) {
      const bottom = block.bottom ?? 1.9;
      const bodyMesh = this.box(
        object,
        body,
        block.width,
        block.height,
        block.depth,
        block.x,
        bottom + block.height / 2,
        block.z,
        entry,
      );
      bodyMesh.name = `${entry.metadata.id}-body-${object.children.length}`;
      this.box(
        object,
        trim,
        block.width + 0.7,
        0.42,
        block.depth + 0.7,
        block.x,
        bottom + block.height + 0.2,
        block.z,
        entry,
      );
      this.box(
        object,
        roof,
        block.width - 1.8,
        0.34,
        block.depth - 1.8,
        block.x,
        bottom + block.height + 0.56,
        block.z,
      );
      // Mechanical roof plant gives each silhouette an architectural top.
      this.box(
        object,
        base,
        Math.min(4, block.width * 0.35),
        1.7,
        3.5,
        block.x,
        bottom + block.height + 1.45,
        block.z - 1.5,
        entry,
      );
      const floors = Math.max(2, Math.floor(block.height / 2.75));
      const columnsX = Math.max(2, Math.floor((block.width - 1.8) / 2.45));
      const columnsZ = Math.max(2, Math.floor((block.depth - 1.8) / 2.45));
      const pushWindow = (
        x: number,
        y: number,
        z: number,
        rotated: boolean,
      ) => {
        transformer.position.set(x, y, z);
        transformer.rotation.set(0, rotated ? Math.PI / 2 : 0, 0);
        transformer.scale.set(1.45, 1.22, 0.085);
        transformer.updateMatrix();
        windows.push(transformer.matrix.clone());
      };
      for (let floor = 0; floor < floors; floor++) {
        const y = bottom + 1.5 + floor * ((block.height - 2) / floors);
        for (let column = 0; column < columnsX; column++) {
          const x =
            block.x -
            block.width / 2 +
            (column + 1) * (block.width / (columnsX + 1));
          pushWindow(x, y, block.z + block.depth / 2 + 0.06, false);
          pushWindow(x, y, block.z - block.depth / 2 - 0.06, false);
        }
        for (let column = 0; column < columnsZ; column++) {
          const z =
            block.z -
            block.depth / 2 +
            (column + 1) * (block.depth / (columnsZ + 1));
          pushWindow(block.x + block.width / 2 + 0.06, y, z, true);
          pushWindow(block.x - block.width / 2 - 0.06, y, z, true);
        }
      }
    }
    const windowInstances = new InstancedMesh(
      this.boxGeometry,
      glass,
      windows.length,
    );
    const color = new Color();
    windows.forEach((matrix, index) => {
      windowInstances.setMatrixAt(index, matrix);
      color.setHex(
        index % 9 === 0 ? 0xe3fdff : index % 4 === 0 ? 0x168ec4 : 0x57dfff,
      );
      windowInstances.setColorAt(index, color);
    });
    windowInstances.name = `${entry.metadata.id}-windows`;
    object.add(windowInstances);
    // Entrance canopy and glazing face the central east-west avenue.
    const entranceZ =
      entry.metadata.type === "office" || entry.metadata.type === "research"
        ? 11.2
        : -11.2;
    this.box(object, trim, 7.6, 0.34, 4, 0, 3.5, entranceZ);
    this.box(
      object,
      glass,
      6,
      2.7,
      0.18,
      0,
      2.25,
      entranceZ - Math.sign(entranceZ),
    );
    this.label(entry, height + 7);
  }

  private buildParking(): void {
    const metadata = { ...buildingMetadata[4]! };
    const object = new Group();
    object.name = "underground-parking-b2";
    object.position.set(0, -6, 10);
    object.userData = { buildingId: metadata.id, metadata };
    const entry = { object, metadata };
    this.entries.push(entry);
    this.group.add(object);
    const slab = this.material(entry, 0x274959);
    const structure = this.material(entry, 0x497786);
    const marking = this.material(entry, 0x91bdba, 0x1e4d53, false);
    // B2 is the main shared underground space for the pump room, pipe
    // network and flood simulation. Keep it visibly larger than the ground
    // buildings so it reads as a real parking level rather than a small pad.
    const floor = this.box(object, slab, 56, 0.65, 44, 0, 0, 0, entry);
    floor.name = "B2-PARKING-body-slab";
    this.box(object, structure, 56, 2.4, 0.4, 0, 1.45, -22, entry);
    this.box(object, structure, 0.4, 2.4, 44, -28, 1.45, 0, entry);
    this.box(object, structure, 0.4, 0.65, 44, 28, 0.6, 0, entry);
    this.box(object, structure, 56, 0.65, 0.4, 0, 0.6, 22, entry);
    const columns = new InstancedMesh(this.boxGeometry, structure, 21);
    const marks = new InstancedMesh(this.boxGeometry, marking, 96);
    const pose = new Object3D();
    let columnIndex = 0;
    let markIndex = 0;
    for (const z of [-14, 0, 14]) {
      for (const x of [-21, -14, -7, 0, 7, 14, 21]) {
        pose.position.set(x, 1.6, z);
        pose.scale.set(0.55, 2.7, 0.55);
        pose.updateMatrix();
        columns.setMatrixAt(columnIndex++, pose.matrix);
      }
    }
    // Four parking bays surround the central vehicle aisle, while the middle
    // remains clear for the live pipe network and emergency barrier.
    for (const z of [-16, -9, 9, 16]) {
      for (let x = -24; x <= 24; x += 2.4) {
        pose.position.set(x, 0.345, z);
        pose.scale.set(0.07, 0.025, 2.8);
        pose.updateMatrix();
        marks.setMatrixAt(markIndex++, pose.matrix);
      }
      pose.position.set(0, 0.345, z + (z < 0 ? 3 : -3));
      pose.scale.set(48, 0.025, 0.07);
      pose.updateMatrix();
      marks.setMatrixAt(markIndex++, pose.matrix);
    }
    // Lane guide lines make the added scale legible from the default camera.
    for (const z of [-4, 4]) {
      pose.position.set(0, 0.345, z);
      pose.scale.set(52, 0.025, 0.1);
      pose.updateMatrix();
      marks.setMatrixAt(markIndex++, pose.matrix);
    }
    marks.count = markIndex;
    object.add(columns, marks);
    this.label(entry, 4.9);
  }

  /** Bake each static box transform into one geometry per material and building.
   * Instanced windows, columns and parking stripes keep their existing GPU batches.
   */
  private batchStaticGeometry(): void {
    const nextOutlines: {
      material: LineBasicMaterial;
      entry: BuildingEntry;
    }[] = [];
    for (const entry of this.entries) {
      const batches = new Map<
        MeshStandardMaterial,
        Mesh<BoxGeometry, MeshStandardMaterial>[]
      >();
      for (const child of entry.object.children) {
        if (
          !(child instanceof Mesh) ||
          child instanceof InstancedMesh ||
          child.geometry !== this.boxGeometry ||
          !(child.material instanceof MeshStandardMaterial)
        )
          continue;
        const parts = batches.get(child.material) ?? [];
        parts.push(child as Mesh<BoxGeometry, MeshStandardMaterial>);
        batches.set(child.material, parts);
      }
      let batchIndex = 0;
      for (const [material, parts] of batches) {
        const transformed = parts.map((part) => {
          part.updateMatrix();
          return part.geometry.clone().applyMatrix4(part.matrix);
        });
        const geometry = mergeGeometries(transformed, false);
        transformed.forEach((part) => part.dispose());
        if (!geometry) continue;
        geometry.computeBoundingBox();
        geometry.computeBoundingSphere();
        const mesh = new Mesh(geometry, material);
        mesh.name = parts.some((part) => part.name.includes("-body-"))
          ? `${entry.metadata.id}-body-batched`
          : `${entry.metadata.id}-architecture-${batchIndex++}`;
        mesh.castShadow = parts.some((part) => part.castShadow);
        mesh.receiveShadow = parts.some((part) => part.receiveShadow);
        parts.forEach((part) => part.removeFromParent());
        entry.object.add(mesh);
      }
      const lines = entry.object.children.filter(
        (child): child is LineSegments<EdgesGeometry, LineBasicMaterial> =>
          child instanceof LineSegments &&
          child.geometry === this.edgeGeometry &&
          child.material instanceof LineBasicMaterial,
      );
      if (!lines.length) continue;
      const transformedEdges = lines.map((line) => {
        line.updateMatrix();
        return line.geometry.clone().applyMatrix4(line.matrix);
      });
      const geometry = mergeGeometries(transformedEdges, false);
      transformedEdges.forEach((part) => part.dispose());
      if (!geometry) {
        lines.forEach((line) =>
          nextOutlines.push({ material: line.material, entry }),
        );
        continue;
      }
      geometry.computeBoundingSphere();
      const material = lines[0]!.material;
      const outline = new LineSegments(geometry, material);
      outline.name = `${entry.metadata.id}-edges-batched`;
      outline.raycast = () => {};
      for (const line of lines) {
        line.removeFromParent();
        if (line.material !== material) line.material.dispose();
      }
      entry.object.add(outline);
      nextOutlines.push({ material, entry });
    }
    this.outlines.splice(0, this.outlines.length, ...nextOutlines);
    // The unit-edge template is no longer attached after successful batching.
    if (
      !this.entries.some((entry) =>
        entry.object.children.some(
          (child) =>
            child instanceof LineSegments &&
            child.geometry === this.edgeGeometry,
        ),
      )
    )
      this.edgeGeometry.dispose();
  }

  private label(entry: BuildingEntry, y: number): void {
    const element = document.createElement("div");
    element.className = "twin-label";
    element.dataset.buildingId = entry.metadata.id;
    element.style.pointerEvents = "none";
    element.replaceChildren(document.createTextNode(entry.metadata.name), Object.assign(document.createElement("small"), { className: "twin-label__type", textContent: entry.metadata.typeLabel }));
    const label = new CSS2DObject(element);
    label.position.set(0, y, 0);
    entry.object.add(label);
    this.labels.set(entry.object, label);
  }

  private attachBuildingAsset(entry: BuildingEntry): void {
    const metadata = entry.metadata;
    const data: BuildingAssetData = {
      id: `building_${String(this.entries.indexOf(entry) + 1).padStart(3, "0")}`,
      name: metadata.name, type: metadata.typeLabel, floors: metadata.floors,
      status: metadata.status.replace(" · 演示数据", ""),
      riskLevel: riskLabels[metadata.risk],
      position: [entry.object.position.x, entry.object.position.y, entry.object.position.z],
    };
    entry.object.userData.building = data;
    entry.object.traverse((object) => { object.userData.building = data; });
  }

  private applyAppearance(): void {
    for (const entry of this.entries) {
      const parking = entry.metadata.type === "parking";
      entry.object.visible =
        (!parking || this.mode !== "above") && (!this.deviceFocus || parking);
      for(const child of entry.object.children){
        if(child instanceof CSS2DObject || parking)continue;
        child.visible=child.userData.undergroundEnvelope ? this.mode==='underground' : this.mode!=='underground';
        if(child instanceof Mesh&&child.userData.undergroundEnvelope){const mat=child.material as MeshBasicMaterial;mat.color.set(this.leakBuildings.has(entry.metadata.id)?0xe9a451:0x447c96);mat.opacity=this.leakBuildings.has(entry.metadata.id)?.35:.16;}
      }
      entry.object.traverse((child) => {
        if (child instanceof Mesh) {
          child.userData.initialCastShadow ??= child.castShadow;
          child.castShadow =
            Boolean(child.userData.initialCastShadow) &&
            (parking || this.mode !== "underground");
        }
        if (child instanceof CSS2DObject)
          child.element.style.opacity =
            this.mode === "underground" && !parking ? "0.48" : "1";
      });
    }
    for (const surface of this.surfaces) {
      const { material, entry } = surface;
      const muted =
        this.mode === "underground" && entry.metadata.type !== "parking";
      material.color.copy(surface.color);
      if (this.mode === "risk" && surface.tint)
        material.color.lerp(new Color(riskColors[entry.metadata.risk]), 0.62);
      material.emissive.copy(surface.emissive);
      const selected = this.selected === entry.object;
      const hovered = this.hovered === entry.object;
      entry.object.scale.setScalar(selected ? 1.035 : hovered ? 1.018 : 1);
      const label = this.labels.get(entry.object);
      if (label) {
        const subline = selected || hovered ? `风险等级 · ${riskLabels[entry.metadata.risk]}` : entry.metadata.typeLabel;
        label.element.replaceChildren(document.createTextNode(entry.metadata.name), Object.assign(document.createElement("small"), { className: "twin-label__type", textContent: subline }));
      }
      if (selected || hovered)
        material.emissive.lerp(new Color(0x3b9fad), selected ? 0.32 : 0.16);
      if (this.mode === "risk" && surface.tint)
        material.emissive.lerp(
          new Color(riskColors[entry.metadata.risk]),
          0.15,
        );
      if(this.mode==='risk' && entry.metadata.type==='parking' && this.floodRisk!==null){
        const c=new Color(this.floodRisk>=80?'#ed6b6d':this.floodRisk>=60?'#ee9853':this.floodRisk>=20?'#e4ce65':'#29d3a2');
        material.color.copy(surface.color).lerp(c,.6);material.emissive.copy(c).multiplyScalar(.18);
      }
      if(this.leakBuildings.has(entry.metadata.id)&&surface.tint){material.color.lerp(new Color(0xe9a451),.55);material.emissive.lerp(new Color(0xe9a451),.2);}
      material.opacity = muted ? 0.13 : surface.opacity;
      material.transparent = muted;
      material.depthWrite = !muted;
      material.needsUpdate = true;
    }
    for (const outline of this.outlines) {
      outline.material.opacity =
        this.mode === "underground" && outline.entry.metadata.type !== "parking"
          ? 0.14
          : 0.4;
    }
  }

  dispose(): void {
    disposeObject(this.group);
    this.entries.length = 0;
    this.surfaces.length = 0;
    this.outlines.length = 0;
  }
}
