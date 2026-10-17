import {DoubleSide,Mesh,PlaneGeometry,ShaderMaterial} from 'three';
import type {SceneMode} from '../types/scene';import type {FloodState} from '../../types/flood';import {disposeObject} from '../utils/dispose';
export class WaterSurface {
 readonly mesh:Mesh<PlaneGeometry,ShaderMaterial>;readonly floorY=-5.675;
 private level=0;private mode:SceneMode='above';private targetScale=.17;private scale=.17;private targetLevel=0;private physicalLevel=0;
 private readonly uniforms={time:{value:0},opacity:{value:.34},waveStrength:{value:.06}};
 constructor(){this.mesh=new Mesh(new PlaneGeometry(29.1,25.1),new ShaderMaterial({uniforms:this.uniforms,transparent:true,depthWrite:false,side:DoubleSide,
 vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
 fragmentShader:'varying vec2 vUv; uniform float time; uniform float opacity; uniform float waveStrength; void main(){vec2 p=vUv*2.0-1.0;float edge=1.0-smoothstep(.80,1.0,max(abs(p.x),abs(p.y)));float ripple=sin(vUv.x*45.0+time*1.7)*sin(vUv.y*37.0-time*1.2);vec3 color=vec3(.10,.43,.62)+ripple*waveStrength;gl_FragColor=vec4(color,opacity*edge);}'
 }));this.mesh.name='b2-water-surface';this.mesh.rotation.x=-Math.PI/2;this.mesh.position.set(0,this.floorY+.002,10);this.mesh.renderOrder=2;this.mesh.visible=false;this.mesh.raycast=()=>{};}
 updateLevel(cm:number):void {this.level=Math.max(0,cm);this.targetLevel=this.level/100;this.physicalLevel=this.targetLevel;this.mesh.position.y=this.floorY+this.physicalLevel+.002;this.targetScale=.15+Math.min(.1,this.level/100);this.visibility();}
 updateFlood(f:FloodState):void {this.level=f.waterLevel;this.targetLevel=f.waterLevel/100;this.targetScale=Math.sqrt(Math.max(0,Math.min(1,f.waterArea/f.effectiveArea)));this.uniforms.opacity.value=.30+Math.min(.15,f.waterLevel/200);this.visibility();}
 applyReplay(level:number|null,area:number|null,effectiveArea:number|null):void {
  if(level===null||area===null||effectiveArea===null||effectiveArea<=0){this.level=0;this.mesh.visible=false;return;}
  this.level=level;this.targetLevel=this.physicalLevel=Math.max(0,level)/100;
  this.targetScale=this.scale=Math.sqrt(Math.max(0,Math.min(1,area/effectiveArea)));
  this.uniforms.opacity.value=.30+Math.min(.15,level/200);this.update(0,false);this.visibility();
 }
 update(dt:number,running:boolean):void {const a=1-Math.exp(-dt*5);this.scale+=(this.targetScale-this.scale)*a;this.physicalLevel+=(this.targetLevel-this.physicalLevel)*a;this.mesh.scale.set(this.scale,this.scale,1);this.mesh.position.y=this.floorY+this.physicalLevel+.002;this.mesh.position.x=-4*(1-this.scale);this.mesh.position.z=10+4*(1-this.scale);if(running)this.uniforms.time.value+=dt;}
 setMode(mode:SceneMode):void {this.mode=mode;this.visibility();}
 private visibility():void {this.mesh.visible=this.level>0&&this.mode!=='above';}
 get waterLevel():number{return this.level;}
 get areaScale():number{return this.scale;}
 dispose():void{disposeObject(this.mesh);}
}
