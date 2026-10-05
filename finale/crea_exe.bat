@echo off
rem Crea l'eseguibile del gioco: dist\IlSegretoDelCarbonaro.exe
rem Serve Python 3.10 o piu' recente. Si lancia con un doppio clic (o da cmd, dentro la cartella finale).
cd /d "%~dp0"

echo.
echo === 1/3  Installo le dipendenze del gioco e PyInstaller ===
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto errore

echo.
echo === 2/3  Creo l'eseguibile (ci vogliono alcuni minuti) ===
python -m PyInstaller --noconfirm --clean --onefile --windowed --name IlSegretoDelCarbonaro --collect-all ursina --collect-all panda3d --collect-all direct il_segreto_del_carbonaro_finale.py
if errorlevel 1 goto errore

echo.
echo === 3/3  Fatto ===
echo Il gioco e' in: %~dp0dist\IlSegretoDelCarbonaro.exe
echo.
pause
exit /b 0

:errore
echo.
echo Qualcosa e' andato storto: leggi i messaggi qui sopra.
pause
exit /b 1
