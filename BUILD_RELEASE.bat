@echo off
title Tortuga Music & TV - Release Builder
echo ========================================================
echo   TORTUGA MUSIC & TV - AUTOMATED RELEASE BUILDER
echo   Genera contemporaneamente APK e AAB con versione sincronizzata
echo ========================================================
echo.

set /p NEW_VER="Inserisci la nuova versione (es. 3.7) oppure premi INVIO per mantenere la corrente: "

if "%NEW_VER%"=="" (
    python build_release.py
) else (
    python build_release.py %NEW_VER%
)

echo.
echo ========================================================
echo   OPERAZIONE COMPLETATA!
echo ========================================================
pause
