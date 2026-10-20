# SPDX-License-Identifier: GPL-3.0-or-later

# ViewReal: ディスプレイの物理サイズをもとに、3D ビューポートを実寸表示にズームするアドオン

import math
import sys

import bpy

INCH_TO_M = 0.0254


# ---------------------------------------------------------------------------
# 解像度の自動取得（Windows のみ）
# ---------------------------------------------------------------------------

def detect_resolution():
    """メインモニターの解像度（実ピクセル）を (幅, 高さ) で返す。取れなければ None。"""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        user32.GetDC.restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]

        hdc = user32.GetDC(None)
        try:
            # DESKTOPHORZRES / DESKTOPVERTRES は Windows の拡大率に関係なく実ピクセルを返す
            width = gdi32.GetDeviceCaps(hdc, 118)
            height = gdi32.GetDeviceCaps(hdc, 117)
        finally:
            user32.ReleaseDC(None, hdc)
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def apply_detected_resolution(prefs):
    """自動取得した解像度を設定に書き込む。成功したら True。"""
    res = detect_resolution()
    if res is None:
        return False
    prefs.res_x, prefs.res_y = res
    return True


def calc_ppi(prefs):
    if prefs.display_inch <= 0 or prefs.res_x <= 0 or prefs.res_y <= 0:
        return 0.0
    return math.hypot(prefs.res_x, prefs.res_y) / prefs.display_inch


def get_prefs(context):
    return context.preferences.addons[__package__].preferences


# ---------------------------------------------------------------------------
# 設定（どの .blend ファイルでも共通）
# ---------------------------------------------------------------------------

def on_mode_update(self, context):
    if self.resolution_mode == 'AUTO':
        apply_detected_resolution(self)


class ViewRealPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    display_inch: bpy.props.FloatProperty(
        name="Display Size",
        description="ディスプレイの対角サイズ（インチ）",
        default=24.0,
        min=1.0,
        soft_max=100.0,
        precision=1,
    )
    resolution_mode: bpy.props.EnumProperty(
        name="Resolution",
        items=[
            ('AUTO', "Auto", "画面の解像度を自動で取得する（Windows のみ）"),
            ('MANUAL', "Manual", "画面の解像度を手で入力する"),
        ],
        default='AUTO',
        update=on_mode_update,
    )
    view_scale: bpy.props.FloatProperty(
        name="Scale",
        description="表示倍率。1.0 で実寸、0.1 で 1/10、2.0 で 2倍の大きさに表示する",
        default=1.0,
        min=0.0001,
        soft_min=0.01,
        soft_max=10.0,
        step=10,
        precision=3,
    )
    res_x: bpy.props.IntProperty(name="X", default=1920, min=1, subtype='PIXEL')
    res_y: bpy.props.IntProperty(name="Y", default=1080, min=1, subtype='PIXEL')

    def draw(self, context):
        draw_settings(self.layout, self)


def draw_settings(layout, prefs):
    layout.use_property_split = True
    layout.use_property_decorate = False

    col = layout.column()
    col.prop(prefs, "display_inch", text="Display Size (inch)")
    col.row().prop(prefs, "resolution_mode", expand=True)

    sub = col.column(align=True)
    sub.enabled = prefs.resolution_mode == 'MANUAL'
    sub.prop(prefs, "res_x", text="Resolution X")
    sub.prop(prefs, "res_y", text="Y")

    if prefs.resolution_mode == 'AUTO':
        col.operator(VIEWREAL_OT_detect_resolution.bl_idname, icon='FILE_REFRESH')

    col.label(text=f"PPI: {calc_ppi(prefs):.1f}")

    layout.separator()
    layout.prop(prefs, "view_scale")


# ---------------------------------------------------------------------------
# オペレーター
# ---------------------------------------------------------------------------

class VIEWREAL_OT_detect_resolution(bpy.types.Operator):
    bl_idname = "viewreal.detect_resolution"
    bl_label = "Detect"
    bl_description = "画面の解像度を自動で取得し直す"

    def execute(self, context):
        prefs = get_prefs(context)
        if not apply_detected_resolution(prefs):
            self.report({'WARNING'}, "解像度を取得できませんでした。Manual で入力してください")
            return {'CANCELLED'}
        self.report({'INFO'}, f"解像度: {prefs.res_x} x {prefs.res_y}")
        return {'FINISHED'}


class VIEWREAL_OT_set_real_view(bpy.types.Operator):
    bl_idname = "viewreal.set_real_view"
    bl_label = "Set Real View"
    bl_description = "ビューの中心にある物が実寸で見えるようにズームする"

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        space = context.space_data
        rv3d = space.region_3d

        if space.region_quadviews:
            self.report({'WARNING'}, "4分割表示（Quad View）には対応していません")
            return {'CANCELLED'}
        if rv3d.view_perspective == 'CAMERA':
            self.report({'WARNING'}, "カメラビュー中は使えません。カメラビューを抜けてから押してください")
            return {'CANCELLED'}

        prefs = get_prefs(context)
        if prefs.resolution_mode == 'AUTO' and not apply_detected_resolution(prefs):
            self.report({'WARNING'}, "解像度を自動取得できなかったため、保存済みの値を使います")

        ppi = calc_ppi(prefs)
        if ppi <= 0:
            self.report({'ERROR'}, "ディスプレイのサイズと解像度を正しく入力してください")
            return {'CANCELLED'}

        # ボタンはサイドバーにあるので、同じエリアの描画領域（WINDOW）を探す
        region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if region is None or region.width <= 0:
            return {'CANCELLED'}

        # 今のズームで、ビューの中心の奥行きにある 1 Blender 単位が何 px で表示されているか
        proj_x = rv3d.window_matrix[0][0]
        distance = rv3d.view_distance
        if rv3d.view_perspective == 'PERSP':
            current_px = proj_x * region.width / (2.0 * distance)
        else:
            current_px = proj_x * region.width / 2.0

        # 実寸のときに 1 Blender 単位が何 px になるべきか
        meters_per_unit = context.scene.unit_settings.scale_length
        target_px = ppi / INCH_TO_M * meters_per_unit * prefs.view_scale

        # 透視でも平行投影でも、表示の大きさは view_distance に反比例する
        rv3d.view_distance = distance * current_px / target_px
        context.area.tag_redraw()

        self.report({'INFO'}, f"実寸 x{prefs.view_scale:g} で表示しました（PPI {ppi:.1f}）")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# パネル（サイドバー > Item）
# ---------------------------------------------------------------------------

class VIEWREAL_PT_panel(bpy.types.Panel):
    bl_label = "ViewReal"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"

    def draw(self, context):
        prefs = get_prefs(context)
        draw_settings(self.layout, prefs)
        self.layout.separator()
        self.layout.operator(VIEWREAL_OT_set_real_view.bl_idname, icon='ZOOM_ALL')


# ---------------------------------------------------------------------------

classes = (
    ViewRealPreferences,
    VIEWREAL_OT_detect_resolution,
    VIEWREAL_OT_set_real_view,
    VIEWREAL_PT_panel,
)


def _detect_on_startup():
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
    except KeyError:
        return None
    if prefs.resolution_mode == 'AUTO':
        apply_detected_resolution(prefs)
    return None


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(_detect_on_startup, first_interval=0.5)


def unregister():
    if bpy.app.timers.is_registered(_detect_on_startup):
        bpy.app.timers.unregister(_detect_on_startup)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
