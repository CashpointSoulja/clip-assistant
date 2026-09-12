import bpy, math, os
from mathutils import Vector

ROOT = "/Users/whtnybiatch/Documents/ChatGPT/steve barlet/clip-assistant"
OUT = os.path.join(ROOT, "web/assets/3d")
os.makedirs(OUT, exist_ok=True)

# Clean only this new scene; no user scene is opened or modified.
bpy.ops.wm.read_factory_settings(use_empty=True)

def mat(name, color, metallic=0.0, rough=0.45):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metallic
    return m

YELLOW = mat("Steven Yellow", (0.78, 0.56, 0.015), 0.05, 0.28)
CHALK = mat("Chalk White", (0.86, 0.89, 0.91), 0.0, 0.52)
CHARCOAL = mat("Charcoal", (0.035, 0.04, 0.045), 0.08, 0.3)
CHROME = mat("Soft Chrome", (0.5, 0.53, 0.56), 0.72, 0.2)

def mesh_obj(name, verts, faces, material):
    me = bpy.data.meshes.new(name + "Mesh")
    me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob

def cube(name, loc, scale, material, bevel=0.0, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    ob = bpy.context.object; ob.name = name; ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = ob.modifiers.new("Soft edges", "BEVEL"); mod.width = bevel; mod.segments = 2
    ob.data.materials.append(material)
    return ob

# Sculptural solid ribbon: a broad looped editing strip with a subtle twist.
N = 72; width = 0.78; thick = 0.10
center=[]; left=[]; right=[]
for i in range(N):
    t = 2*math.pi*i/(N-1)
    p = Vector((1.78*math.sin(t), 0.68*math.sin(2*t), 1.62*math.cos(t) + 0.18*math.sin(t)))
    tangent = Vector((1.78*math.cos(t), 1.36*math.cos(2*t), -1.62*math.sin(t) + 0.18*math.cos(t))).normalized()
    side = tangent.cross(Vector((0, 1, 0))).normalized()
    center.append(p); left.append(p + side*width/2); right.append(p - side*width/2)
verts=[]
for side in (left,right):
    verts += [(p.x,p.y-thick/2,p.z) for p in side]
    verts += [(p.x,p.y+thick/2,p.z) for p in side]
faces=[]
for base in (0, 2*N):
    for i in range(N-1):
        a=base+i; b=base+i+1; c=base+N+i+1; d=base+N+i
        faces.append((a,b,c,d) if base==0 else (d,c,b,a))
# connect both strip edges and end caps
for i in range(N-1):
    faces += [(i,i+1,2*N+i+1,2*N+i), (N+i,N+i+1,3*N+i+1,3*N+i)]
faces += [(0,N,3*N,2*N), (N-1,2*N-1,4*N-1,3*N-1)]
ribbon=mesh_obj("Hero Editing Ribbon", verts, faces, CHROME)
ribbon.data.materials.append(YELLOW)
# One restrained yellow edit marker keeps the interaction cue visible in the light theme.
for poly in ribbon.data.polygons:
    if 9 <= poly.index <= 11: poly.material_index = 1
    poly.use_smooth = True
bev=ribbon.modifiers.new("Rounded ribbon edges", "BEVEL"); bev.width=0.055; bev.segments=2

# A thin second rail makes the loop read as an orbital editing gesture in motion.
rail_curve = bpy.data.curves.new("Secondary Orbital Rail", "CURVE"); rail_curve.dimensions='3D'; rail_curve.bevel_depth=0.035; rail_curve.bevel_resolution=3; rail_curve.resolution_u=2
rail = rail_curve.splines.new('POLY'); rail.points.add(47)
for i, pt in enumerate(rail.points):
    t=2*math.pi*i/47; pt.co=(2.08*math.sin(t), 0.78*math.sin(2*t)+0.12, 1.9*math.cos(t)+0.18*math.sin(t), 1)
rail_ob=bpy.data.objects.new("Secondary Orbital Rail", rail_curve); bpy.context.collection.objects.link(rail_ob); rail_curve.materials.append(CHROME)

# Three floating editorial frame cards, clearly readable as story/edit beats.
for idx, (ang, scale, tilt) in enumerate([(0.30,1.0,-0.14),(2.35,0.82,0.18),(4.55,0.72,-0.2)]):
    x=1.78*math.sin(ang); z=1.62*math.cos(ang) + 0.18*math.sin(ang); y=0.68*math.sin(2*ang)+0.48
    loc=(x, y, z)
    frame=cube(f"Editorial Frame {idx+1}", loc, (0.63*scale,0.07,0.43*scale), CHALK, 0.06, (0,tilt,ang*0.08))
    # screen and timeline bars sit just forward of the card
    screen=cube(f"Frame {idx+1} Screen", (x,y-0.082,z), (0.49*scale,0.012,0.25*scale), CHARCOAL, 0.025, (0,tilt,ang*0.08))
    bar=cube(f"Frame {idx+1} Timeline", (x-0.10*scale,y-0.1,z-0.32*scale), (0.25*scale,0.014,0.035*scale), YELLOW, 0.018, (0,tilt,ang*0.08))
    tick=cube(f"Frame {idx+1} Playhead", (x+0.24*scale,y-0.103,z-0.32*scale), (0.018*scale,0.015,0.075*scale), CHROME, 0.01, (0,tilt,ang*0.08))

# Small chrome reels/markers add film language without texture weight.
for i, ang in enumerate([0.9, 3.5, 5.55]):
    x=1.95*math.sin(ang); z=1.9*math.cos(ang)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.13, depth=0.055, location=(x,0.18,z), rotation=(math.pi/2,0,0))
    ob=bpy.context.object; ob.name=f"Chrome Reel {i+1}"; ob.data.materials.append(CHROME)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.045, depth=0.065, location=(x,0.17,z), rotation=(math.pi/2,0,0))
    bpy.context.object.name=f"Reel Hub {i+1}"; bpy.context.object.data.materials.append(CHARCOAL)

# Camera: centered origin contract, transparent poster composition.
bpy.ops.object.camera_add(location=(5.0,-8.5,3.7))
cam=bpy.context.object; cam.name="Hero Camera"; bpy.context.scene.camera=cam
def point_at(ob, target): ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
point_at(cam,(0,0,0)); cam.data.type='ORTHO'; cam.data.ortho_scale=5.6

world=bpy.context.scene.world or bpy.data.worlds.new("World"); bpy.context.scene.world=world
world.use_nodes=True; world.node_tree.nodes["Background"].inputs["Color"].default_value=(0.04,0.045,0.05,1); world.node_tree.nodes["Background"].inputs["Strength"].default_value=0.22
for name, loc, energy, size, color in [("Key",(4,-4,6),900,4.0,(1.0,0.86,0.58)),("Fill",(-4,-2,3),500,3.0,(0.65,0.78,1.0)),("Rim",(0,4,4),700,2.5,(1.0,0.72,0.25))]:
    bpy.ops.object.light_add(type='AREA', location=loc); l=bpy.context.object; l.name=name; l.data.energy=energy; l.data.shape='DISK'; l.data.size=size; l.data.color=color; point_at(l,(0,0,0))

scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=1000; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'; scene.render.film_transparent=True
scene.render.filepath=os.path.join(OUT,"hero-poster.png")
scene.render.image_settings.color_depth='8'; scene.render.image_settings.compression=25
scene.view_settings.look='AgX - Medium High Contrast'

# Save source and export web-ready GLB.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,"hero.blend"))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,"hero.glb"), export_format='GLB', export_apply=True, export_materials='EXPORT', export_cameras=False, export_lights=False)
bpy.ops.render.render(write_still=True)

result={"objects":len(bpy.context.scene.objects),"verts":sum(len(o.data.vertices) for o in bpy.context.scene.objects if o.type=='MESH'),"path":OUT}
