import { BoxGeometry, Color, CylinderGeometry, GridHelper, Group, IcosahedronGeometry, InstancedMesh, Mesh, MeshBasicMaterial, MeshStandardMaterial, Object3D, TorusGeometry } from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { riskLabels, type BuildingAssetData, type BuildingEntry, type BuildingMetadata, type SceneMode } from "../types/scene";
import { disposeObject } from "../utils/dispose";

/** Original focused park base, streets, plazas and instanced landscaping. */
export class ParkEnvironment {
  readonly group = new Group();
  /** Visual context assets exposed as ordinary pickable building entries. */
  readonly entries: BuildingEntry[] = [];
  private readonly surfaces: { material: MeshStandardMaterial; opacity: number }[] = [];
  private readonly foliage = new Group();
  private readonly furniture = new Group();
  private readonly districtBuildings = new Group();
  private hovered: Group | null = null;
  private selected: Group | null = null;
  private readonly buildingFocus = new Map<Group, Mesh<BoxGeometry, MeshBasicMaterial>>();
  private readonly buildingLabels = new Map<Group, CSS2DObject>();
  private districtPalette?: { body: MeshStandardMaterial; roof: MeshStandardMaterial; trim: MeshStandardMaterial; glass: MeshStandardMaterial };
  private readonly boxGeometry = new BoxGeometry(1, 1, 1);

  constructor() {
    this.group.name = "park-environment";
    this.foliage.name = "park-instanced-trees";
    this.furniture.name = "park-street-furniture";
    this.districtBuildings.name = "park-expansion-buildings";
    const ground = this.material(0x07182c, 0x03101f);
    const edge = this.material(0x0e5f87, 0x064563);
    const road = this.material(0x0a2138, 0x03101f);
    const walkway = this.material(0x17445f, 0x082b43);
    const grass = this.material(0x0b4f50, 0x063638);
    const plaza = this.material(0x113c59, 0x082f4b);
    const lane = this.material(0x4ddcff, 0x139bc3);
    const inset = this.material(0x081e35, 0x041326);
    // Keep the original core untouched, then frame it with a connected
    // science-park district. 256 × 206 is just over five times the old
    // 114 × 92 site area, without changing the scene coordinate system.
    this.box(ground, 256, 0.9, 206, 0, -0.55, 0);
    this.box(edge, 256, 0.18, 0.35, 0, 0.01, -103);
    this.box(edge, 256, 0.18, 0.35, 0, 0.01, 103);
    this.box(edge, 0.35, 0.18, 206, -128, 0.01, 0);
    this.box(edge, 0.35, 0.18, 206, 128, 0.01, 0);
    for (const x of [-29, 29]) for (const z of [-24, 24]) {
      this.box(walkway, 45, 0.14, 35, x, 0, z);
      this.box(grass, 41, 0.12, 31, x, 0.11, z);
    }
    this.box(road, 114, 0.07, 10, 0, 0, 0);
    this.box(road, 9, 0.07, 69, 0, 0, -11.5);
    this.box(lane, 112, 0.02, 0.12, 0, 0.05, -4.2);
    this.box(lane, 112, 0.02, 0.12, 0, 0.05, 4.2);
    this.box(lane, 0.1, 0.02, 67, -3.6, 0.05, -11.5);
    this.box(lane, 0.1, 0.02, 67, 3.6, 0.05, -11.5);
    this.box(plaza, 23, 0.16, 18, 0, 0.03, 33);
    this.box(inset, 17.5, 0.02, 12.5, 0, 0.125, 33);
    this.box(walkway, 12, 0.12, 4, 0, 0.03, 44);
    const paving = new InstancedMesh(this.boxGeometry, plaza, 48);
    const pose = new Object3D();
    let tile = 0;
    for (let row = 0; row < 6; row++) for (let column = 0; column < 8; column++) {
      pose.position.set(-7.45 + column * 2.12, 0.15, 27.8 + row * 2.08);
      pose.scale.set(1.98, 0.025, 1.94); pose.updateMatrix(); paving.setMatrixAt(tile++, pose.matrix);
    }
    this.group.add(paving);
    this.createRoadMarkings(lane);
    this.createParkExtension({ road, walkway, grass, plaza, lane, edge, inset });
    this.createDistrictBuildings();
    this.createTrees();
    this.createDistrictTrees();
    this.createFlowerBeds();
    this.createFurniture();
    this.createDistrictLighting();
    const grid = new GridHelper(300, 100, 0x42647c, 0x2d485e);
    grid.position.y = -1.1; grid.material.transparent = true; grid.material.opacity = 0.15; grid.material.depthWrite = false;
    this.group.add(grid, this.districtBuildings, this.foliage, this.furniture);
  }

  private material(color: number, emissive = 0x000000): MeshStandardMaterial {
    const material = new MeshStandardMaterial({ color, emissive, emissiveIntensity: 0.28, roughness: 0.87, metalness: 0.1 });
    this.surfaces.push({ material, opacity: 1 }); return material;
  }

  private box(material: MeshStandardMaterial, width: number, height: number, depth: number, x: number, y: number, z: number): Mesh {
    const mesh = new Mesh(this.boxGeometry, material);
    mesh.position.set(x, y, z); mesh.scale.set(width, height, depth); mesh.receiveShadow = true; this.group.add(mesh); return mesh;
  }

  private createRoadMarkings(material: MeshStandardMaterial): void {
    const transforms: { x: number; z: number; width: number; depth: number }[] = [];
    for (let x = -53; x <= 53; x += 5) if (Math.abs(x) > 7) transforms.push({ x, z: 0, width: 2.1, depth: 0.12 });
    for (let z = -42; z <= 20; z += 5) if (Math.abs(z) > 7) transforms.push({ x: 0, z, width: 0.12, depth: 2.1 });
    for (let x = -3; x <= 3; x += 1) { transforms.push({ x, z: 7, width: 0.55, depth: 2.1 }); transforms.push({ x, z: -7, width: 0.55, depth: 2.1 }); }
    for (let z = -3; z <= 3; z += 1) { transforms.push({ x: -7, z, width: 2.1, depth: 0.55 }); transforms.push({ x: 7, z, width: 2.1, depth: 0.55 }); }
    const mesh = new InstancedMesh(this.boxGeometry, material, transforms.length);
    const pose = new Object3D();
    transforms.forEach((transform, index) => { pose.position.set(transform.x, 0.058, transform.z); pose.scale.set(transform.width, 0.025, transform.depth); pose.updateMatrix(); mesh.setMatrixAt(index, pose.matrix); });
    this.group.add(mesh);
  }

  /**
   * A connected outer district rather than copied building blocks. The existing
   * four-building core remains in the middle; this layer supplies the access,
   * public and parking infrastructure expected around a technology campus.
   */
  private createParkExtension(materials: {
    road: MeshStandardMaterial; walkway: MeshStandardMaterial; grass: MeshStandardMaterial;
    plaza: MeshStandardMaterial; lane: MeshStandardMaterial; edge: MeshStandardMaterial; inset: MeshStandardMaterial;
  }): void {
    const { road, walkway, grass, plaza, lane, edge, inset } = materials;
    // Outer circulation road: four connected sides plus two north/south
    // branches that tie directly into the original central avenue.
    this.box(road, 210, 0.07, 10, 0, 0, -76);
    this.box(road, 210, 0.07, 10, 0, 0, 76);
    this.box(road, 10, 0.07, 162, -100, 0, 0);
    this.box(road, 10, 0.07, 162, 100, 0, 0);
    this.box(road, 10, 0.07, 72, -63, 0, -37);
    this.box(road, 10, 0.07, 72, 63, 0, 37);
    this.box(road, 72, 0.07, 8, -32, 0, 56);
    this.box(road, 72, 0.07, 8, 32, 0, -56);

    // Perimeter lane cues retain the existing cyan visual language.
    this.box(lane, 204, 0.02, 0.14, 0, 0.05, -79.2);
    this.box(lane, 204, 0.02, 0.14, 0, 0.05, 79.2);
    this.box(lane, 0.14, 0.02, 156, -103.2, 0.05, 0);
    this.box(lane, 0.14, 0.02, 156, 103.2, 0.05, 0);
    const outerMarks: { x: number; z: number; width: number; depth: number }[] = [];
    for (let x = -92; x <= 92; x += 7) { outerMarks.push({ x, z: -76, width: 2.6, depth: 0.14 }, { x, z: 76, width: 2.6, depth: 0.14 }); }
    for (let z = -65; z <= 65; z += 7) { outerMarks.push({ x: -100, z, width: 0.14, depth: 2.6 }, { x: 100, z, width: 0.14, depth: 2.6 }); }
    this.instancePaving(outerMarks, lane, 0.06);

    // North central civic plaza and two smaller pocket parks create a hierarchy
    // of public space around the original north plaza rather than a blank field.
    this.box(plaza, 42, 0.16, 30, 0, 0.03, 68);
    this.box(inset, 32, 0.02, 20, 0, 0.125, 68);
    this.box(walkway, 54, 0.13, 7, 0, 0.03, 52);
    this.box(grass, 42, 0.12, 32, -67, 0.05, 43);
    this.box(grass, 42, 0.12, 32, 67, 0.05, -43);
    this.box(walkway, 32, 0.12, 22, -67, 0.01, 43);
    this.box(walkway, 32, 0.12, 22, 67, 0.01, -43);
    this.box(grass, 58, 0.12, 22, -47, 0.05, -68);
    this.box(grass, 58, 0.12, 22, 47, 0.05, 68);
    this.box(walkway, 34, 0.1, 4, -47, 0.03, -68);
    this.box(walkway, 34, 0.1, 4, 47, 0.03, 68);

    // Two ground car parks face the perimeter road. Rows are generated as a
    // single instanced marking set, keeping draw calls controlled.
    this.createParkingArea(-72, -49, 38, 31, road, lane, edge, "west");
    this.createParkingArea(72, 49, 38, 31, road, lane, edge, "east");
    // Main arrival forecourt / parking entrance at the southern ring road.
    this.box(walkway, 28, 0.12, 16, 0, 0.02, -76);
    this.box(edge, 18, 0.22, 0.45, 0, 0.13, -83.5);
    this.box(lane, 5.2, 0.03, 0.22, -5.4, 0.22, -76);
    this.box(lane, 5.2, 0.03, 0.22, 5.4, 0.22, -76);

    // Circular resting spaces make the larger site read as a campus landscape.
    const seatingMaterial = new MeshStandardMaterial({ color: 0x295e76, emissive: 0x123f55, emissiveIntensity: 0.32, roughness: 0.55, metalness: 0.28 });
    const glowMaterial = new MeshStandardMaterial({ color: 0x83ecf3, emissive: 0x32cbd5, emissiveIntensity: 0.7, roughness: 0.25, metalness: 0.42 });
    this.surfaces.push({ material: seatingMaterial, opacity: 1 }, { material: glowMaterial, opacity: 1 });
    for (const [x, z] of [[-67, 43], [67, -43], [0, 68]] as [number, number][]) {
      const deck = new Mesh(new CylinderGeometry(5.5, 5.5, 0.2, 28), seatingMaterial);
      deck.position.set(x, 0.28, z); deck.receiveShadow = true;
      const ring = new Mesh(new TorusGeometry(2.2, 0.12, 6, 24), glowMaterial);
      ring.position.set(x, 0.55, z); ring.rotation.x = Math.PI / 2;
      this.furniture.add(deck, ring);
    }
  }

  private createParkingArea(x: number, z: number, width: number, depth: number, road: MeshStandardMaterial, lane: MeshStandardMaterial, edge: MeshStandardMaterial, name: string): void {
    this.box(road, width, 0.1, depth, x, 0.01, z);
    this.box(edge, width + 1, 0.12, 0.3, x, 0.07, z - depth / 2);
    this.box(edge, width + 1, 0.12, 0.3, x, 0.07, z + depth / 2);
    const markings: { x: number; z: number; width: number; depth: number }[] = [];
    for (let row = -1; row <= 1; row += 2) {
      const rowZ = z + row * 8;
      for (let column = -15; column <= 15; column += 3.5) markings.push({ x: x + column, z: rowZ, width: 0.09, depth: 4.6 });
      markings.push({ x, z: rowZ, width: 34, depth: 0.13 });
    }
    this.instancePaving(markings, lane, 0.08, `parking-${name}-markings`);
  }

  private instancePaving(transforms: { x: number; z: number; width: number; depth: number }[], material: MeshStandardMaterial, y: number, name = "district-road-markings"): void {
    const mesh = new InstancedMesh(this.boxGeometry, material, transforms.length);
    const pose = new Object3D();
    transforms.forEach((item, index) => {
      pose.position.set(item.x, y, item.z); pose.scale.set(item.width, 0.02, item.depth); pose.updateMatrix(); mesh.setMatrixAt(index, pose.matrix);
    });
    mesh.name = name; this.group.add(mesh);
  }

  /**
   * Twenty programmatic context buildings form three deliberately irregular
   * planning zones: peripheral R&D offices, lower research blocks and a public
   * service frontage. They are visual campus context only; the four original
   * interactive buildings remain the project's operating assets.
   */
  private createDistrictBuildings(): void {
    type Category = "office" | "lab" | "amenity" | "service";
    type Definition = { id: string; category: Category; x: number; z: number; width: number; depth: number; height: number };
    const buildings: Definition[] = [
      // A 类：外围研发办公区，10–20 层的不同高度形成园区天际线。
      { id: "A01", category: "office", x: -84, z: -17, width: 13, depth: 11, height: 52 },
      { id: "A02", category: "office", x: -80, z: 20, width: 15, depth: 12, height: 41 },
      { id: "A03", category: "office", x: 83, z: -18, width: 14, depth: 12, height: 46 },
      { id: "A04", category: "office", x: 86, z: 20, width: 12, depth: 13, height: 36 },
      { id: "A05", category: "office", x: -43, z: -63, width: 16, depth: 13, height: 38 },
      { id: "A06", category: "office", x: 40, z: -64, width: 12, depth: 14, height: 44 },
      { id: "A07", category: "office", x: -39, z: 67, width: 14, depth: 12, height: 34 },
      { id: "A08", category: "office", x: 40, z: 67, width: 16, depth: 11, height: 40 },
      // B 类：中低层实验研发楼，围绕研发办公区形成灵活的组团。
      { id: "B01", category: "lab", x: -62, z: -17, width: 17, depth: 13, height: 18 },
      { id: "B02", category: "lab", x: -59, z: 28, width: 19, depth: 14, height: 16 },
      { id: "B03", category: "lab", x: 61, z: -27, width: 18, depth: 12, height: 17 },
      { id: "B04", category: "lab", x: 61, z: 30, width: 20, depth: 14, height: 19 },
      { id: "B05", category: "lab", x: -19, z: -64, width: 18, depth: 12, height: 15 },
      { id: "B06", category: "lab", x: 17, z: 67, width: 19, depth: 13, height: 17 },
      // C 类：公共服务区沿中央广场和南入口布置。
      { id: "C01-CANTEEN", category: "amenity", x: -25, z: 81, width: 23, depth: 15, height: 11 },
      { id: "C02-INNOVATION", category: "amenity", x: 28, z: 81, width: 20, depth: 16, height: 14 },
      { id: "C03-EXHIBITION", category: "amenity", x: -28, z: -86, width: 22, depth: 13, height: 10 },
      { id: "C04-CLUB", category: "amenity", x: 29, z: -86, width: 18, depth: 14, height: 9 },
      // D 类：入口服务设施，尺度低且贴近南侧到达空间。
      { id: "D01-GATE", category: "service", x: -10, z: -91, width: 10, depth: 6, height: 5 },
      { id: "D02-SERVICE", category: "service", x: 12, z: -91, width: 15, depth: 8, height: 7 },
    ];
    const body = new MeshStandardMaterial({ color: 0x103a60, emissive: 0x082c49, emissiveIntensity: 0.52, roughness: 0.38, metalness: 0.54 });
    const roof = new MeshStandardMaterial({ color: 0x0a2948, emissive: 0x061d35, emissiveIntensity: 0.55, roughness: 0.3, metalness: 0.62 });
    const trim = new MeshStandardMaterial({ color: 0x2bd4f2, emissive: 0x0b8eaf, emissiveIntensity: 0.82, roughness: 0.22, metalness: 0.62 });
    const glass = new MeshStandardMaterial({ color: 0x68e8ff, emissive: 0x129dcb, emissiveIntensity: 0.92, roughness: 0.15, metalness: 0.64 });
    this.districtPalette = { body, roof, trim, glass };
    this.surfaces.push({ material: body, opacity: 1 }, { material: roof, opacity: 1 }, { material: trim, opacity: 1 }, { material: glass, opacity: 1 });
    const windows: { x: number; y: number; z: number; rotate: boolean; scaleX: number; scaleY: number }[] = [];
    for (const item of buildings) {
      const metadata = this.districtMetadata(item);
      const object = new Group();
      object.name = `district-building-${item.id.toLowerCase()}`;
      object.position.set(item.x, 0, item.z);
      const building: BuildingAssetData = {
        id: `building_${String(this.entries.length + 6).padStart(3, "0")}`,
        name: metadata.name, type: metadata.typeLabel, floors: metadata.floors,
        status: "正常", riskLevel: riskLabels[metadata.risk], position: [item.x, 0, item.z],
      };
      object.userData = { buildingId: metadata.id, metadata, building };
      this.entries.push({ object, metadata });
      this.districtBuildings.add(object);
      const baseHeight = item.category === "service" ? 0.5 : 0.75;
      const foundation = new Mesh(this.boxGeometry, roof);
      foundation.position.set(0, baseHeight / 2, 0); foundation.scale.set(item.width + 1.4, baseHeight, item.depth + 1.4);
      const mass = new Mesh(this.boxGeometry, body);
      mass.position.set(0, baseHeight + item.height / 2, 0); mass.scale.set(item.width, item.height, item.depth); mass.castShadow = true; mass.receiveShadow = true;
      const crown = new Mesh(this.boxGeometry, trim);
      crown.position.set(0, baseHeight + item.height + 0.28, 0); crown.scale.set(item.width + 0.6, 0.38, item.depth + 0.6);
      const roofPlate = new Mesh(this.boxGeometry, roof);
      roofPlate.position.set(0, baseHeight + item.height + 0.62, 0); roofPlate.scale.set(Math.max(3, item.width - 1.5), 0.32, Math.max(3, item.depth - 1.5));
      const roofUnit = new Mesh(this.boxGeometry, roof);
      roofUnit.position.set(Math.min(2, item.width * 0.16), baseHeight + item.height + 1.35, -Math.min(1.6, item.depth * 0.14));
      roofUnit.scale.set(Math.max(2.2, item.width * 0.28), 1.2, Math.max(1.8, item.depth * 0.24));
      const canopy = new Mesh(this.boxGeometry, trim);
      canopy.position.set(0, 3.2, -item.depth / 2 - 0.7); canopy.scale.set(Math.min(7, item.width * 0.56), 0.28, 2.4);
      const entryGlass = new Mesh(this.boxGeometry, glass);
      entryGlass.position.set(0, 1.85, -item.depth / 2 - 1.15); entryGlass.scale.set(Math.min(4.8, item.width * 0.38), 2.35, 0.1);
      foundation.name = `district-${item.id}-foundation`; mass.name = `district-${item.id}-${item.category}`; crown.name = `district-${item.id}-crown`;
      roofUnit.name = `district-${item.id}-roof-equipment`; canopy.name = `district-${item.id}-entry-canopy`; entryGlass.name = `district-${item.id}-entry-glass`;
      object.add(foundation, mass, crown, roofPlate, roofUnit, canopy, entryGlass);
      this.addDistrictLabel(object, metadata, 0, baseHeight + item.height + 5, 0);
      const focus = new Mesh(new BoxGeometry(item.width + 1.3, item.height + 2.1, item.depth + 1.3), new MeshBasicMaterial({ color: 0x62efff, transparent: true, opacity: 0, wireframe: true, depthWrite: false }));
      focus.position.set(0, baseHeight + item.height / 2, 0); focus.visible = false; focus.name = `district-${item.id}-focus-outline`; focus.raycast = () => {};
      object.add(focus); this.buildingFocus.set(object, focus);
      const floorHeight = item.category === "office" ? 3.0 : item.category === "lab" ? 3.2 : 2.8;
      const floors = Math.max(2, Math.floor(item.height / floorHeight));
      const columnsX = Math.max(2, Math.floor(item.width / 2.8));
      const columnsZ = Math.max(2, Math.floor(item.depth / 2.8));
      for (let floor = 0; floor < floors; floor += 1) {
        const y = baseHeight + 1.5 + floor * ((item.height - 2.6) / floors);
        for (let column = 1; column <= columnsX; column += 1) {
          const x = item.x - item.width / 2 + column * item.width / (columnsX + 1);
          windows.push({ x, y, z: item.z + item.depth / 2 + 0.055, rotate: false, scaleX: item.category === "lab" ? 1.85 : 1.35, scaleY: 1.2 });
          windows.push({ x, y, z: item.z - item.depth / 2 - 0.055, rotate: false, scaleX: item.category === "lab" ? 1.85 : 1.35, scaleY: 1.2 });
        }
        for (let column = 1; column <= columnsZ; column += 1) {
          const z = item.z - item.depth / 2 + column * item.depth / (columnsZ + 1);
          windows.push({ x: item.x + item.width / 2 + 0.055, y, z, rotate: true, scaleX: item.category === "lab" ? 1.85 : 1.35, scaleY: 1.2 });
          windows.push({ x: item.x - item.width / 2 - 0.055, y, z, rotate: true, scaleX: item.category === "lab" ? 1.85 : 1.35, scaleY: 1.2 });
        }
      }
      object.traverse((child) => { child.userData.building = building; });
    }
    const facade = new InstancedMesh(this.boxGeometry, glass, windows.length);
    const pose = new Object3D(); const color = new Color();
    windows.forEach((window, index) => {
      pose.position.set(window.x, window.y, window.z); pose.rotation.set(0, window.rotate ? Math.PI / 2 : 0, 0); pose.scale.set(window.scaleX, window.scaleY, 0.075); pose.updateMatrix(); facade.setMatrixAt(index, pose.matrix);
      color.setHex(index % 9 === 0 ? 0xe0fcff : index % 4 === 0 ? 0x198fc2 : 0x5be0ff); facade.setColorAt(index, color);
    });
    facade.name = "district-building-facade-windows"; facade.castShadow = true; this.districtBuildings.add(facade);
  }

  private districtMetadata(item: { id: string; category: "office" | "lab" | "amenity" | "service"; width: number; depth: number; height: number }): BuildingMetadata {
    const names: Record<string, string> = {
      "C01-CANTEEN": "园区食堂", "C02-INNOVATION": "创新中心", "C03-EXHIBITION": "展示中心", "C04-CLUB": "园区活动中心",
      "D01-GATE": "园区门卫", "D02-SERVICE": "综合服务中心",
    };
    const type = item.category === "office" ? "office" : item.category === "lab" ? "laboratory" : "service";
    const floors = Math.max(1, Math.round(item.height / (item.category === "office" ? 3 : item.category === "lab" ? 3.2 : 2.8)));
    const sequence = (item.id.match(/\d+/)?.[0] ?? "1").padStart(2, "0");
    const name = names[item.id] ?? (item.category === "office" ? `科研办公楼 ${sequence}` : `实验研发楼 ${sequence}`);
    const typeLabel = item.category === "office" ? "科研办公建筑" : item.category === "lab" ? "实验研发建筑" : item.category === "amenity" ? "园区配套建筑" : "园区服务设施";
    const risk = item.category === "service" ? "low" : item.category === "amenity" ? "general" : "low";
    return {
      id: `DISTRICT-${item.id}`, name, type, typeLabel,
      area: Math.round(item.width * item.depth * floors * 0.82), floors,
      deviceCount: Math.max(6, floors * (item.category === "office" ? 8 : item.category === "lab" ? 7 : 4)),
      alarms: 0, safetyIndex: item.category === "lab" ? 93 : 96, risk, level: 0,
      status: "正常运行 · 园区扩展资产",
    };
  }

  private addDistrictLabel(object: Group, metadata: BuildingMetadata, x: number, y: number, z: number): void {
    const element = document.createElement("div");
    element.className = "twin-label";
    element.dataset.buildingId = object.userData.buildingId as string;
    element.style.pointerEvents = "none";
    element.replaceChildren(document.createTextNode(metadata.name), Object.assign(document.createElement("small"), { className: "twin-label__type", textContent: metadata.typeLabel }));
    element.dataset.riskLevel = riskLabels[metadata.risk];
    const label = new CSS2DObject(element);
    label.position.set(x, y, z);
    object.add(label); this.buildingLabels.set(object, label);
  }

  private createTrees(): void {
    const points: [number, number][] = [];
    for (const x of [-49, 49]) for (const z of [-37, -28, -18, 16, 26, 36]) points.push([x, z]);
    for (const z of [-40, 40]) for (const x of [-39, -29, -19, 19, 29, 39]) points.push([x, z]);
    for (const z of [-9, 9]) for (const x of [-44, -36, -19, 18, 37, 45]) points.push([x, z]);
    const trunkMaterial = new MeshStandardMaterial({ color: 0x465954, roughness: 1 });
    const crownMaterial = new MeshStandardMaterial({ color: 0x3c786d, roughness: 1, flatShading: true });
    const trunks = new InstancedMesh(new CylinderGeometry(0.2, 0.3, 2.2, 6), trunkMaterial, points.length);
    const crowns = new InstancedMesh(new IcosahedronGeometry(1, 1), crownMaterial, points.length);
    const pose = new Object3D(); const color = new Color();
    points.forEach(([x, z], index) => {
      const scale = 0.85 + (index % 4) * 0.11;
      pose.position.set(x, 1.15, z); pose.scale.set(1, 1, 1); pose.rotation.set(0, 0, 0); pose.updateMatrix(); trunks.setMatrixAt(index, pose.matrix);
      pose.position.set(x, 3.2 * scale, z); pose.scale.set(1.7 * scale, 2.35 * scale, 1.65 * scale); pose.rotation.y = index * 0.71; pose.updateMatrix(); crowns.setMatrixAt(index, pose.matrix);
      color.setHex(index % 3 === 0 ? 0x85a895 : 0x739d94); crowns.setColorAt(index, color);
    });
    crowns.castShadow = true; trunks.castShadow = true; this.foliage.add(trunks, crowns);
  }

  /** Tree avenues and garden clusters for the expanded district. Positions are
   * intentionally kept outside roads, parking aisles and the existing core. */
  private createDistrictTrees(): void {
    const points: [number, number, number][] = [];
    for (const x of [-92, -82, -52, -42, 42, 52, 82, 92]) {
      points.push([x, -68, 1], [x, 68, 1]);
    }
    for (const z of [-58, -46, -32, 31, 46, 58]) {
      points.push([-91, z, 0.9], [91, z, 0.9]);
    }
    for (const [x, z] of [[-78, 35], [-70, 48], [-58, 42], [-75, 55], [78, -35], [70, -48], [58, -42], [75, -55], [-58, -61], [-42, -61], [42, 61], [58, 61]]) points.push([x, z, 1.18]);
    const trunkMaterial = new MeshStandardMaterial({ color: 0x3f6059, roughness: 1 });
    const crownMaterial = new MeshStandardMaterial({ color: 0x316d67, roughness: 0.9, flatShading: true });
    const trunks = new InstancedMesh(new CylinderGeometry(0.22, 0.34, 2.5, 6), trunkMaterial, points.length);
    const crowns = new InstancedMesh(new IcosahedronGeometry(1, 1), crownMaterial, points.length);
    const pose = new Object3D(); const tint = new Color();
    points.forEach(([x, z, scale], index) => {
      pose.position.set(x, 1.3, z); pose.scale.set(1, 1, 1); pose.rotation.set(0, 0, 0); pose.updateMatrix(); trunks.setMatrixAt(index, pose.matrix);
      pose.position.set(x, 3.8 * scale, z); pose.scale.set(1.9 * scale, 2.6 * scale, 1.8 * scale); pose.rotation.y = index * 0.59; pose.updateMatrix(); crowns.setMatrixAt(index, pose.matrix);
      tint.setHex(index % 4 === 0 ? 0x7aa58e : index % 3 === 0 ? 0x4f8876 : 0x3a746b); crowns.setColorAt(index, tint);
    });
    trunks.name = "district-tree-trunks"; crowns.name = "district-tree-canopies";
    trunks.castShadow = true; crowns.castShadow = true; this.foliage.add(trunks, crowns);
  }

  /** Low planting beds bring colour to plazas and building entries without
   * sacrificing the restrained low-poly language of the original park. */
  private createFlowerBeds(): void {
    const bedMaterial = new MeshStandardMaterial({ color: 0x315b57, emissive: 0x123a3a, emissiveIntensity: 0.3, roughness: 0.9 });
    const flowerMaterial = new MeshStandardMaterial({ color: 0xffffff, emissive: 0x5ad4cc, emissiveIntensity: 0.52, roughness: 0.6, vertexColors: true });
    this.surfaces.push({ material: bedMaterial, opacity: 1 }, { material: flowerMaterial, opacity: 1 });
    const beds: [number, number, number, number][] = [[-67, 43, 15, 2.2], [67, -43, 15, 2.2], [-47, -68, 22, 2.1], [47, 68, 22, 2.1], [0, 55, 24, 2.4]];
    const blooms: { x: number; z: number; tint: number }[] = [];
    beds.forEach(([x, z, width, depth], bedIndex) => {
      const bed = new Mesh(this.boxGeometry, bedMaterial);
      bed.position.set(x, 0.22, z); bed.scale.set(width, 0.25, depth); bed.receiveShadow = true; this.foliage.add(bed);
      for (let column = -Math.floor(width / 2) + 1; column < width / 2; column += 1.35)
        blooms.push({ x: x + column, z: z + (bedIndex % 2 ? 0.45 : -0.45), tint: [0x7ce7df, 0x8ba8ef, 0xffb5d6][(column + bedIndex + 30) % 3] ?? 0x7ce7df });
    });
    const flowers = new InstancedMesh(new IcosahedronGeometry(0.28, 0), flowerMaterial, blooms.length);
    const pose = new Object3D(); const color = new Color();
    blooms.forEach((flower, index) => { pose.position.set(flower.x, 0.62 + (index % 3) * 0.05, flower.z); pose.scale.set(1, 0.65, 1); pose.updateMatrix(); flowers.setMatrixAt(index, pose.matrix); color.setHex(flower.tint); flowers.setColorAt(index, color); });
    flowers.name = "district-flower-beds"; this.foliage.add(flowers);
  }

  private createFurniture(): void {
    const posts = new MeshStandardMaterial({ color: 0x5c8092, roughness: 0.5, metalness: 0.5 });
    const lamps = new MeshStandardMaterial({ color: 0x9dd8dc, emissive: 0x67c6d1, emissiveIntensity: 0.6, roughness: 0.3 });
    const poles = new InstancedMesh(new CylinderGeometry(0.1, 0.16, 4, 6), posts, 10);
    const lights = new InstancedMesh(this.boxGeometry, lamps, 10);
    const pose = new Object3D(); let index = 0;
    for (const z of [-6.2, 6.2]) for (const x of [-47, -26, -11, 25, 47]) {
      pose.position.set(x, 2, z); pose.scale.set(1, 1, 1); pose.updateMatrix(); poles.setMatrixAt(index, pose.matrix);
      pose.position.set(x, 4.1, z); pose.scale.set(0.8, 0.15, 0.5); pose.updateMatrix(); lights.setMatrixAt(index++, pose.matrix);
    }
    this.furniture.add(poles, lights);
    const pedestal = new Mesh(new CylinderGeometry(2.3, 2.6, 0.3, 24), posts); pedestal.position.set(0, 0.4, 33);
    const monument = new Mesh(new TorusGeometry(1.7, 0.13, 6, 24), lamps); monument.position.set(0, 2.4, 33); monument.rotation.y = -Math.PI / 5;
    this.furniture.add(pedestal, monument);
  }

  private createDistrictLighting(): void {
    const posts = new MeshStandardMaterial({ color: 0x4c7182, roughness: 0.45, metalness: 0.56 });
    const lamps = new MeshStandardMaterial({ color: 0xb9f8ff, emissive: 0x3cd9e8, emissiveIntensity: 0.8, roughness: 0.22, metalness: 0.4 });
    const points: [number, number][] = [];
    for (let x = -88; x <= 88; x += 22) points.push([x, -71], [x, 71]);
    for (let z = -55; z <= 55; z += 22) points.push([-94, z], [94, z]);
    const poles = new InstancedMesh(new CylinderGeometry(0.1, 0.15, 5, 6), posts, points.length);
    const heads = new InstancedMesh(this.boxGeometry, lamps, points.length);
    const pose = new Object3D();
    points.forEach(([x, z], index) => { pose.position.set(x, 2.5, z); pose.scale.set(1, 1, 1); pose.updateMatrix(); poles.setMatrixAt(index, pose.matrix); pose.position.set(x, 5.1, z); pose.scale.set(0.92, 0.16, 0.52); pose.updateMatrix(); heads.setMatrixAt(index, pose.matrix); });
    poles.name = "district-light-poles"; heads.name = "district-light-heads"; this.furniture.add(poles, heads);
  }

  setMode(mode: SceneMode): void {
    const transparent = mode !== "above";
    for (const surface of this.surfaces) {
      surface.material.opacity = mode === "underground" ? 0.075 : (mode === "risk" || mode === "emergency") ? 0.22 : surface.opacity;
      surface.material.transparent = transparent; surface.material.depthWrite = !transparent; surface.material.needsUpdate = true;
    }
    this.foliage.visible = mode === "above" || mode === "emergency";
    this.furniture.visible = mode === "above" || mode === "emergency";
    // Context buildings deliberately step away in underground mode so the
    // original B2 facility, pipes and devices remain readable.
    this.districtBuildings.visible = mode !== "underground";
    // The expansion district reads as normal/available in risk mode while the
    // existing B2 high-risk asset remains red through BuildingManager's live
    // risk styling. Other modes restore the standard blue glass palette.
    if (this.districtPalette) {
      const { body, roof, trim, glass } = this.districtPalette;
      if (mode === "risk") {
        body.color.setHex(0x20645c); body.emissive.setHex(0x0b413e);
        roof.color.setHex(0x174d49); trim.color.setHex(0x48d7a8); glass.color.setHex(0x70ead0);
      } else {
        body.color.setHex(0x103a60); body.emissive.setHex(0x082c49);
        roof.color.setHex(0x0a2948); trim.color.setHex(0x2bd4f2); glass.color.setHex(0x68e8ff);
      }
    }
  }

  setHover(object: Group | null): void {
    this.hovered = this.entries.some((entry) => entry.object === object) ? object : null;
    this.applyBuildingInteraction();
  }

  setSelected(object: Group | null): void {
    this.selected = this.entries.some((entry) => entry.object === object) ? object : null;
    this.applyBuildingInteraction();
  }

  private applyBuildingInteraction(): void {
    for (const entry of this.entries) {
      const selected = entry.object === this.selected;
      const hovered = entry.object === this.hovered;
      entry.object.scale.setScalar(selected ? 1.035 : hovered ? 1.018 : 1);
      const focus = this.buildingFocus.get(entry.object);
      if (focus) {
        focus.visible = selected || hovered;
        focus.material.color.setHex(selected ? 0x8dffff : 0x48cfe9);
        focus.material.opacity = selected ? 0.92 : 0.5;
      }
      const label = this.buildingLabels.get(entry.object);
      if (label) {
        const type = entry.metadata.typeLabel;
        const subline = selected || hovered ? `风险等级 · ${riskLabels[entry.metadata.risk]}` : type;
        label.element.replaceChildren(document.createTextNode(entry.metadata.name), Object.assign(document.createElement("small"), { className: "twin-label__type", textContent: subline }));
      }
    }
  }

  dispose(): void { disposeObject(this.group); this.surfaces.length = 0; }
}
