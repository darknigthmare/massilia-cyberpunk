'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const A=require('../../src/v74/architecture-datum-core.js');
const ref=ring=>({complete:true,outerCount:1,hasHoles:false,rings:[ring]});
test('containment proves complete edges, including a concave excursion whose vertices are inside',()=>{
  const parent=ref([[0,0],[10,0],[10,10],[6,10],[6,4],[4,4],[4,10],[0,10]]);
  assert.equal(A.contained(ref([[1,1],[9,1],[9,3],[1,3]]),parent),true);
  assert.equal(A.contained(ref([[1,2],[9,2],[9,8],[1,8]]),parent),false);
});
test('coordinate tolerance accepts millimetres but refuses centimetre overhangs, holes and incomplete source walls',()=>{
  const parent=ref([[0,0],[10,0],[10,10],[0,10]]);
  assert.equal(A.contained(ref([[-.004,1],[3,1],[3,3],[-.004,3]]),parent),true);
  assert.equal(A.contained(ref([[-.011,1],[3,1],[3,3],[-.011,3]]),parent),false);
  assert.equal(A.contained(ref([[1,1],[3,1],[3,3],[1,3]]),{...parent,hasHoles:true}),false);
  assert.equal(A.contained({...parent,complete:false},parent),false);
  assert.equal(A.contained(parent,parent,.02),false);
});
