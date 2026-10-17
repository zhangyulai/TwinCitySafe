import {
  Box3,
  BufferGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DoubleSide,
  EdgesGeometry,
  ExtrudeGeometry,
  Float32BufferAttribute,
  Group,
  IcosahedronGeometry,
  InstancedMesh,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Object3D,
  PlaneGeometry,
  Shape,
  Vector3,
} from "three";
import type { SceneMode } from "../types/scene";
import { disposeObject } from "../utils/dispose";

type Position = [number, number];
type GeoFeature = {
  geometry?: { type?: string; coordinates?: unknown };
  properties?: { layer?: string; osmId?: string; height?: string | number; levels?: string | number; highway?: string };
};
type GeoCollection = { features?: GeoFeature[] };

const ORIGIN: Position = [121.38445, 31.16532];
const METERS_PER_LNG = 95020;
const METERS_PER_LAT = 110920;
const SCALE = 0.1;
const LIMIT_X = 78;
const LIMIT_Z = 70;
// This is intentionally much wider than the asset-extraction window. It
// covers the whole camera-visible ground with real geographic context instead
// of presenting the campus as a small map card floating in a dark scene.
const MAP_LIMIT_X = 340;
const MAP_LIMIT_Z = 280;
const ONLINE_BASEMAP_ENABLED = import.meta.env.VITE_ENABLE_ONLINE_GIS === "true";
// The four labelled simulation buildings are overlay assets, separate from
// public OSM footprints. Landscaping must reserve their actual site pads too.
const PROJECT_BUILDING_EXCLUSIONS = [
  { minX: -42, maxX: -11, minZ: -35, maxZ: -9 },  // 办公楼 A
  { minX: 9, maxX: 41, minZ: -41, maxZ: -3 },     // 科研楼 B
  { minX: -44, maxX: -13, minZ: 7, maxZ: 33 },    // 实验楼 C
  { minX: 13, maxX: 43, minZ: 7, maxZ: 34 },      // 综合服务楼
  { minX: -31, maxX: 31, minZ: -18, maxZ: 37 },   // B2 停车场地面范围
];

function stableNumber(value: string): number {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1)
    result = Math.imul(result ^ value.charCodeAt(index), 16777619);
  return result >>> 0;
}

/**
 * Converts the bundled public OSM extract into a lightweight Three.js campus
 * base. It intentionally keeps GIS geometry and the project's simulated assets
 * separate: geometry is a spatial reference, never a claim about real devices.
 */
export class GeoCampusManager {
  readonly group = new Group();
  private readonly materials: (MeshStandardMaterial | MeshBasicMaterial | LineBasicMaterial)[] = [];
  private disposed = false;
  private loaded = false;
  private readonly bounds = new Box3();
  private planTexture?: CanvasTexture;
  private planCanvas?: HTMLCanvasElement;
  private sitePlan?: Mesh;
  private readonly roadMeshes: Mesh[] = [];
  /** Public GIS does not consistently tag trees. This layer adds restrained,
   * deterministic landscaping around real building footprints without claiming
   * it is a surveyed vegetation inventory. */
  private readonly vegetation = new Group();
  private mode: SceneMode = "above";
  private contextEnabled = true;

  constructor(
    private readonly onReady?: (bounds: Box3) => void,
    private readonly onBasemapSource?: (source: "local" | "online") => void,
  ) {
    this.group.name = "public-gis-campus-base";
    this.vegetation.name = "gis-context-landscaping";
    this.group.visible = false;
    void this.load();
  }

  private toScene([longitude, latitude]: Position): Vector3 {
    return new Vector3(
      (longitude - ORIGIN[0]) * METERS_PER_LNG * SCALE,
      0,
      -(latitude - ORIGIN[1]) * METERS_PER_LAT * SCALE,
    );
  }

  private inside(point: Vector3): boolean {
    return Math.abs(point.x) <= LIMIT_X && Math.abs(point.z) <= LIMIT_Z;
  }

  private async load(): Promise<void> {
    try {
      const response = await fetch("/gis/caohejing-keji-oasis.geojson", { cache: "force-cache" });
      if (!response.ok) return;
      const source = (await response.json()) as GeoCollection;
      if (this.disposed) return;
      this.build(source.features ?? []);
      this.loaded = true;
      this.applyVisibility();
      this.onReady?.(this.bounds.clone());
    } catch {
      // The standard procedural campus remains available if the optional GIS
      // source cannot be read, so a transient local-server failure is harmless.
    }
  }

  private build(features: GeoFeature[]): void {
    const roads: Vector3[][] = [];
    const buildings: { footprint: Vector3[]; feature: GeoFeature }[] = [];
    for (const feature of features) {
      const layer = feature.properties?.layer;
      const geometry = feature.geometry;
      if (!geometry?.coordinates) continue;
      if (layer === "roads" && geometry.type === "LineString") {
        const path = (geometry.coordinates as Position[]).map((point) => this.toScene(point));
        if (path.some((point) => this.inside(point))) roads.push(path);
      }
      if (layer === "buildings" && geometry.type === "Polygon") {
        const ring = (geometry.coordinates as Position[][])[0]?.map((point) => this.toScene(point)) ?? [];
        if (ring.length > 3 && ring.some((point) => this.inside(point))) buildings.push({ footprint: ring, feature });
      }
    }
    // Keep the public centre lines and add a readable perimeter circulation
    // route around the extracted park area. It gives every module the same
    // spatial frame even when a page is shown at a compact viewport.
    roads.push(this.perimeterRoad());
    this.createSitePlan(roads, buildings.map((entry) => entry.footprint));
    this.createRoads(roads);
    this.createBuildings(buildings);
    this.createVegetation(buildings.map((entry) => entry.footprint), roads);
    this.bounds.setFromObject(this.group);
    this.bounds.expandByScalar(7);
  }

  /** The local vector plan is drawn first. Public OSM tiles then replace it
   * when available, on the same geographic canvas used by the 3D footprints. */
  private createSitePlan(roads: Vector3[][], footprints: Vector3[][]): void {
    // The canvas is a single GPU texture. 4096px preserves road labels when a
    // tilted camera looks across the whole real GIS field.
    const size = 4096;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d")!;
    context.fillStyle = "#06172a";
    context.fillRect(0, 0, size, size);
    context.strokeStyle = "#1c4c6b";
    context.lineWidth = 1;
    for (let tick = 0; tick <= size; tick += 64) {
      context.beginPath(); context.moveTo(tick, 0); context.lineTo(tick, size); context.stroke();
      context.beginPath(); context.moveTo(0, tick); context.lineTo(size, tick); context.stroke();
    }
    const point = (source: Vector3) => [((source.x + MAP_LIMIT_X) / (MAP_LIMIT_X * 2)) * size, ((source.z + MAP_LIMIT_Z) / (MAP_LIMIT_Z * 2)) * size] as const;
    context.lineCap = "round";
    for (const road of roads) {
      const visible = road.filter((item) => this.inside(item));
      if (visible.length < 2) continue;
      context.beginPath();
      visible.forEach((item, index) => { const [x, y] = point(item); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y); });
      context.strokeStyle = "#123b57"; context.lineWidth = 20; context.stroke();
      context.strokeStyle = "#20769b"; context.lineWidth = 3; context.stroke();
    }
    for (const footprint of footprints) {
      if (!footprint.some((item) => this.inside(item))) continue;
      context.beginPath();
      footprint.forEach((item, index) => { const [x, y] = point(item); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y); });
      context.closePath();
      context.fillStyle = "#0a3450"; context.fill();
      context.strokeStyle = "#36bde5"; context.lineWidth = 2; context.stroke();
    }
    this.planCanvas = canvas;
    this.planTexture = new CanvasTexture(canvas);
    this.planTexture.colorSpace = "srgb";
    this.planTexture.anisotropy = 8;
    const material = new MeshBasicMaterial({ map: this.planTexture, transparent: true, opacity: 0.96, side: DoubleSide, depthWrite: false });
    this.materials.push(material);
    this.sitePlan = new Mesh(new PlaneGeometry(MAP_LIMIT_X * 2, MAP_LIMIT_Z * 2), material);
    this.sitePlan.name = "gis-vector-site-plan";
    this.sitePlan.rotation.x = -Math.PI / 2;
    this.sitePlan.position.y = 0.04;
    this.sitePlan.raycast = () => {};
    this.sitePlan.visible = this.mode !== "underground";
    this.group.add(this.sitePlan);
    this.onBasemapSource?.("local");
    if (ONLINE_BASEMAP_ENABLED) void this.drawOnlineBasemap(size);
  }

  /** Draws a real OSM slippy-map mosaic beneath the Three.js campus. The scene
   * coordinates and the tile projection share the same WGS84 source point, so
   * buildings, roads and simulation assets remain spatially aligned. */
  private async drawOnlineBasemap(size: number): Promise<void> {
    const canvas = this.planCanvas;
    const texture = this.planTexture;
    if (!canvas || !texture) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    // Zoom 16 keeps Chinese road labels legible in the tilted Three.js view.
    // Requests are queued below, so this does not become an uncontrolled burst.
    // The focused building geometry remains at
    // its true relative WGS84 position in the centre of that field.
    const zoom = 16;
    const tileCount = 2 ** zoom;
    const longitudeToTile = (longitude: number) => (longitude + 180) / 360 * tileCount;
    const latitudeToTile = (latitude: number) => {
      const radians = latitude * Math.PI / 180;
      return (1 - Math.asinh(Math.tan(radians)) / Math.PI) * tileCount / 2;
    };
    const xSpan = MAP_LIMIT_X / (METERS_PER_LNG * SCALE);
    const ySpan = MAP_LIMIT_Z / (METERS_PER_LAT * SCALE);
    const left = longitudeToTile(ORIGIN[0] - xSpan);
    const right = longitudeToTile(ORIGIN[0] + xSpan);
    const top = latitudeToTile(ORIGIN[1] + ySpan);
    const bottom = latitudeToTile(ORIGIN[1] - ySpan);
    const firstX = Math.floor(left) - 1, lastX = Math.floor(right) + 1;
    const firstY = Math.floor(top) - 1, lastY = Math.floor(bottom) + 1;
    let onlineReported = false;
    const loadTile = (x: number, y: number) => new Promise<void>((resolve) => {
      if (y < 0 || y >= tileCount) { resolve(); return; }
      const wrappedX = ((x % tileCount) + tileCount) % tileCount;
      const image = new Image();
      image.crossOrigin = "anonymous";
      image.onload = () => {
        if (this.disposed) { resolve(); return; }
        const drawX = (x - left) / (right - left) * size;
        const drawY = (y - top) / (bottom - top) * size;
        const drawWidth = size / (right - left);
        const drawHeight = size / (bottom - top);
        context.drawImage(image, drawX, drawY, drawWidth, drawHeight);
        texture.needsUpdate = true;
        if (!onlineReported) {
          onlineReported = true;
          this.onBasemapSource?.("online");
        }
        resolve();
      };
      image.onerror = () => resolve();
      image.src = `https://tile.openstreetmap.org/${zoom}/${wrappedX}/${y}.png`;
    });
    const tasks: Array<() => Promise<void>> = [];
    for (let x = firstX; x <= lastX; x += 1)
      for (let y = firstY; y <= lastY; y += 1)
        tasks.push(() => loadTile(x, y));
    let cursor = 0;
    const worker = async () => {
      while (cursor < tasks.length) {
        const task = tasks[cursor++];
        if (task) await task();
      }
    };
    await Promise.all(Array.from({ length: Math.min(6, tasks.length) }, worker));
  }

  private createRoads(paths: Vector3[][]): void {
    const roadEdge = this.roadGeometry(paths, 4.2);
    const asphalt = this.roadGeometry(paths, 3.45);
    const center = this.roadGeometry(paths, 0.24);
    // GIS tiles carry the physical road appearance. These meshes only retain
    // a restrained cyan route cue for the digital-twin layer.
    const edgeMaterial = new MeshStandardMaterial({ color: 0x0a6290, emissive: 0x0c86b4, emissiveIntensity: 0.75, roughness: 0.42, metalness: 0.55, side: DoubleSide, transparent: true, opacity: 0.34 });
    const roadMaterial = new MeshStandardMaterial({ color: 0x071b2e, emissive: 0x04192a, emissiveIntensity: 0.45, roughness: 0.72, metalness: 0.4, side: DoubleSide, transparent: true, opacity: 0.22 });
    const centerMaterial = new MeshStandardMaterial({ color: 0x52e5ff, emissive: 0x13a9d4, emissiveIntensity: 1.15, roughness: 0.22, metalness: 0.62, side: DoubleSide, transparent: true, opacity: 0.62 });
    edgeMaterial.userData.gisAboveOpacity = 0.34;
    roadMaterial.userData.gisAboveOpacity = 0.22;
    centerMaterial.userData.gisAboveOpacity = 0.62;
    edgeMaterial.userData.gisAboveTransparent = true;
    roadMaterial.userData.gisAboveTransparent = true;
    centerMaterial.userData.gisAboveTransparent = true;
    this.materials.push(edgeMaterial, roadMaterial, centerMaterial);
    const edgeMesh = new Mesh(roadEdge, edgeMaterial);
    edgeMesh.name = "gis-road-edges";
    edgeMesh.position.y = 0.22;
    const roadMesh = new Mesh(asphalt, roadMaterial);
    roadMesh.name = "gis-road-network";
    roadMesh.position.y = 0.26;
    const centerMesh = new Mesh(center, centerMaterial);
    centerMesh.name = "gis-road-guides";
    centerMesh.position.y = 0.3;
    this.group.add(edgeMesh, roadMesh, centerMesh);
    this.roadMeshes.push(edgeMesh, roadMesh, centerMesh);
    const visible = this.mode !== "underground";
    edgeMesh.visible = visible;
    roadMesh.visible = visible;
    centerMesh.visible = visible;
  }

  private perimeterRoad(): Vector3[] {
    return [
      new Vector3(-52, 0, -39), new Vector3(52, 0, -39),
      new Vector3(52, 0, 39), new Vector3(-52, 0, 39),
      new Vector3(-52, 0, -39),
    ];
  }

  private roadGeometry(paths: Vector3[][], width: number): BufferGeometry {
    const vertices: number[] = [];
    for (const path of paths) {
      for (let index = 1; index < path.length; index += 1) {
        const from = path[index - 1]!;
        const to = path[index]!;
        // Public road ways often continue far outside the selected park. Keep
        // only local segments so the shared camera frames the campus itself.
        if (!this.inside(from) || !this.inside(to)) continue;
        const direction = new Vector3().subVectors(to, from);
        direction.y = 0;
        if (direction.lengthSq() < 0.0001) continue;
        direction.normalize();
        const normal = new Vector3(-direction.z, 0, direction.x).multiplyScalar(width / 2);
        const a = from.clone().add(normal), b = from.clone().sub(normal);
        const c = to.clone().sub(normal), d = to.clone().add(normal);
        vertices.push(a.x, 0, a.z, b.x, 0, b.z, c.x, 0, c.z, a.x, 0, a.z, c.x, 0, c.z, d.x, 0, d.z);
      }
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new Float32BufferAttribute(vertices, 3));
    geometry.computeVertexNormals();
    return geometry;
  }

  private createBuildings(entries: { footprint: Vector3[]; feature: GeoFeature }[]): void {
    const walls = new MeshStandardMaterial({ color: 0x0c3656, emissive: 0x062e4a, emissiveIntensity: 0.58, roughness: 0.43, metalness: 0.48 });
    const roof = new MeshStandardMaterial({ color: 0x167a9a, emissive: 0x0c6688, emissiveIntensity: 0.85, roughness: 0.3, metalness: 0.62 });
    const edge = new LineBasicMaterial({ color: 0x37d9ff, transparent: true, opacity: 0.72 });
    const windows = new LineBasicMaterial({ color: 0x86efff, transparent: true, opacity: 0.68 });
    this.materials.push(walls, roof, edge, windows);
    const windowVertices: number[] = [];
    // The public extract has limited height tags. Promote only three central
    // real footprints to landmark towers, giving the GIS core a readable urban
    // skyline without replacing it with arbitrary non-geographic boxes.
    const landmarkHeights = new Map<string, number>();
    entries
      .map(({ footprint, feature }) => {
        const vertices = footprint.slice(0, -1);
        const center = vertices.reduce((sum, point) => sum.add(point), new Vector3()).multiplyScalar(1 / Math.max(1, vertices.length));
        return { identity: feature.properties?.osmId ?? `${footprint[0]?.x}-${footprint[0]?.z}`, distance: Math.hypot(center.x, center.z) };
      })
      .sort((left, right) => left.distance - right.distance)
      .slice(0, 3)
      .forEach((entry, index) => landmarkHeights.set(entry.identity, [18, 15.5, 13.5][index]!));
    for (const { footprint, feature } of entries) {
      const shape = new Shape();
      footprint.forEach((point, index) => {
        if (index === 0) shape.moveTo(point.x, -point.z);
        else shape.lineTo(point.x, -point.z);
      });
      const source = feature.properties ?? {};
      const levels = Number(source.levels ?? 0);
      const declaredHeight = Number(source.height ?? 0);
      const identity = source.osmId ?? `${footprint[0]?.x}-${footprint[0]?.z}`;
      const floors = Number.isFinite(levels) && levels > 0 ? levels : 4 + (stableNumber(identity) % 10);
      // Keep the public OSM context legible beside the project's highlighted
      // operating buildings. This is a visual vertical exaggeration only:
      // actual OSM heights remain source data, while small surrounding blocks
      // receive a 4.6m readable minimum and a restrained 20m maximum.
      const sourceHeight = Number.isFinite(declaredHeight) && declaredHeight > 0 ? declaredHeight : floors * 3.6;
      const height = Math.max(landmarkHeights.get(identity) ?? 0, Math.min(20, Math.max(4.6, sourceHeight * SCALE * 1.45)));
      const geometry = new ExtrudeGeometry(shape, { depth: height, bevelEnabled: false, steps: 1 });
      geometry.rotateX(-Math.PI / 2);
      const mesh = new Mesh(geometry, [walls, roof]);
      mesh.name = `gis-building-${identity}`;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const outline = new LineSegments(new EdgesGeometry(geometry), edge);
      outline.name = `gis-building-outline-${identity}`;
      outline.raycast = () => {};
      this.group.add(mesh, outline);
      this.addFacadeWindows(windowVertices, footprint, height, landmarkHeights.has(identity) ? Math.max(floors, 9) : floors);
    }
    this.createCentralLandmarkTowers(windowVertices, walls, roof, edge);
    const windowGeometry = new BufferGeometry();
    windowGeometry.setAttribute("position", new Float32BufferAttribute(windowVertices, 3));
    const facadeWindows = new LineSegments(windowGeometry, windows);
    facadeWindows.name = "gis-building-facade-windows";
    facadeWindows.raycast = () => {};
    this.group.add(facadeWindows);
  }

  /**
   * The public OSM slice has incomplete height tags. These three clearly
   * marked centre and perimeter towers give the shared digital-twin a legible
   * skyline while retaining the surrounding OSM roads and footprint context.
   */
  private createCentralLandmarkTowers(
    windowVertices: number[],
    walls: MeshStandardMaterial,
    roof: MeshStandardMaterial,
    edge: LineBasicMaterial,
  ): void {
    const towers = [
      { id: "central-tower-01", x: -5.4, z: 0.8, width: 6.8, depth: 7.4, height: 25, floors: 13 },
      { id: "central-tower-02", x: 4.4, z: 4.5, width: 5.7, depth: 6.2, height: 20, floors: 10 },
      { id: "central-tower-03", x: -1.2, z: 10.2, width: 5.2, depth: 5.8, height: 16.5, floors: 8 },
      // Perimeter business towers frame the campus without competing with the
      // three central landmarks or the labelled operating buildings.
      { id: "perimeter-tower-west", x: -55, z: 5.5, width: 5.5, depth: 6.4, height: 18, floors: 9 },
      { id: "perimeter-tower-east", x: 54, z: 3.8, width: 6.1, depth: 6.8, height: 19, floors: 10 },
      { id: "perimeter-tower-north", x: 2.5, z: 48, width: 6.4, depth: 6, height: 17, floors: 9 },
      { id: "perimeter-tower-south", x: 1.5, z: -48, width: 5.8, depth: 6.2, height: 16, floors: 8 },
    ];
    towers.forEach((tower) => {
      const halfWidth = tower.width / 2, halfDepth = tower.depth / 2;
      const footprint = [
        new Vector3(tower.x - halfWidth, 0, tower.z - halfDepth),
        new Vector3(tower.x + halfWidth, 0, tower.z - halfDepth),
        new Vector3(tower.x + halfWidth, 0, tower.z + halfDepth),
        new Vector3(tower.x - halfWidth, 0, tower.z + halfDepth),
        new Vector3(tower.x - halfWidth, 0, tower.z - halfDepth),
      ];
      const shape = new Shape();
      footprint.forEach((point, index) => {
        if (index === 0) shape.moveTo(point.x, -point.z);
        else shape.lineTo(point.x, -point.z);
      });
      const geometry = new ExtrudeGeometry(shape, { depth: tower.height, bevelEnabled: false, steps: 1 });
      geometry.rotateX(-Math.PI / 2);
      const towerMesh = new Mesh(geometry, [walls, roof]);
      towerMesh.name = `gis-${tower.id}`;
      towerMesh.castShadow = true;
      towerMesh.receiveShadow = true;
      const outline = new LineSegments(new EdgesGeometry(geometry), edge);
      outline.name = `gis-${tower.id}-outline`;
      outline.raycast = () => {};
      this.group.add(towerMesh, outline);
      this.addFacadeWindows(windowVertices, footprint, tower.height, tower.floors);
    });
  }

  /**
   * A landscape plan, rather than decoration scattered around every footprint:
   * short roadside avenues, a few courtyard clusters, and narrow planted beds.
   * The public OSM extract has no authoritative tree survey, so every element
   * remains a visual context layer rather than an asserted real-world asset.
   */
  private createVegetation(footprints: Vector3[][], roads: Vector3[][]): void {
    type TreePoint = { x: number; z: number; angle: number; scale: number; bed: boolean };
    const points: TreePoint[] = [];
    const clearOfBuilding = (x: number, z: number) => {
      if (PROJECT_BUILDING_EXCLUSIONS.some((area) => x > area.minX && x < area.maxX && z > area.minZ && z < area.maxZ)) return false;
      return !footprints.some((footprint) => {
      const vertices = footprint.slice(0, -1);
      const xs = vertices.map((point) => point.x), zs = vertices.map((point) => point.z);
      // Flower beds extend farther than a trunk, hence this 5m no-plant buffer.
      return x > Math.min(...xs) - 5 && x < Math.max(...xs) + 5 && z > Math.min(...zs) - 5 && z < Math.max(...zs) + 5;
      });
    };
    const add = (x: number, z: number, angle: number, scale: number, bed: boolean) => {
      if (points.length >= 32 || !this.inside(new Vector3(x, 0, z)) || !clearOfBuilding(x, z)) return;
      if (points.some((point) => Math.hypot(point.x - x, point.z - z) < 5.8)) return;
      points.push({ x, z, angle, scale, bed });
    };

    // Place trees in regular rows beside public road segments, never across the
    // whole parcel perimeter. The final appended perimeter route is excluded.
    roads.slice(0, -1).forEach((path, pathIndex) => {
      for (let index = 1; index < path.length; index += 1) {
        const from = path[index - 1]!, to = path[index]!;
        if (!this.inside(from) || !this.inside(to)) continue;
        const direction = new Vector3().subVectors(to, from); direction.y = 0;
        const length = direction.length();
        if (length < 9) continue;
        direction.normalize();
        const normal = new Vector3(-direction.z, 0, direction.x);
        const steps = Math.min(3, Math.floor(length / 13));
        for (let step = 1; step <= steps; step += 1) {
          const position = from.clone().lerp(to, step / (steps + 1));
          const side = (pathIndex + step) % 2 === 0 ? 1 : -1;
          position.addScaledVector(normal, 3.9 * side);
          add(position.x, position.z, Math.atan2(direction.z, direction.x), 0.78 + ((pathIndex + step) % 3) * 0.07, (pathIndex + step) % 3 === 0);
        }
      }
    });
    // Small, deliberate courtyard groups inside the real building cluster.
    footprints.filter((_, index) => index % 11 === 0).forEach((footprint, index) => {
      const vertices = footprint.slice(0, -1);
      if (!vertices.length) return;
      const center = vertices.reduce((sum, point) => sum.add(point), new Vector3()).multiplyScalar(1 / vertices.length);
      const angle = index * 1.83;
      add(center.x + Math.cos(angle) * 5.5, center.z + Math.sin(angle) * 5.5, angle, 0.82, true);
    });

    const bedMaterial = new MeshStandardMaterial({ color: 0x0e6658, emissive: 0x063a33, emissiveIntensity: 0.4, roughness: 0.95, transparent: true, opacity: 0.7 });
    const trunkMaterial = new MeshStandardMaterial({ color: 0x3c5c52, roughness: 1 });
    const canopyMaterial = new MeshStandardMaterial({ color: 0x3e907c, emissive: 0x105e53, emissiveIntensity: 0.33, roughness: 0.9, flatShading: true });
    const pinkFlowerMaterial = new MeshStandardMaterial({ color: 0xff6fae, emissive: 0xa91d64, emissiveIntensity: 0.7, roughness: 0.42 });
    const goldFlowerMaterial = new MeshStandardMaterial({ color: 0xffc94f, emissive: 0xb76a0b, emissiveIntensity: 0.65, roughness: 0.42 });
    const whiteFlowerMaterial = new MeshStandardMaterial({ color: 0xf2fbff, emissive: 0x8ad8e8, emissiveIntensity: 0.55, roughness: 0.3 });
    this.materials.push(bedMaterial, trunkMaterial, canopyMaterial, pinkFlowerMaterial, goldFlowerMaterial, whiteFlowerMaterial);
    const beds = new InstancedMesh(new PlaneGeometry(1, 1), bedMaterial, points.filter((point) => point.bed).length);
    const bedCount = points.filter((point) => point.bed).length;
    // Three small flower species per designed bed make the landscape read as a
    // planted garden, not an uninterrupted field of green circles.
    // These use an overview camera, so individual botanical-scale blossoms are
    // invisible. Make each instance a compact flower cluster: still smaller
    // than a tree, but legible as a coloured planted band at campus scale.
    // Ordered strips read as designed flowering borders at the overview scale;
    // random sphere-like blooms read as visual noise from the same camera.
    const pinkFlowers = new InstancedMesh(new PlaneGeometry(1, 1), pinkFlowerMaterial, bedCount);
    const goldFlowers = new InstancedMesh(new PlaneGeometry(1, 1), goldFlowerMaterial, bedCount);
    const whiteFlowers = new InstancedMesh(new PlaneGeometry(1, 1), whiteFlowerMaterial, bedCount);
    const trunks = new InstancedMesh(new CylinderGeometry(0.16, 0.25, 2.1, 6), trunkMaterial, points.length);
    const crowns = new InstancedMesh(new IcosahedronGeometry(1, 1), canopyMaterial, points.length);
    const pose = new Object3D();
    const tint = new Color();
    let bedIndex = 0;
    points.forEach((item, index) => {
      if (item.bed) {
        pose.position.set(item.x, 0.14, item.z); pose.rotation.set(-Math.PI / 2, 0, item.angle); pose.scale.set(7.2, 1.65, 1); pose.updateMatrix(); beds.setMatrixAt(bedIndex, pose.matrix);
        const stripe = (offset: number, target: InstancedMesh) => {
          const x = item.x - Math.sin(item.angle) * offset;
          const z = item.z + Math.cos(item.angle) * offset;
          pose.position.set(x, 0.18, z); pose.rotation.set(-Math.PI / 2, 0, item.angle); pose.scale.set(5.85, 0.32, 1); pose.updateMatrix(); target.setMatrixAt(bedIndex, pose.matrix);
        };
        stripe(-0.48, pinkFlowers); stripe(0, goldFlowers); stripe(0.48, whiteFlowers);
        bedIndex += 1;
      }
      pose.position.set(item.x, 1.15 * item.scale, item.z); pose.rotation.set(0, 0, 0); pose.scale.set(item.scale, item.scale, item.scale); pose.updateMatrix(); trunks.setMatrixAt(index, pose.matrix);
      pose.position.set(item.x, 2.95 * item.scale, item.z); pose.scale.set(1.4 * item.scale, 1.85 * item.scale, 1.32 * item.scale); pose.rotation.y = index * 0.63; pose.updateMatrix(); crowns.setMatrixAt(index, pose.matrix);
      tint.setHex(index % 3 === 0 ? 0x74c69a : index % 3 === 1 ? 0x55b58f : 0x3b987e); crowns.setColorAt(index, tint);
    });
    [beds, pinkFlowers, goldFlowers, whiteFlowers, trunks, crowns].forEach((mesh) => { mesh.castShadow = mesh === trunks || mesh === crowns; mesh.receiveShadow = mesh !== crowns; mesh.instanceMatrix.needsUpdate = true; });
    crowns.instanceColor!.needsUpdate = true;
    this.vegetation.add(beds, pinkFlowers, goldFlowers, whiteFlowers, trunks, crowns);
    this.vegetation.visible = this.mode !== "underground";
    this.group.add(this.vegetation);
  }

  /** Small GIS footprints receive a light window grid too, so they read as
   * occupied buildings instead of anonymous map blocks. */
  private addFacadeWindows(vertices: number[], footprint: Vector3[], height: number, floors: number): void {
    const visualFloors = Math.max(2, Math.min(10, floors));
    const rowHeight = height / (visualFloors + 1);
    for (let index = 1; index < footprint.length; index += 1) {
      const from = footprint[index - 1]!;
      const to = footprint[index]!;
      const length = from.distanceTo(to);
      if (length < 0.9) continue;
      const panes = Math.max(1, Math.min(6, Math.floor(length / 1.45)));
      for (let floor = 1; floor <= visualFloors; floor += 1) {
        const y = floor * rowHeight;
        vertices.push(from.x, y, from.z, to.x, y, to.z);
      }
      for (let pane = 1; pane < panes; pane += 1) {
        const point = from.clone().lerp(to, pane / panes);
        vertices.push(point.x, rowHeight * 0.35, point.z, point.x, height - rowHeight * 0.35, point.z);
      }
    }
  }

  setMode(mode: SceneMode): void {
    this.mode = mode;
    const underground = mode === "underground";
    // A transparent map plane still visually competes with pipes through alpha
    // compositing. Underground is a cutaway view: hide the surface entirely,
    // retain only ghosted building volumes as spatial reference.
    if (this.sitePlan) this.sitePlan.visible = !underground;
    for (const road of this.roadMeshes) road.visible = !underground;
    this.vegetation.visible = !underground;
    for (const material of this.materials) {
      material.transparent = underground || material.userData.gisAboveTransparent === true;
      const aboveOpacity = Number(material.userData.gisAboveOpacity ?? (material instanceof LineBasicMaterial ? 0.72 : 1));
      material.opacity = underground
        ? material instanceof LineBasicMaterial ? 0.3 : 0.18
        : aboveOpacity;
      material.depthWrite = !underground;
      material.needsUpdate = true;
    }
    this.applyVisibility();
  }

  /** Keeps the optional real-GIS layer available without forcing it into the
   * focused original park scene used by the default product presentation. */
  setContextEnabled(enabled: boolean): void {
    this.contextEnabled = enabled;
    this.applyVisibility();
  }

  get isReady(): boolean { return this.loaded; }

  getBounds(): Box3 {
    return this.bounds.clone();
  }

  private applyVisibility(): void {
    this.group.visible = this.loaded && this.contextEnabled;
  }

  dispose(): void {
    this.disposed = true;
    disposeObject(this.group);
    this.planTexture?.dispose();
    this.materials.length = 0;
  }
}
