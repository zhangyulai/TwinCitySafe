import { Group, LineCurve3, Mesh, MeshStandardMaterial, TubeGeometry, Vector3 } from "three";
import type { SceneMode } from "../types/scene";
import { disposeObject } from "../utils/dispose";
/** Programmatic yellow power routes complement the live water/fire network. */
export class PowerLineOverlay {
  readonly group = new Group();
  constructor() { this.group.name="underground-power-lines"; [[[-42,-5,28],[-14,-5,8]],[[-14,-5,8],[20,-5,-8]],[[20,-5,-8],[46,-5,-26]]].forEach((path,index)=>{const [from,to]=path.map(p=>new Vector3(...p as [number,number,number]));const mesh=new Mesh(new TubeGeometry(new LineCurve3(from,to),8,.18,8,false),new MeshStandardMaterial({color:0xf0ce55,emissive:0x9b7820,emissiveIntensity:.36,roughness:.45,metalness:.28}));mesh.name=`power-line-${index+1}`;this.group.add(mesh);});this.group.visible=false; }
  setMode(mode: SceneMode): void { this.group.visible = mode === "underground"; }
  dispose(): void { disposeObject(this.group); }
}
