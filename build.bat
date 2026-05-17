@echo off
echo ============================================
echo   SnapTool - Build Script
echo ============================================
echo.

:: Install dependencies
echo Installing dependencies...
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Building SnapTool executable...
py -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name SnapTool ^
    --hidden-import mss ^
    --hidden-import PIL ^
    --hidden-import snaptool ^
    --hidden-import snaptool.app ^
    --hidden-import snaptool.capture ^
    --hidden-import snaptool.config ^
    --hidden-import snaptool.hotkeys ^
    --hidden-import snaptool.editor ^
    --hidden-import snaptool.save_dialog ^
    --hidden-import snaptool.settings_dialog ^
    --hidden-import snaptool.history ^
    main.py

if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: dist\SnapTool.exe
echo ============================================
pause
