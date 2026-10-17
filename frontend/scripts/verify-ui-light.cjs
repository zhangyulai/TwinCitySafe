/* Read-only visual/layout acceptance for the six-page light workspace. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = path.resolve(__dirname, '../../docs/ui-light');
const base = process.env.M10_BASE_URL || 'http://127.0.0.1:5173';
const routes = ['dashboard','operation','pipeline','risk','simulation','review'];
const results = {layouts:[],errors:[],screenshots:[]};
let browser;
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1920,height:1080}});
  page.setDefaultTimeout(15000);
  await page.addInitScript(()=>{
    for(const type of [WebGLRenderingContext,WebGL2RenderingContext])for(const name of ['drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced']){
      const original=type.prototype[name];if(!original)continue;
      type.prototype[name]=function(...args){this.canvas.__uiDrawCalls=(this.canvas.__uiDrawCalls||0)+1;return original.apply(this,args);};
    }
  });
  page.on('pageerror',error=>results.errors.push(error.message));
  for(const width of [1920,1440,1366,390]){
    await page.setViewportSize({width,height:width===390?844:1080});
    for(const route of routes){
      await page.goto(`${base}/${route}`);
      await page.locator('.workspace-navigation').waitFor();
      if(route!=='review')await page.locator('[data-testid="twin-scene"] canvas').first().waitFor();
      await page.waitForTimeout(1800);
      const layout=await page.evaluate(()=>{
        const el=document.querySelector('[data-testid="twin-scene"]'),canvas=el?.querySelector('canvas');
        const r=canvas?.getBoundingClientRect();
        return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,scheme:getComputedStyle(document.documentElement).colorScheme,body:getComputedStyle(document.body).backgroundColor,scene:r?{width:r.width,height:r.height,top:r.top,canvasWidth:canvas.width,canvasHeight:canvas.height,drawCalls:canvas.__uiDrawCalls}:null,overflow:Array.from(document.querySelectorAll('main *')).filter(e=>e.getBoundingClientRect().right>innerWidth+2&&getComputedStyle(e).position!=='absolute').slice(0,8).map(e=>({tag:e.tagName,class:e.className,right:e.getBoundingClientRect().right}))};
      });
      results.layouts.push({route,...layout});console.log(route,width,JSON.stringify(layout));
      const file=path.join(output,`${route}-${width}.png`);await page.screenshot({path:file,fullPage:true});results.screenshots.push(file);
    }
  }
  fs.writeFileSync(path.join(output,'layout-results.json'),JSON.stringify(results,null,2));
  assert(results.layouts.every(x=>x.scrollWidth<=x.width+1),'Page overflow; see layout-results.json');
  assert(results.layouts.every(x=>x.scheme==='light'),'All routes use light controls');
  assert(results.layouts.every(x=>!x.scene||(x.scene.width>220&&x.scene.height>180&&x.scene.drawCalls>0)),'All scenes must render at usable size');
  assert.deepEqual(results.errors,[]);
  await browser.close();
})().catch(async e=>{results.failure=String(e.stack);fs.writeFileSync(path.join(output,'layout-results.json'),JSON.stringify(results,null,2));console.error(e);await browser?.close();process.exitCode=1;});
