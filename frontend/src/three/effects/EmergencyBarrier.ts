import {BoxGeometry,Group,Mesh,MeshBasicMaterial} from 'three';
import {CSS2DObject} from 'three/addons/renderers/CSS2DRenderer.js';import {disposeObject} from '../utils/dispose';import type {SceneMode} from '../types/scene';
/** Allocated once, opacity-zero prewarming avoids first-closure GPU allocations. */
export class EmergencyBarrier {
 readonly group=new Group();readonly gate:Mesh<BoxGeometry,MeshBasicMaterial>;private readonly mark:MeshBasicMaterial;
 private readonly label:CSS2DObject;private closed=false;private preview=false;
 constructor(){
  const geometry=new BoxGeometry(1,1,1);this.gate=new Mesh(geometry,new MeshBasicMaterial({color:0xe86562,transparent:true,opacity:0,depthWrite:false}));this.gate.scale.set(.25,3,5);
  this.mark=new MeshBasicMaterial({color:0xff7875,transparent:true,opacity:0,depthWrite:false});
  const a=new Mesh(geometry,this.mark),b=new Mesh(geometry,this.mark);a.scale.set(.3,.15,5);b.scale.copy(a.scale);a.rotation.x=.55;b.rotation.x=-.55;
  this.group.add(this.gate,a,b);this.group.position.set(14.5,-4,10);this.group.name='B2-EAST-emergency-barrier';
  const element=document.createElement('div');element.className='twin-label';element.dataset.entranceId='B2-EAST';element.style.color='#ffb46d';element.style.pointerEvents='none';this.label=new CSS2DObject(element);this.label.position.y=2.4;this.group.add(this.label);this.label.visible=false;
 }
 apply(closed:boolean){this.closed=closed;this.update();}
 setPreview(preview:boolean){this.preview=preview;this.update();}
 private update(){this.gate.material.color.setHex(this.closed?0xe86562:0xe6c85b);this.gate.material.opacity=this.closed?.35:this.preview?.15:0;this.mark.opacity=this.closed?.9:0;this.label.visible=this.closed||this.preview;this.label.element.textContent=this.closed?'B2 东入口 · 已封控':'B2 东入口 · 拟封控（预览）';}
 setMode(mode:SceneMode){this.group.visible=mode!=='above';}
 debug(){return {closed:this.closed,preview:this.preview,visible:this.group.visible&&(this.closed||this.preview)};}
 dispose(){disposeObject(this.group);}
}
