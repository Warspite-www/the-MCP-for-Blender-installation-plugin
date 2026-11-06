bl_info = {
    'name': 'MCP for Blender Installer',
    'author': 'MCP-for-blender-install contributors',
    'version': (1, 0, 0),
    'blender': (4, 2, 0),
    'location': 'Preferences > Add-ons > MCP for Blender Installer',
    'description': 'Install MCP for Blender and optionally configure Codex on Windows',
    'category': 'Interface',
}

import bpy
from bpy.props import BoolProperty
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import urllib.request
import uuid


_events = queue.Queue()
_busy = False
_status = '就绪。请先保存当前场景。'
_log = []
_active = False


def _run(args, timeout=1800):
    result = subprocess.run(
        [str(arg) for arg in args], capture_output=True,
        encoding='utf-8', errors='replace', timeout=timeout,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or 'No output').strip()
        raise RuntimeError(detail[-6000:])
    return result.stdout


def _backup(path):
    path = Path(path)
    if path.is_file():
        shutil.copy2(path, path.with_name(path.name + '.before-blender-mcp-' + uuid.uuid4().hex + '.bak'))


def _find_codex():
    found = shutil.which('codex.exe') or shutil.which('codex')
    if found:
        return found
    # Codex bundled with the VS Code extension may not be on PATH.
    candidates = list((Path.home() / '.vscode' / 'extensions').glob(
        'openai.chatgpt-*/bin/windows-x86_64/codex.exe'))
    if not candidates:
        return None
    return str(max(candidates, key=lambda p: p.stat().st_mtime))


def _worker(addons_dir, configure_codex):
    try:
        codex = _find_codex() if configure_codex else None
        if configure_codex and not codex:
            raise RuntimeError('找不到 Codex CLI。请先安装，或取消“同时配置 Codex”后重试。')

        uvx = shutil.which('uvx.exe')
        if not uvx:
            default = Path.home() / '.local' / 'bin' / 'uvx.exe'
            if default.is_file():
                uvx = str(default)
        if not uvx:
            _events.put(('status', '正在通过 Astral 官方安装器安装 uv……'))
            with tempfile.TemporaryDirectory(prefix='blender-mcp-uv-') as folder:
                installer = Path(folder) / 'install-uv.ps1'
                with urllib.request.urlopen('https://astral.sh/uv/install.ps1', timeout=60) as response:
                    installer.write_bytes(response.read())
                _run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', installer])
            default = Path.home() / '.local' / 'bin' / 'uvx.exe'
            uvx = str(default) if default.is_file() else shutil.which('uvx.exe')
            if not uvx:
                raise RuntimeError('uv 安装后仍找不到 uvx。请重启 Blender 后重试。')

        _events.put(('status', '正在下载 MCP 依赖和安装插件，首次可能需要数分钟……'))
        _backup(Path(addons_dir) / 'blender_mcp.py')
        _run([uvx, 'mcp-for-blender', 'install-addon', '--addons-dir', addons_dir])

        if configure_codex:
            _events.put(('status', '正在检查 Codex MCP 配置……'))
            # get returns a failure when the named entry does not exist.
            result = subprocess.run(
                [codex, 'mcp', 'get', 'blender'], capture_output=True,
                timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            if result.returncode == 0:
                _events.put(('log', '已有 Codex blender 注册项已保留；请自行确认其启动命令。'))
            else:
                codex_root = Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex'))
                _backup(codex_root / 'config.toml')
                _run([codex, 'mcp', 'add', 'blender', '--env', 'DISABLE_TELEMETRY=true',
                      '--', uvx, 'mcp-for-blender'], timeout=60)
                _events.put(('log', 'Codex MCP 已注册。请完全退出并重启 Codex / VS Code。'))
        _events.put(('enable', None))
    except Exception as exc:
        _events.put(('error', str(exc)))


def _redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'PREFERENCES', 'VIEW_3D'}:
                area.tag_redraw()


def _poll():
    global _busy, _status
    if not _active:
        return None
    while True:
        try:
            event, message = _events.get_nowait()
        except queue.Empty:
            break
        if event == 'status':
            _status = message
        elif event == 'log':
            _log.append(message)
        elif event == 'error':
            _busy = False
            _status = '安装失败：请查看下方详情，修复后重试。'
            _log.append(message)
        elif event == 'enable':
            try:
                # Blender API must only be used on Blender's main thread.
                import addon_utils
                addon_utils.modules_refresh()
                addon_utils.enable('blender_mcp', default_set=True, persistent=True)
                if 'blender_mcp' not in bpy.context.preferences.addons:
                    raise RuntimeError('插件未能启用，请检查 Blender 系统控制台。')
                _backup(Path(bpy.utils.user_resource('CONFIG')) / 'userpref.blend')
                bpy.ops.wm.save_userpref()
                _status = '安装并启用成功。3D 视图按 N → MCP for Blender。'
                _log.append('MCP 服务器通常会自动启动；如未启动，请点击 Start MCP Server。')
            except Exception as exc:
                _status = '文件已安装，但启用或保存失败。请查看详情。'
                _log.append(str(exc))
            finally:
                _busy = False
    _redraw()
    return 0.5 if _busy else None


class MCPINSTALLER_OT_install(bpy.types.Operator):
    bl_idname = 'mcp_installer.install'
    bl_label = '一键安装 MCP for Blender'
    bl_description = '下载 uv 和 MCP 插件，启用并保存偏好设置；可选配置 Codex'

    @classmethod
    def poll(cls, context):
        return os.name == 'nt' and not _busy

    def execute(self, context):
        global _busy, _status
        prefs = context.preferences.addons[__package__].preferences
        # Updating a loaded module safely requires a restart; do not overwrite it.
        if 'blender_mcp' in context.preferences.addons:
            self.report({'INFO'}, 'MCP 插件已启用，无需重复安装。更新请使用上游更新功能。')
            return {'CANCELLED'}
        if not prefs.confirm_saved:
            self.report({'WARNING'}, '请先保存场景，然后勾选“我已保存场景”。')
            return {'CANCELLED'}
        addons_dir = bpy.utils.user_resource('SCRIPTS', path='addons', create=True)
        _log.clear()
        _busy = True
        _status = '正在准备安装……'
        threading.Thread(target=_worker, args=(addons_dir, prefs.configure_codex), daemon=True).start()
        if not bpy.app.timers.is_registered(_poll):
            bpy.app.timers.register(_poll, first_interval=0.2, persistent=True)
        return {'FINISHED'}


def _draw_status(layout):
    layout.label(text=_status, icon='TIME' if _busy else 'INFO')
    for entry in _log[-8:]:
        for line in entry.splitlines():
            # Keep long error messages readable in narrow preferences windows.
            for offset in range(0, len(line), 80):
                layout.label(text=line[offset:offset + 80])


class MCPINSTALLER_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    configure_codex: BoolProperty(name='同时配置 Codex', default=True)
    confirm_saved: BoolProperty(name='我已保存场景', default=False, options={'SKIP_SAVE'})

    def draw(self, context):
        layout = self.layout
        layout.label(text='Windows 安装助手：下载并运行 Astral 官方 uv 安装器和 MCP 包。')
        layout.label(text='需要网络；请保持 Blender 打开，安装中不要禁用本助手。')
        if os.name != 'nt':
            layout.label(text='此安装助手仅支持 Windows。', icon='ERROR')
            return
        row = layout.column()
        row.enabled = not _busy
        row.prop(self, 'configure_codex')
        row.prop(self, 'confirm_saved')
        row.operator('mcp_installer.install', icon='IMPORT')
        _draw_status(layout)


_classes = (MCPINSTALLER_OT_install, MCPINSTALLER_Preferences)


def register():
    global _active
    for cls in _classes:
        bpy.utils.register_class(cls)
    _active = True


def unregister():
    global _active
    _active = False
    if bpy.app.timers.is_registered(_poll):
        bpy.app.timers.unregister(_poll)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
