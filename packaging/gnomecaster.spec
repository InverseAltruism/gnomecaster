# PyInstaller recipe for the Windows app: python -m PyInstaller packaging/gnomecaster.spec
# One folder, not one file: a one-file build unpacks itself to a temp folder at each start,
# which is slower and often reported to trigger antivirus false positives. The version comes
# from companion/gnomecaster/__init__.py.
import pathlib
import re
import sys

ROOT = pathlib.Path(SPECPATH).parent
VERSION = re.search(r'__version__ = "([\d.]+)"', (ROOT / "companion" / "gnomecaster" / "__init__.py").read_text()).group(1)


def version_resource():
    """The Details tab of the .exe's properties. Windows only: elsewhere the recipe still
    builds, which checks it on Linux."""
    if sys.platform != "win32":
        return None
    from PyInstaller.utils.win32 import versioninfo as vi
    numbers = tuple(int(n) for n in (VERSION.split(".") + ["0"] * 4)[:4])
    strings = {"CompanyName": "InverseAltruism", "FileDescription": "Gnomecaster", "FileVersion": VERSION,
               "InternalName": "Gnomecaster", "LegalCopyright": "InverseAltruism",
               "OriginalFilename": "Gnomecaster.exe", "ProductName": "Gnomecaster", "ProductVersion": VERSION}
    return vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[vi.StringFileInfo([vi.StringTable("040904B0", [vi.StringStruct(k, v) for k, v in strings.items()])]),
              vi.VarFileInfo([vi.VarStruct("Translation", [0x0409, 1200])])])


a = Analysis(
    [str(ROOT / "companion" / "gnomecaster_app.py")],
    pathex=[str(ROOT / "companion")],
    datas=[
        (str(ROOT / "addon"), "addon"),
        (str(ROOT / "desktop" / "ui"), "desktop/ui"),
        (str(ROOT / "assets" / "brand" / "png" / "icon-64.png"), "assets/brand/png"),
    ],
    hiddenimports=["pystray._win32"],       # pystray picks its backend at run time
    # pystray is LGPL-3.0: shipped as plain source so a player can replace or change it
    module_collection_mode={"pystray": "py"},
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gnomecaster",
    icon=str(ROOT / "assets" / "brand" / "gnomecaster.ico"),
    version=version_resource(),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Gnomecaster", upx=False)
