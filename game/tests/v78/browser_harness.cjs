'use strict';
// Shared execution plumbing; game and viewer scenarios live in separate files.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
const {sourceEvidence, finishEvidence} = require('./browser_provenance.cjs');

function options(scope) {
  const result = {url:'http://127.0.0.1:8828/SOMA_MASSILIA_URBAIN_v0_78.html',
    chromium:'/usr/bin/chromium',output:'/tmp/massilia-v78-'+scope,timeout:90000};
  for (let i=2;i<process.argv.length;i++) {
    const key=process.argv[i].replace(/^--/,'');
    assert(Object.hasOwn(result,key)&&process.argv[i+1],'Unknown or incomplete option');
    result[key]=key==='timeout'?Number(process.argv[++i]):process.argv[++i];
  }
  return result;
}

function expectedSceneAbort(row, origin) {
  if (!row.duringNavigation || !row.startedBeforeNavigation ||
      !['fetch','xhr'].includes(row.resourceType) || row.error!=='net::ERR_ABORTED') return false;
  const url=new URL(row.url);
  return url.origin===origin && /\/data\/v69\/(?:world|metropole)\/(?:tiles\/[A-Za-z0-9_.-]+\.(?:terrain|vector)\.json\.gz|layers\/(?:surfaces|navigation)\.[A-Za-z0-9_.-]+\/tiles\/[A-Za-z0-9_.-]+\.(?:surfaces|navigation)\.json\.gz)$/.test(url.pathname);
}

async function run({scope, script, instrumentation, limits=[], scenario}) {
  const opts=options(scope), output=path.resolve(opts.output);
  const report={schema:'soma/browser-'+scope+'/78/1',scope,passed:false,
    startedAt:new Date().toISOString(),environment:{freshNonPersistentContext:true,
      softwareWebGL:true,viewport:{width:1280,height:720}},instrumentation,
    limits:['Bounded automated fixtures are not a human campaign playthrough or a physical traversal of the whole metropolis.',
      'No architectural 1:1 certification, source-only browser fallback, player GPU performance or fresh-cloud restoration claim.',...limits],
    steps:[],screenshots:[],pageErrors:[],consoleErrors:[],httpErrors:[],requestFailures:[]};
  let browser, page, currentStep='launch', navigating=false;
  const requestStarts=new WeakMap();
  const tools={opts, output, report,
    get page(){return page;},
    async step(name, action) {
      currentStep=name;
      const row={name,startedAt:new Date().toISOString()};report.steps.push(row);
      process.stderr.write('[v78 '+scope+'] '+name+'\n');
      try {row.observation=await action();row.status='passed';return row.observation;}
      catch(error){row.status='failed';row.error=String(error.stack||error);throw error;}
      finally {row.finishedAt=new Date().toISOString();}
    },
    async shot(name) {
      const filename=name+'.png';await page.screenshot({path:path.join(output,filename)});
      report.screenshots.push(filename);
    },
    async storage() {
      return page.evaluate(()=>Object.fromEntries(Object.entries(localStorage).sort(([a],[b])=>a.localeCompare(b))));
    },
    async navigate(action) {
      navigating=true;
      try {await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),action()]);}
      finally {navigating=false;}
    },
    async reload() {
      navigating=true;
      try {await page.reload({waitUntil:'domcontentloaded'});}
      finally {navigating=false;}
    },
    async ready() {
      await page.waitForFunction(()=>window.__SOMA_V78__?.ready &&
        window.__SOMA_GROUP64__?.ready && window.__SOMA_V37_SAVE__?.getStatus().ready);
    },
    async errors() {
      assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);
      assert.deepEqual(report.httpErrors,[]);
      for (const row of report.requestFailures) {
        row.expected=expectedSceneAbort(row,new URL(opts.url).origin);
        if(row.expected)row.expectedKind='preexisting-native-scene-resource-cancelled-by-explicit-navigation';
        assert(row.expected,'Unexpected request failure: '+JSON.stringify(row));
      }
      return {pageErrors:0,consoleErrors:0,httpErrors:0,navigationResourceAborts:report.requestFailures.length};
    }};
  await fs.mkdir(output,{recursive:true});
  try {
    report.provenance=await sourceEvidence(script);
    browser=await chromium.launch({executablePath:opts.chromium,headless:true,
      args:['--no-sandbox','--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    report.environment.chromium=browser.version();
    report.environment.playwright=require('playwright/package.json').version;
    const context=await browser.newContext({viewport:report.environment.viewport,locale:'fr-FR'});
    assert.deepEqual((await context.storageState()).origins,[]);
    page=await context.newPage();page.setDefaultTimeout(opts.timeout);
    page.on('pageerror',error=>report.pageErrors.push({step:currentStep,error:String(error.stack||error)}));
    page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push({step:currentStep,text:m.text(),location:m.location()});});
    page.on('response',r=>{if(r.status()>=400)report.httpErrors.push({step:currentStep,status:r.status(),url:r.url()});});
    page.on('request',r=>requestStarts.set(r,{navigating}));
    page.on('requestfailed',r=>report.requestFailures.push({step:currentStep,url:r.url(),
      resourceType:r.resourceType(),error:r.failure()?.errorText,duringNavigation:navigating,
      startedBeforeNavigation:requestStarts.has(r)&&!requestStarts.get(r).navigating}));
    await scenario(tools);
    await tools.step('runtime-errors-remain-empty',tools.errors);
    report.passed=true;
  } catch(error) {
    report.failure=String(error.stack||error);process.exitCode=1;
    if(page)try{await tools.shot('failure');}catch{}
  } finally {
    if(report.provenance)await finishEvidence(report,script);
    report.finishedAt=new Date().toISOString();
    report.counts={passed:report.steps.filter(r=>r.status==='passed').length,
      failed:report.steps.filter(r=>r.status==='failed').length};
    await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
    if(browser)await browser.close();
    process.stdout.write(JSON.stringify({passed:report.passed,counts:report.counts,
      report:path.join(output,'report.json'),failure:report.failure,sourceSetUnchanged:report.sourceSetUnchanged})+'\n');
  }
  return report;
}
module.exports={run,expectedSceneAbort};
