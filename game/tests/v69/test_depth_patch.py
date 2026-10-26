"""Surface-only depth layers preserve source coordinates and close geometry."""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME / "tools"))
from v69_depth import patch_depth


def script(html, name):
    matches = re.findall(r'<script\b[^>]*\bid="' + re.escape(name) + r'"[^>]*>(.*?)</script>', html, re.S)
    if len(matches) != 1:
        raise AssertionError("Expected exactly one source script: " + name)
    return matches[0]


def function(source, name):
    start = source.index("function " + name + "(")
    end = re.search(r"\nfunction \w+\(", source[start:])
    if end is None:
        raise AssertionError("Missing function boundary: " + name)
    return source[start:start + end.start()]


class DepthPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = GAME / "baseline/v66.html"
        if not cls.path.exists():
            raise unittest.SkipTest("Prepare the verified original game first")
        cls.original = cls.path.read_text(encoding="utf-8")
        cls.patched = patch_depth(cls.original)

    def test_projection_and_every_embedded_geographic_payload_remain_identical(self):
        projection = "M4.perspective(proj,currentFovRadians(),this.c.width/this.c.height,.05,420);"
        self.assertEqual(self.original.count(projection), 2)
        self.assertEqual(self.patched.count(projection), 2)
        pattern = re.compile(r'<script\b[^>]*\btype="application/json"[^>]*>.*?</script>', re.S)
        self.assertEqual(pattern.findall(self.original), pattern.findall(self.patched))
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),
                         "f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014")

    def test_patch_is_idempotent_and_refuses_partial_or_missing_anchors(self):
        self.assertEqual(patch_depth(self.patched), self.patched)
        for broken in (self.original.replace("function preciseSurface(", "function unknownSurface(", 1),
                       self.original.replace("vNormal=aNormal;float d=", "vNormal=aNormal; float d=", 1),
                       self.patched.replace("v69Normal(K.normal(...lifted))", "K.normal(...lifted)", 1),
                       self.patched + '<script id="soma-v56-terrain-runtime"></script>'):
            with self.assertRaises(ValueError):
                patch_depth(broken)
        with self.assertRaises(TypeError):
            patch_depth(None)

    @unittest.skipUnless(shutil.which("node"), "Node is required to execute actual terrain emitters")
    def test_real_surface_emitters_keep_xyz_and_the_core_normal_untouched(self):
        original = function(script(self.original, "soma-v56-terrain-runtime"), "preciseSurface")
        patched = function(script(self.patched, "soma-v56-terrain-runtime"), "preciseSurface")
        runner = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
function execute(source,height,override){
 const rows=[],normal=()=>[0,.8,.6],scope={kind:'surface',zone:{v50Record:{boundsL93:[0,0,250,250]}}};
 const c=vm.createContext({grid:{},window:{__SOMA_SIGHT61_CORE__:{oneTerrainTriangle:()=>true}},stats:{},K:{normal},
   transform:p=>[p[0],p[1]+7,p[2]],rawTri(...args){rows.push(args)}});
 vm.runInContext(source,c);
 const g={__v56:scope};if(override!==undefined)g.__v69DepthLayer=override;
 c.preciseSurface(g,[1,height,1],[3,height,1],[1,height,3],[.2,.3,.4]);
 assert.deepEqual(normal(),[0,.8,.6]);
 return rows[0];
}
for(const height of [.004,.031,.035,.037,.04,.045,.067,.075]){
 const before=execute(input.original,height),after=execute(input.patched,height);
 assert.equal(JSON.stringify(after.slice(0,3)),JSON.stringify(before.slice(0,3)));
 assert.equal(JSON.stringify(after[4]),JSON.stringify(before[4]));
 const magnitude=Math.hypot(...after[3]);assert(magnitude>=17&&magnitude<=26);
 assert(Math.abs(after[3][1]/magnitude-before[3][1])<1e-12);
 assert(Math.abs(after[3][2]/magnitude-before[3][2])<1e-12);
}
const background=execute(input.patched,.004,1),park=execute(input.patched,.004,3);
assert(Math.hypot(...park[3])>Math.hypot(...background[3]));
assert.equal(JSON.stringify(background.slice(0,3)),JSON.stringify(park.slice(0,3)));
console.log('source XYZ, normal orientation, materials and park ordering preserved');
"""
        import json
        result = subprocess.run([shutil.which("node"), "-e", runner], input=json.dumps({"original": original, "patched": patched}),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is required for source land-use scope tests")
    def test_real_landuse_priority_restores_geometry_scope_even_after_an_error(self):
        source = function(script(self.patched, "soma-v50-playable-truth-cells"), "addLanduse53")
        runner = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync(0,'utf8'),layers=[];
let fail=false;
const c=vm.createContext({geometryMesh53:()=>({source:'same mesh'}),palette:()=>({park:[0,1,0],industrial:[1,0,1]}),
 drawMesh53(g,mesh,y,col){layers.push({layer:g.__v69DepthLayer,y});if(fail)throw Error('draw interrupted')}});
vm.runInContext(source,c);
const g={};c.addLanduse53({},g,[],{leisure:'park'});assert.equal(layers[0].layer,3);assert.equal(layers[0].y,.004);
assert.equal(Object.hasOwn(g,'__v69DepthLayer'),false);
g.__v69DepthLayer=9;c.addLanduse53({},g,[],{landuse:'residential'});assert.equal(layers[1].layer,1);assert.equal(g.__v69DepthLayer,9);
fail=true;assert.throws(()=>c.addLanduse53({},g,[],{natural:'wood'}));assert.equal(g.__v69DepthLayer,9);
console.log('temporary render scope restored');
"""
        result = subprocess.run([shutil.which("node"), "-e", runner], input=source, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_terrain_building_collision_and_weapon_implementations_are_not_rewritten(self):
        before = script(self.original, "soma-v56-terrain-runtime")
        after = script(self.patched, "soma-v56-terrain-runtime")
        for name in ("buildTerrain", "building", "water", "vehicleObject", "poseVehicle", "poseCamera", "footprintValid"):
            self.assertEqual(function(before, name), function(after, name))
        for name in ("soma-v56-terrain-core", "soma-v57-core", "soma-v63-nav-core"):
            self.assertEqual(script(self.original, name), script(self.patched, name))
        weapon_lines = r"^.*(?:function weaponGeo\(|weaponGeo=function).*$"
        self.assertEqual(re.findall(weapon_lines, self.original, re.M), re.findall(weapon_lines, self.patched, re.M))
        self.assertNotIn("gl_FragDepth", self.patched)


if __name__ == "__main__":
    unittest.main()
