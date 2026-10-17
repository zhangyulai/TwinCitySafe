import { CircleGeometry, Color, Group, Mesh, MeshBasicMaterial } from "three";
import type { SceneMode } from "../types/scene";
import { disposeObject } from "../utils/dispose";
export interface RiskDatum { position: [number, number]; riskLevel: number; }
const colorFor = (risk: number) => risk >= .7 ? 0xf05f63 : risk >= .4 ? 0xf0c65b : 0x42c88e;
/** GPU-light risk cells. Input is a `{position, riskLevel}` contract. */
export class RiskHeatmap {
  readonly group = new Group(); private readonly cells: Mesh<CircleGeometry, MeshBasicMaterial>[] = [];
  constructor() { this.group.name = "campus-risk-heatmap"; this.setRiskData([{position:[-29,-22],riskLevel:.18},{position:[25,-22],riskLevel:.32},{position:[-29,20],riskLevel:.46},{position:[28,20],riskLevel:.22},{position:[0,10],riskLevel:.82},{position:[-63,28],riskLevel:.28},{position:[62,-26],riskLevel:.38},{position:[0,68],riskLevel:.2}]); this.group.visible = false; }
  setRiskData(data: RiskDatum[]): void {
    while (this.cells.length < data.length) { const cell = new Mesh(new CircleGeometry(1, 32), new MeshBasicMaterial({ transparent:true, opacity:.3, depthWrite:false, color:0x42c88e })); cell.rotation.x=-Math.PI/2; cell.renderOrder=3; cell.raycast=()=>{}; this.cells.push(cell); this.group.add(cell); }
    this.cells.forEach((cell,index)=>{const datum=data[index];cell.visible=!!datum;if(!datum)return;const risk=Math.max(0,Math.min(1,datum.riskLevel));cell.position.set(datum.position[0],.42,datum.position[1]);cell.scale.setScalar(7+risk*11);cell.material.color=new Color(colorFor(risk));cell.material.opacity=.16+risk*.3;});
  }
  setMode(mode: SceneMode): void { this.group.visible = mode === "risk"; }
  dispose(): void { disposeObject(this.group); this.cells.length = 0; }
}
