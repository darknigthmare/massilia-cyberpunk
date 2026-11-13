// Minimal dependency-free Chrome DevTools capture harness for real playable builds.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

export async function openNativeBrowser(url, {width=1280,height=720,timeout=120000,webgl=false}={}) {
  const chromium=["/usr/bin/google-chrome","/usr/bin/google-chrome-stable","/usr/bin/chromium","/usr/bin/chromium-browser"].find(existsSync);
  if(!chromium)throw new Error("Aucun Chrome/Chromium : impossible de générer des captures réelles");
  const profile=await mkdtemp(join(tmpdir(),"launcher-native-capture-"));
  const port=9300+process.pid%700;
  const flags=["--headless=new","--no-sandbox","--disable-dev-shm-usage",
    "--no-first-run","--no-default-browser-check","--hide-scrollbars","--window-size="+width+","+height,
    "--force-device-scale-factor=1","--remote-allow-origins=*","--remote-debugging-port="+port,
    ...(webgl?["--enable-unsafe-swiftshader","--use-gl=angle","--use-angle=swiftshader"]:["--disable-gpu"]),
    "--user-data-dir="+profile,"about:blank"];
  const child=spawn(chromium,flags,{stdio:["ignore","ignore","pipe"]});
  let stderr="";
  child.stderr.on("data",data=>{stderr+=String(data).slice(0,400);});
  let urlCDP;
  for(let attempt=0;attempt<140;attempt++) {
    try{const res=await fetch("http://127.0.0.1:"+port+"/json/list");if(res.ok){
      const targets=await res.json();urlCDP=targets.find(t=>t.type==="page")?.webSocketDebuggerUrl;if(urlCDP)break;
    }}catch{}
    await sleep(100);
  }
  if(!urlCDP){child.kill("SIGTERM");throw new Error("CDP inaccessible: "+stderr.slice(-800));}
  const socket=new WebSocket(urlCDP),callbacks=new Map();
  let seq=0;
  await new Promise((resolve,reject)=>{
    socket.addEventListener("open",resolve,{once:true});
    socket.addEventListener("error",reject,{once:true});
  });
  socket.addEventListener("message",ev=>{
    const msg=JSON.parse(ev.data);
    if(!msg.id||!callbacks.has(msg.id))return;
    const {resolve,reject}=callbacks.get(msg.id);
    callbacks.delete(msg.id);
    msg.error?reject(new Error(JSON.stringify(msg.error))):resolve(msg.result||{});
  });
  const call=(method,params={})=>{
    const id=++seq;socket.send(JSON.stringify({id,method,params}));
    return new Promise((resolve,reject)=>callbacks.set(id,{resolve,reject}));
  };
  async function evaluate(expression) {
    const result=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true,userGesture:true});
    if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text||"Browser evaluation failed");
    return result.result?.value;
  }
  async function waitFor(expression,limit=timeout) {
    const stop=Date.now()+limit;
    while(Date.now()<stop){try{if(await evaluate(expression))return;}catch{}await sleep(180);}
    throw new Error("Browser predicate not reached: "+expression);
  }
  async function capture(format="png") {
    const result=await call("Page.captureScreenshot",{format,quality:format==="jpeg"?90:undefined,fromSurface:true,captureBeyondViewport:false});
    const image=Buffer.from(result.data||"","base64");
    if(image.length<12000)throw new Error("Captured frame is empty "+image.length);
    if(format==="png"&&(image.subarray(0,8).toString("hex")!=="89504e470d0a1a0a"||
       image.readUInt32BE(16)!==width||image.readUInt32BE(20)!==height))throw new Error("Native PNG dimensions mismatch");
    return image;
  }
  async function key(code,key,type){
    return call("Input.dispatchKeyEvent",{type,key,code,windowsVirtualKeyCode:key.toUpperCase().charCodeAt(0)});
  }
  await call("Page.enable");
  await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width,height,deviceScaleFactor:1,mobile:false});
  await call("Page.navigate",{url});
  return {call,evaluate,waitFor,capture,key,sleep,width,height,
    async close(){socket.close();child.kill("SIGTERM");await sleep(250);await rm(profile,{force:true,recursive:true}).catch(()=>{});}};
}
