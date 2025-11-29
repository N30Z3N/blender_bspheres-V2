# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

bl_info = {
    'name': 'bSpheres (Modern)',
    'category': '3D View',
    'author': 'Abinadi Cordova (Updated for 4.x+)',
    'version': (1, 2, 0),
    'blender': (4, 0, 0),
    'location': '3D View > N-Panel > bSpheres',
    'description': 'Z-Sphere style base mesh creation using Skin, Mirror, and Subdivision modifiers.',
}

import bpy
import bmesh
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatVectorProperty,
    IntProperty,
    FloatProperty
)
from bpy_extras.object_utils import AddObjectHelper, object_data_add


class OBJECT_OT_ApplyBSphereModifiers(bpy.types.Operator):
    """Apply Mirror, Skin, and Subdivision modifiers and Voxel Remesh"""
    bl_idname = 'tcg.apply_bsphere_modifiers'
    bl_label = 'Apply bSphere Modifiers'
    bl_options = {"REGISTER", "UNDO"}

    voxel_size: FloatProperty(
        name="Voxel Size",
        description="Size of the voxels for remeshing",
        default=0.05,
        min=0.001,
        max=1.0,
        precision=3
    )

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.mode == 'OBJECT'

    def execute(self, context):
        obj = context.object
        
        # Store previous X-Ray state to restore later if desired, 
        # though usually we want it off after applying.
        if context.space_data.type == 'VIEW_3D':
            context.space_data.shading.show_xray = False

        # Apply specific modifiers by name if they exist
        modifiers_to_apply = ["Mirror", "Skin", "Subdivision"]
        
        for mod_name in modifiers_to_apply:
            mod = obj.modifiers.get(mod_name)
            if mod:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError:
                    self.report({'WARNING'}, f"Could not apply modifier: {mod.name}")

        # Remesh Logic
        # We access the mesh data directly via obj.data, not by name lookup
        mesh = obj.data
        mesh.remesh_voxel_size = self.voxel_size
        
        try:
            bpy.ops.object.voxel_remesh()
            self.report({'INFO'}, "bSphere mesh applied and remeshed.")
        except RuntimeError as e:
            self.report({'ERROR'}, f"Remesh failed: {str(e)}")

        return {"FINISHED"}


class MESH_OT_PrimitiveBSphereAdd(bpy.types.Operator, AddObjectHelper):
    """Add a single-vertex bSphere base"""
    bl_idname = "mesh.primitive_bsphere_add"
    bl_label = "Add bSphere"
    bl_options = {'REGISTER', 'UNDO'}

    # Generic transform props handled by AddObjectHelper
    
    def execute(self, context):
        # 1. Create a single vertex at (0,0,0) locally
        mesh = bpy.data.meshes.new("bSphere")
        bm = bmesh.new()
        bm.verts.new((0.0, 0.0, 0.0))
        bm.to_mesh(mesh)
        bm.free()
        
        mesh.update()

        # 2. Add object to scene using modern helper (handles naming, collection linking)
        object_data_add(context, mesh, operator=self)
        
        # 3. Get the active object (the one we just created)
        obj = context.active_object

        # 4. Setup Modifiers
        # Mirror
        mod_mirror = obj.modifiers.new(name="Mirror", type='MIRROR')
        mod_mirror.use_axis = (True, False, False) # X Axis default
        
        # Skin
        mod_skin = obj.modifiers.new(name="Skin", type='SKIN')
        mod_skin.use_x_symmetry = False
        mod_skin.use_y_symmetry = False
        mod_skin.use_z_symmetry = False
        # In newer Blender versions, we might want to toggle 'Smooth Shading' on the skin mod
        # if available, but standard is fine.

        # Subdivision
        mod_sub = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        mod_sub.levels = 2
        mod_sub.render_levels = 2
        
        # 5. Setup Edit Mode & Selection
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Mark Root for Skin Modifier (Critical for stability)
        # We must select the vert first
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.skin_root_mark()
        
        # 6. Viewport Settings
        if context.space_data.type == 'VIEW_3D':
            context.space_data.shading.show_xray = True
        
        return {'FINISHED'}


class VIEW3D_PT_BSpheresPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_bSpheres_Panel'
    bl_label = 'bSpheres'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'bSpheres'

    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        # --- Creation Section ---
        col = layout.column(align=True)
        col.label(text="Create Base:")
        col.operator("mesh.primitive_bsphere_add", text="Create bSphere", icon='MESH_UVSPHERE')
        
        layout.separator()

        # --- Contextual Tools ---
        if obj and obj.type == 'MESH':
            has_bsphere_setup = False
            
            # Check if we have the specific modifiers to decide if we show the controls
            if obj.modifiers.get("Skin") or obj.modifiers.get("Mirror"):
                has_bsphere_setup = True

            if has_bsphere_setup:
                box = layout.box()
                box.label(text="Modifiers", icon='MODIFIER')
                
                # Mirror Controls
                mod_mirror = obj.modifiers.get("Mirror")
                if mod_mirror:
                    row = box.row(align=True)
                    row.label(text="Mirror:")
                    row.prop(mod_mirror, "use_axis", index=0, text="X", toggle=True)
                    row.prop(mod_mirror, "use_axis", index=1, text="Y", toggle=True)
                    row.prop(mod_mirror, "use_axis", index=2, text="Z", toggle=True)
                
                # Subsurf Controls
                mod_sub = obj.modifiers.get("Subdivision")
                if mod_sub:
                    row = box.row(align=True)
                    row.label(text="Subd Level:")
                    row.prop(mod_sub, "levels", text="")

                # Skin Controls
                mod_skin = obj.modifiers.get("Skin")
                if mod_skin:
                    box.separator()
                    col = box.column(align=True)
                    col.label(text="Skin Data (Edit Mode):")
                    
                    row = col.row(align=True)
                    op_mark = row.operator("object.skin_loose_mark_clear", text="Mark Loose")
                    op_mark.action = 'MARK'
                    
                    op_clear = row.operator("object.skin_loose_mark_clear", text="Clear Loose")
                    op_clear.action = 'CLEAR'
                    
                    col.operator("object.skin_root_mark", text="Mark Root", icon='ANCHOR_CENTER')

                # --- Apply / Finish Section ---
                layout.separator()
                col = layout.column(align=True)
                col.label(text="Finalize:")
                
                # Add property specifically for the apply operator
                props = col.operator("tcg.apply_bsphere_modifiers", text="Voxel Remesh & Apply", icon='SCULPTMODE_HLT')
                
                # Info Text
                box_info = layout.box()
                col_info = box_info.column(align=True)
                col_info.scale_y = 0.8
                col_info.label(text="Shortcuts:", icon='INFO')
                col_info.label(text="• Extrude: E")
                col_info.label(text="• Scale Radius: Ctrl + A")
                col_info.label(text="• Split Segment: Ctrl + R")


# --- Registration ---

classes = (
    OBJECT_OT_ApplyBSphereModifiers,
    MESH_OT_PrimitiveBSphereAdd,
    VIEW3D_PT_BSpheresPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    register()
