import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    [str(root / "src" / "lgtv_remote" / "__main__.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "src" / "lgtv_remote" / "ui" / "styles" / "*.qss"), "lgtv_remote/ui/styles"),
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "qasync",
        "aiowebostv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "numpy",
        "PIL",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6.Qt3D",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCanvasPainter",
        "PySide6.QtCharts",
        "PySide6.QtConcurrent",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtGraphs",
        "PySide6.QtHelp",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNfc",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtSerialBus",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtXml",
        "pydantic",
        "pydantic_core",
        "lxml",
        "cryptography",
        "Cython",
        "ast_serialize",
    ],
    noarchive=False,
    cipher=block_cipher,
)

# Strip transitive shared libraries that are not needed at runtime.
# These get pulled in by Qt plugins or system deps but the app never uses them.
_EXCLUDE_LIBS = {
    # Video codecs (pulled by gdk-pixbuf / multimedia plugins)
    "libx265", "libx264", "libaom", "libSvtAv1Enc", "libdav1d", "librav1e",
    "libde265", "libheif", "libjxl",
    # KDE theme libraries (pulled by Breeze platform theme)
    "libKF6BreezeIcons", "libKF6Style", "libKF6KIOCore", "libKF6KIOWidgets",
    "libKF6WidgetsAddons", "libKF6ConfigCore", "libKF6ConfigWidgets",
    "libKF6ColorScheme", "libKF6IconThemes", "libKF6I18n",
    "liboxygenstyle",
    # Qt modules not needed (already excluded as Python modules, but their
    # .so libs can still be dragged in as transitive deps)
    "libQt6Quick", "libQt6Qml", "libQt6QmlCompiler", "libQt6QmlModels",
    "libQt6Pdf", "libQt6ShaderTools", "libQt6Multimedia",
    "libQt6Quick3D", "libQt6QuickTemplates2", "libQt6QuickControls2",
    "libQt6QuickDialogs2", "libQt6WebEngine", "libQt6WebChannel",
    "libQt6Sql", "libQt6Svg",
    # Image format libs rarely needed
    "libraw", "libOpenEXR", "libIex", "libIlmThread", "libImath",
    # Other large libs not used
    "libglycin", "libCython",
    "Cython",
}

def _should_exclude(name):
    for prefix in _EXCLUDE_LIBS:
        if name.startswith(prefix):
            return True
    return False

a.binaries = [(name, path, typ) for name, path, typ in a.binaries
              if not _should_exclude(name)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="lgtv-remote",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    icon=str(root / "icons" / "lgtv-remote.svg"),
)
