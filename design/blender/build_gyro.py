import bpy, math, os
from mathutils import Vector

ROOT='/Users/whtnybiatch/Documents/ChatGPT/steve barlet/clip-assistant'; OUT=os.path.join(ROOT,'web/assets/3d'); os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
def material(name,color,metallic=.8,rough=.18):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Metallic'].default_value=metallic; p.inputs['Roughness'].default_value=rough; return m
chrome=material('Cool brushed chrome',(0.48,.56,.65),.92,.16); dark=material('Graphite inset',(.025,.035,.05),.75,.2); yellow=material('Steven yellow',(.9,.63,.02),.45,.2)
def smooth(obj,bev=0):
 if hasattr(obj.data,'polygons'):
  for f in obj.data.polygons:f.use_smooth=True
 if bev: m=obj.modifiers.new('Soft polished edge','BEVEL');m.width=bev;m.segments=3
 return obj
def torus(name,major,minor,rot=(0,0,0),scale=(1,1,1),mat=chrome):
 bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=12,location=(0,0,0),rotation=rot)
 o=smooth(bpy.context.object);o.name=name;o.scale=scale;o.data.materials.append(mat);return o

# Three broad, smooth bands on crossing axes: a gyroscopic editorial signal.
torus('Orbital band A',2.0,.16,(0,0,0),(.98,1,.72))
torus('Orbital band B',2.0,.16,(math.pi/2,0,.32),(1,.98,.72))
torus('Orbital band C',1.86,.14,(0,math.pi/2,-.45),(.86,1.06,1),chrome)
# Center volume and tiny edit-color indicator.
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=.54); orb=smooth(bpy.context.object,.015);orb.name='Chrome signal core';orb.data.materials.append(chrome)
bpy.ops.mesh.primitive_torus_add(major_radius=.58,minor_radius=.025,major_segments=48,minor_segments=8,rotation=(math.pi/2,0,0));accent=smooth(bpy.context.object);accent.name='Yellow edit marker';accent.data.materials.append(yellow)
# Small dark hub makes the sphere read as an intentional editorial instrument.
bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.12,depth=.08,rotation=(math.pi/2,0,0));hub=bpy.context.object;hub.name='Core hub';hub.data.materials.append(dark)

def point(ob,target=(0,0,0)):ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(5.6,-8.4,3.4));cam=bpy.context.object;cam.name='Hero Camera';cam.data.type='ORTHO';cam.data.ortho_scale=5.35;bpy.context.scene.camera=cam;point(cam)
world=bpy.data.worlds.new('Pale studio world');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.78,.82,.86,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for name,loc,energy,size,color in [('Key',(4,-4,6),1050,4,(.82,.9,1)),('Fill',(-4,-2,3),650,4,(.55,.7,1)),('Rim',(1,4,5),900,3,(1,.85,.62))]:
 bpy.ops.object.light_add(type='AREA',location=loc);l=bpy.context.object;l.name=name;l.data.energy=energy;l.data.shape='DISK';l.data.size=size;l.data.color=color;point(l)
s=bpy.context.scene;s.render.engine='BLENDER_EEVEE';s.render.resolution_x=1000;s.render.resolution_y=1000;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.film_transparent=True;s.render.filepath=os.path.join(OUT,'hero-poster.png');s.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'hero.blend'));bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,'hero.glb'),export_format='GLB',export_apply=True,export_materials='EXPORT',export_cameras=False,export_lights=False);bpy.ops.render.render(write_still=True)
