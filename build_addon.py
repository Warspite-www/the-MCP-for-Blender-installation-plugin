"""Build a shareable Blender addon ZIP using only the Python standard library."""
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parent
    source = root / 'addon' / 'blender_mcp_installer' / '__init__.py'
    compile(source.read_text(encoding='utf-8'), str(source), 'exec')
    target = root / 'dist' / 'blender-mcp-installer-1.0.0.zip'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, 'blender_mcp_installer/__init__.py')
        archive.write(root / 'LICENSE', 'blender_mcp_installer/LICENSE')
    print(target.name)


if __name__ == '__main__':
    main()
