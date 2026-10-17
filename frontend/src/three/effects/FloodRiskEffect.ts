import {Color,DoubleSide,Group,Mesh,PlaneGeometry,RingGeometry,MeshBasicMaterial,ShaderMaterial} from 'three';
import {CSS2DObject} from 'three/addons/renderers/CSS2DRenderer.js';import type {FloodState} from '../../types/flood';import type {SceneMode} from '../types/scene';import {disposeObject} from '../utils/dispose';
export class FloodRiskEffect {
 readonly group=new Group();private readonly heat:Mesh<PlaneGeometry,ShaderMaterial>;private readonly ring:Mesh<RingGeometry,MeshBasicMaterial>;private readonly label:CSS2DObject;
 private active=false;private mode:SceneMode='above';private target=0;private scale=0;private risk=0;private time=0;private level=0;
 private readonly color=new Color('#29d3a2');private readonly targetColor=new Color('#29d3a2');
 constructor(){this.heat=new Mesh(new PlaneGeometry(29.1,25.1),new ShaderMaterial({uniforms:{tint:{value:this.color},strength:{value:.23}},transparent:true,depthWrite:false,side:DoubleSide,
 vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
 fragmentShader:'varying vec2 vUv;uniform vec3 tint;uniform float strength;void main(){vec2 p=(vUv-.5)*2.0;float falloff=(1.0-smoothstep(.55,1.0,max(abs(p.x),abs(p.y))));gl_FragColor=vec4(tint,falloff*strength);}'
 }));this.heat.rotation.x=-Math.PI/2;this.heat.renderOrder=3;this.heat.raycast=()=>{};
 this.ring=new Mesh(new RingGeometry(14,14.2,64),new MeshBasicMaterial({color:0xef9858,transparent:true,opacity:.45,side:DoubleSide,depthWrite:false}));this.ring.rotation.x=-Math.PI/2;this.ring.raycast=()=>{};
 const el=document.createElement('div');el.className='flood-scene-label';this.label=new CSS2DObject(el);this.group.add(this.heat,this.ring,this.label);this.group.visible=false;}
 apply(f:Pick<FloodState,"scenarioId"|"riskScore"|"waterLevel"|"waterArea"|"effectiveArea">):void {this.active=!!f.scenarioId;this.risk=f.riskScore;this.level=f.waterLevel;this.target=Math.sqrt(Math.min(1,f.waterArea/f.effectiveArea));this.targetColor.set(f.riskScore>=80?'#ed6b6d':f.riskScore>=60?'#ee9853':f.riskScore>=20?'#e4ce65':'#29d3a2');this.label.element.textContent=`B2 仿真区 · 水位 ${f.waterLevel.toFixed(1)} cm · 风险 ${f.riskScore.toFixed(1)}`;this.visibility();}
 applyReplay(f:Pick<FloodState,"scenarioId"|"riskScore"|"waterLevel"|"waterArea"|"effectiveArea">|null):void {
  if(!f){this.active=false;this.group.visible=false;return;}
  this.apply(f);this.scale=this.target;this.color.copy(this.targetColor);this.update(0,false);
 }
 update(dt:number,running:boolean):void {if(!this.active)return;const a=1-Math.exp(-dt*4);this.scale+=(this.target-this.scale)*a;this.color.lerp(this.targetColor,a);this.heat.material.uniforms.strength!.value=.20+this.risk/500;this.heat.scale.set(this.scale,this.scale,1);this.heat.position.set(-4*(1-this.scale),-5.655+this.level/100,10+4*(1-this.scale));this.ring.position.set(0,-5.60+this.level/100,10);if(running)this.time+=dt;this.ring.scale.setScalar(Math.max(.1,this.scale)*(1+.05*Math.sin(this.time*2)));this.ring.material.opacity=this.risk>=60?(this.risk>=80?.65:.40)+.12*Math.sin(this.time*2):0;this.ring.material.color.copy(this.color);this.label.position.set(0,1.4,10);}
 setMode(mode:SceneMode):void {this.mode=mode;this.visibility();}
 private visibility():void {this.group.visible=this.active&&this.mode!=='above';this.ring.visible=true;}
 debug(){return {active:this.active,visible:this.group.visible,scale:this.scale,color:'#'+this.color.getHexString(),pulseVisible:this.risk>=60&&this.group.visible,risk:this.risk};}
 dispose():void {disposeObject(this.group);}
}
