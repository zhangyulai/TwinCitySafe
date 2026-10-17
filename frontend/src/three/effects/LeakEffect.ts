import {BufferGeometry,Float32BufferAttribute,Points,PointsMaterial,Group,RingGeometry,Mesh,MeshBasicMaterial,DoubleSide,Vector3} from 'three';import {disposeObject} from '../utils/dispose';import type {SceneMode} from '../types/scene';
/** Fixed pool, no per-state geometries/textures. The anchor is the observed rank-one segment. */
export class LeakEffect {
 readonly group=new Group();private geometry=new BufferGeometry();private positions=new Float32Array(120*3);private material=new PointsMaterial({color:0x78d4f4,size:.22,transparent:true,opacity:0,depthWrite:false});private ringMaterial=new MeshBasicMaterial({color:0xf17168,transparent:true,opacity:0,side:DoubleSide,depthWrite:false});private ring=new Mesh(new RingGeometry(.8,1.05,32),this.ringMaterial);private strength=0;private time=0;private anchor:string|null=null;
 constructor(){this.geometry.setAttribute('position',new Float32BufferAttribute(this.positions,3));const points=new Points(this.geometry,this.material);points.frustumCulled=false;this.ring.rotation.x=-Math.PI/2;this.group.add(points,this.ring);this.group.name='observed-leak-effect';}
 apply(id:string|null,position:Vector3|undefined,flow:number){this.anchor=id;this.strength=id&&position?Math.min(1,flow/25):0;if(position)this.group.position.copy(position);this.material.opacity=this.strength*.8;this.ringMaterial.opacity=this.strength*.6;}
 update(dt:number,running:boolean){if(running)this.time+=dt;const strength=this.strength;for(let i=0;i<120;i++){const phase=(this.time*(.5+strength)+i/120)%1,angle=i*2.39996;this.positions[i*3]=Math.cos(angle)*phase*(.5+strength);this.positions[i*3+1]=phase*(2+strength*3);this.positions[i*3+2]=Math.sin(angle)*phase*(.5+strength);}const attribute=this.geometry.getAttribute('position');(attribute.array as Float32Array).set(this.positions);attribute.needsUpdate=true;this.ring.scale.setScalar(1+strength+Math.sin(this.time*3)*.15*strength);}
 setMode(mode:SceneMode){this.group.visible=mode==='underground';}
 debug(){return {anchor:this.anchor,strength:this.strength,poolSize:120,visible:this.group.visible&&this.strength>0};}
 dispose(){disposeObject(this.group);}
}
