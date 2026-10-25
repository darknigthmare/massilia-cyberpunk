"""Separate rendered ground overlays in depth without moving their geometry.

The original near plane (5 cm), projection, positions and collision data remain
unchanged. Only source-ground surface normals carry a small render-layer marker;
the vertex shader decodes the original normal before lighting/wetness and shifts
clip depth by one 24-bit depth-buffer unit per layer. No fragment-depth write is
needed, so the existing early-depth path remains available.
"""
import re

_MARKER = "/* SOMA 0.69: deterministic source-surface depth layers. */"
_SURFACE_START = "function preciseSurface(g,a,b,c,col){\n"
_SURFACE_HELPER = r"""function preciseSurface(g,a,b,c,col){
/* SOMA 0.69: deterministic source-surface depth layers. */
 const v69Offset=(a[1]+b[1]+c[1])/3;
 const v69Layer=g.__v69DepthLayer??(v69Offset<.02?1:v69Offset<.033?4:v69Offset<.036?5:v69Offset<.039?6:v69Offset<.043?7:v69Offset<.055?8:v69Offset<.071?9:10);
 const v69Normal=n=>n.map(value=>value*(16+v69Layer));
"""
_OLD_LANDUSE = "drawMesh53(g,mesh,.004,green?pal.park:pal.industrial);"
_NEW_LANDUSE = """const v69PreviousLayer=g.__v69DepthLayer;g.__v69DepthLayer=green?3:1;
 try{drawMesh53(g,mesh,.004,green?pal.park:pal.industrial);}
 finally{if(v69PreviousLayer===undefined)delete g.__v69DepthLayer;else g.__v69DepthLayer=v69PreviousLayer;}"""
_OLD_POSITION = "gl_Position=uVP*vec4(aPos,1.0);float li="
_NEW_POSITION = (
    "gl_Position=uVP*vec4(aPos,1.0);"
    "float v69NormalLength=length(aNormal);"
    "float v69SurfaceLayer=(v69NormalLength>16.5&&v69NormalLength<26.5)?floor(v69NormalLength-16.0+0.5):0.0;"
    "gl_Position.z-=gl_Position.w*v69SurfaceLayer*1.1920928955078125e-7;"
    "float li="
)
_OLD_VARYING = "vNormal=aNormal;float d="
_NEW_VARYING = "vNormal=v69SurfaceLayer>0.0?aNormal/v69NormalLength:aNormal;float d="


def _once(text, old, new, name):
    if text.count(old) != 1:
        raise ValueError(f"Unexpected depth-patch anchor: {name}")
    return text.replace(old, new, 1)


def _script(html, script_id, rewrite):
    pattern = re.compile(r'(<script\b[^>]*\bid="' + re.escape(script_id) + r'"[^>]*>)(.*?)(</script>)', re.S)
    if len(pattern.findall(html)) != 1:
        raise ValueError(f"Depth patch script missing or duplicated: {script_id}")
    return pattern.sub(lambda match: match[1] + rewrite(match[2]) + match[3], html, count=1)


def _terrain(script):
    if script.count(_SURFACE_START) != 1 or script.count("function surfaceTriangle(") != 1:
        raise ValueError("Unexpected terrain surface function")
    start = script.index(_SURFACE_START)
    end = script.index("function surfaceTriangle(", start)
    surface = script[start:end]
    if surface.count("K.normal(...lifted)") != 2:
        raise ValueError("Unexpected fast/clipped surface triangle emitters")
    surface = surface.replace(_SURFACE_START, _SURFACE_HELPER, 1)
    surface = surface.replace("K.normal(...lifted)", "v69Normal(K.normal(...lifted))")
    return script[:start] + surface + script[end:]


def patch_depth(html: str) -> str:
    """Apply once, or preserve an intact existing patch; refuse partial drift.

    Both roads and source land-use polygons retain their XYZ coordinates. Land
    use receives a visual priority: mapped park/grass/wood cover is drawn above
    the broad industrial/residential background when their polygons overlap.
    Rigid buildings, water, actors, weapons and terrain triangles are unmarked.
    """
    if not isinstance(html, str):
        raise TypeError("Depth patch expects HTML text")
    for script_id in ("soma-v56-terrain-runtime", "soma-v50-playable-truth-cells"):
        pattern = r'<script\b[^>]*\bid="' + re.escape(script_id) + r'"[^>]*>'
        if len(re.findall(pattern, html)) != 1:
            raise ValueError(f"Depth patch script missing or duplicated: {script_id}")
    if _MARKER in html:
        checks = ((_MARKER, 1), (_SURFACE_HELPER, 1),
                  ("v69Normal(K.normal(...lifted))", 2), (_NEW_LANDUSE, 1),
                  (_NEW_POSITION, 1), (_NEW_VARYING, 1))
        if any(html.count(anchor) != count for anchor, count in checks):
            raise ValueError("Depth patch is partial or has drifted")
        if _OLD_POSITION in html or _OLD_VARYING in html:
            raise ValueError("Depth patch has mixed old and new shader paths")
        return html
    if "v69SurfaceLayer" in html or "__v69DepthLayer" in html:
        raise ValueError("Unexpected partial depth-patch state")
    output = _script(html, "soma-v56-terrain-runtime", _terrain)
    output = _script(output, "soma-v50-playable-truth-cells",
                     lambda script: _once(script, _OLD_LANDUSE, _NEW_LANDUSE, "source land-use priority"))
    output = _once(output, _OLD_POSITION, _NEW_POSITION, "world vertex position")
    return _once(output, _OLD_VARYING, _NEW_VARYING, "decoded surface normal")
