@echo off
setlocal
cd /d "%~dp0"

echo [1/3] PyInstaller kuruluyor...
python -m pip install -r requirements-build.txt
if errorlevel 1 goto failed

echo [2/3] SSHStarter.exe olusturuluyor...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SSHStarter --icon assets\ssh-starter.ico --add-data "assets\ssh-starter.ico;assets" main.py
if errorlevel 1 goto failed

echo [3/3] MIT lisansi dagitim klasorune kopyalaniyor...
copy /Y LICENSE dist\LICENSE >nul
if errorlevel 1 goto failed

echo.
echo Tamamlandi: dist\SSHStarter.exe
pause
exit /b 0

:failed
echo.
echo Derleme basarisiz oldu. Yukaridaki hata mesajini inceleyin.
pause
exit /b 1
