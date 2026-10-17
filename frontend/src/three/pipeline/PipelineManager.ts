import {Group,LineCurve3,Mesh,MeshStandardMaterial,TubeGeometry,Vector3,CylinderGeometry} from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import type {SceneMode} from '../types/scene';
import type {PipelineKind,PipelineState,ParkRealtimeState} from '../../types/realtime';
import {pipeColors,type PipelineNetwork,type PipelineType} from '../../types/pipeline';
import {disposeObject} from '../utils/dispose';
export interface PipelineEntry {id:string;type:PipelineKind;object:Group;representative:Mesh<TubeGeometry,MeshStandardMaterial>;material:MeshStandardMaterial;state:PipelineState|null;offset:{value:number};speed:number}
/** Asset-driven geometry. A common compiled shader, per-edge scalar uniforms, no frame allocations. */
export class PipelineManager {
 readonly group=new Group(); readonly entries:PipelineEntry[]=[];readonly valves:Group[]=[];
 private replayMissing=new Set<string>();
 private ranks=new Map<string,number>();private pulseTime=0;
 private selected:string|null=null;private hovered:string|null=null;private trace=new Set<string>();private affected=false;
 private network:PipelineNetwork|null=null;private readonly label=new CSS2DObject(document.createElement('span'));
 constructor(){this.group.name='underground-pipeline-assets';this.label.element.className='pipeline-scene-label';this.group.add(this.label);this.label.visible=false;this.setMode('above');}
 load(network:PipelineNetwork):void {
  if(this.network===network)return;
  for(const e of this.entries){this.group.remove(e.object);disposeObject(e.object);}for(const v of this.valves){this.group.remove(v);disposeObject(v);}
  this.entries.length=0;this.valves.length=0;this.network=network;
  const nodes=new Map(network.nodes.map(n=>[n.id,n]));
  for(const e of network.edges){
   const a=nodes.get(e.startNodeId),b=nodes.get(e.endNodeId);if(!a||!b)continue;
   const curve=new LineCurve3(new Vector3(a.x,a.y,a.z),new Vector3(b.x,b.y,b.z));
   const material=new MeshStandardMaterial({color:pipeColors[e.pipelineType],emissive:pipeColors[e.pipelineType],emissiveIntensity:.12,roughness:.5,metalness:.15});
   const offset={value:0};
   material.onBeforeCompile=shader=>{
    shader.uniforms.flowOffset=offset;
    shader.vertexShader='varying vec2 pipeUv;\n'+shader.vertexShader.replace('#include <uv_vertex>','#include <uv_vertex>\npipeUv=uv;');
    shader.fragmentShader='uniform float flowOffset; varying vec2 pipeUv;\n'+shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\nfloat pulse = smoothstep(0.72,0.88,fract(pipeUv.x * 8.0 - flowOffset));\ndiffuseColor.rgb *= 0.72 + 0.55 * pulse;');
   };
   material.customProgramCacheKey=()=> 'pipeline-flow-m4';
   const mesh=new Mesh(new TubeGeometry(curve,8,Math.max(.23,e.diameter/850),8,false),material);
   const object=new Group();object.name=e.id;object.userData.pipelineId=e.id;object.add(mesh);this.group.add(object);
   this.entries.push({id:e.id,type:e.pipelineType==='drainage'?'drain':e.pipelineType,object,representative:mesh,material,state:null,offset,speed:0});
  }
  for(const v of network.valves){const n=nodes.get(v.nodeId);if(!n)continue;const object=new Group();object.name=v.id;object.userData.valveId=v.id;object.userData.pipelineType=n.metadata.pipelineType;object.position.set(n.x,n.y,n.z);
   const material=new MeshStandardMaterial({color:0x42cbaa,roughness:.5});
   const body=new Mesh(new CylinderGeometry(.7,.7,1.3,12),material);object.add(body);const wheel=new Mesh(new CylinderGeometry(1,1,.15,12),material);wheel.position.y=1;object.add(wheel);this.valves.push(object);this.group.add(object);}
  this.refresh();
 }
 updatePipelineState(state:PipelineState):void {const e=this.entries.find(e=>e.id===state.id);if(!e)return;e.state=state;e.speed=state.flow/30;e.object.userData.state=state;this.appearance(e);}
 applyReplayStates(states:Partial<PipelineState>[]=[],valves:ParkRealtimeState['valves']=[]):void {
  this.replayMissing.clear();
  for(const e of this.entries){const value=states.find(p=>p.id===e.id);e.state=value?value as PipelineState:null;e.speed=typeof value?.flow==='number'?value.flow/30:0;e.object.userData.state=value??null;if(!value?.status)this.replayMissing.add(e.id);this.appearance(e);}
  for(const v of this.valves){v.userData.replayStatus='unknown';v.traverse(o=>{if(o instanceof Mesh)(o.material as MeshStandardMaterial).color.set('#65747f');});}
  this.updateValves(valves);
 }
 updateValves(values:ParkRealtimeState['valves']):void {for(const v of values??[]){const object=this.valves.find(o=>o.name===v.id);if(object)object.userData.replayStatus=v.status;object?.traverse(o=>{if(o instanceof Mesh)(o.material as MeshStandardMaterial).color.set(v.status==='open'?0x42cbaa:v.status==='closed'?0x697a87:0xe8a14c);});}}
 update(delta:number,running=true):void {if(!running)return;this.pulseTime+=delta;for(const e of this.entries){e.offset.value=(e.offset.value+delta*e.speed)%1;if(this.ranks.get(e.id)===0&&e.state?.status!=="isolated"&&e.state?.status!=="offline")e.material.emissiveIntensity=.65+.2*Math.sin(this.pulseTime*3);}}
 setSelected(id:string|null):void {this.selected=id;this.label.visible=!!id;this.label.element.textContent=id??'';const e=this.entries.find(e=>e.id===id);if(e)e.representative.geometry.parameters.path.getPoint(.5,this.label.position);else {const v=this.valves.find(v=>v.name===id);if(v)this.label.position.copy(v.position);else this.label.visible=false;}this.label.position.y+=2;this.refresh();}
 setHover(id:string|null):void {this.hovered=id;this.refresh();}
 setTrace(ids:string[],affected=false):void {this.trace=new Set(ids);this.affected=affected;this.refresh();}
 setLeakRanks(ids:string[]):void {this.ranks=new Map(ids.map((id,i)=>[id,i]));this.refresh();}
 private refresh():void {for(const e of this.entries)this.appearance(e);}
 private appearance(e:PipelineEntry):void {const kind=e.type==='drain'?'drainage':e.type;const isolated=e.state?.status==='isolated'||e.state?.status==='offline';const traced=this.trace.has(e.id);
  e.material.color.set(isolated?'#65747f':this.ranks.has(e.id)?['#ef716b','#e7a75b','#e4d779'][this.ranks.get(e.id)!]!:traced?(this.affected?'#f0a451':'#83edff'):this.replayMissing.has(e.id)?'#65747f':pipeColors[kind]);e.material.emissive.copy(e.material.color);
  e.material.emissiveIntensity=!isolated&&this.ranks.has(e.id)?(.7-(this.ranks.get(e.id)??0)*.15):e.id===this.selected ? .65 : e.id===this.hovered ? .3 : traced ? .4 : this.trace.size ? .025 : .12;
 }
 filter(types:PipelineType[]):void {for(const e of this.entries)e.object.visible=types.includes(e.type==='drain'?'drainage':e.type);for(const v of this.valves)v.visible=types.includes(v.userData.pipelineType);}
 getObject(id:string):Group|undefined {return this.entries.find(e=>e.id===id)?.object??this.valves.find(v=>v.name===id);}
 focusNode(id:string):Vector3|undefined {const n=this.network?.nodes.find(n=>n.id===id);return n?new Vector3(n.x,n.y,n.z):undefined;}
 setMode(mode:SceneMode):void {this.group.visible=mode==='underground';}
 dispose():void {this.label.element.remove();disposeObject(this.group);this.entries.length=0;this.valves.length=0;}
}
