'use strict';
/* Execute every historical route-preview test against the frozen v72 runtime.
 * Parent files are read-only. The small adaptation list below documents each
 * intentionally changed planning/version expectation; source guards stay exact.
 */
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const parent=path.resolve(__dirname,'../v70/route-preview.test.cjs'),original=fs.readFileSync(parent,'utf8');
let source=original;
function once(old,replacement){assert.equal(source.split(old).length-1,1,'Historical test anchor drift: '+old);source=source.replace(old,replacement);}
const oldPath='../../src/v70/route-preview-core.js';
assert.equal(source.split(oldPath).length-1,2,'Two historical runtime reads must target v72');
source=source.split(oldPath).join('../../src/v72/route-corridor-core.js');
// A direct spine over budget now stops before IO, keeping both endpoint cells.
once('assert.equal(f.requests.length,1);assert.equal(r.route,null);assert.equal(r.coverage.requestedCells,2);',
 'assert.equal(f.requests.length,0);assert.equal(r.code,"corridor_cell_budget");assert.equal(r.route,null);assert.equal(r.coverage.requestedCells,2);');
// The documented hard cell ceiling increased from64 to192.
once('budgets:{maxCells:65}','budgets:{maxCells:193}');
// The post-search deadline test must exceed the actual configured default.
once('time=4000;return out;','time=Preview.DEFAULTS.maxMilliseconds+1;return out;');
once("context.__SOMA_ROUTE70_CORE__.VERSION,'0.70.0'","context.__SOMA_ROUTE70_CORE__.VERSION,'0.72.0'");
// The exact clipped corridor is narrower than the historical circumscribed
// corridor. Keep the real golden path, source turns, byte/memory bounds and
// source immutability assertions; require complete bounded corridor coverage.
once('assert.equal(loads.length,15);',
 'assert.equal(loads.length,r.coverage.selectedCells.length);assert(loads.length<=96);assert.equal(r.coverage.completeRequestedSector,true);');
source=source.replace(/test\('/g,"test('historical conformance72: ");
const derived=new Module(parent,module);derived.filename=parent;derived.paths=Module._nodeModulePaths(path.dirname(parent));
derived._compile(source,parent);
assert.equal(fs.readFileSync(parent,'utf8'),original,'Historical test source changed');
