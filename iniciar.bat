@echo off
chcp 65001 >nul
title MF Tech - OSINT
color 0A
setlocal enabledelayedexpansion

echo ============================================================
echo            MF Tech - OSINT
echo    Sistema de Investigacion de Fuentes Abiertas
echo ============================================================
echo.

rem ------------------------------------------------------------
rem  Paso 0: descomprimir binarios empaquetados (si falta el .exe)
rem ------------------------------------------------------------
if exist "tools\cloudflared.zip" if not exist "tools\cloudflared.exe" (
    echo [..] Descomprimiendo cloudflared (necesario para Localizacion GPS)...
    powershell -NoProfile -Command "Expand-Archive -LiteralPath 'tools\cloudflared.zip' -DestinationPath 'tools' -Force" >nul 2>&1
)
if exist "tools\phoneinfoga.zip" if not exist "tools\phoneinfoga.exe" (
    echo [..] Descomprimiendo phoneinfoga (complementa la herramienta Telefono)...
    powershell -NoProfile -Command "Expand-Archive -LiteralPath 'tools\phoneinfoga.zip' -DestinationPath 'tools' -Force" >nul 2>&1
)

rem ------------------------------------------------------------
rem  Paso 1: encontrar un Python utilizable
rem  1a) el .venv de la carpeta ya funciona en esta PC
rem  1b) python del sistema (python / py -3)
rem  1c) instalador de Python incluido en "instalador\"
rem ------------------------------------------------------------
set "PY_BASE="

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if !errorlevel!==0 (
        echo [OK] Entorno virtual valido en esta carpeta.
        goto :check_deps
    )
    echo [..] El .venv de esta carpeta no funciona en esta PC; sera recreado.
)

python --version >nul 2>&1
if !errorlevel!==0 (set "PY_BASE=python")
if not defined PY_BASE (
    py -3 --version >nul 2>&1
    if !errorlevel!==0 (set "PY_BASE=py -3")
)

rem  Escoge el instalador segun la arquitectura: x86 para PC viejas de 32 bits
set "PY_OS_ARCH=64 bits"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" set "PY_OS_ARCH=32 bits"

if not defined PY_BASE (
    set "PY_INST_OK="
    if /i "%PROCESSOR_ARCHITECTURE%"=="x86" (
        if exist "instalador\python-3.12.4-x86.exe" (
            echo [..] Instalando Python 3.12.4 (32 bits) incluido en la carpeta...
            start /wait "" "instalador\python-3.12.4-x86.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 Include_launcher=1
            set "PY_INST_OK=1"
        )
    ) else (
        if exist "instalador\python-3.12.4-amd64.exe" (
            echo [..] Instalando Python 3.12.4 (64 bits) incluido en la carpeta...
            start /wait "" "instalador\python-3.12.4-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 Include_launcher=1
            set "PY_INST_OK=1"
        )
    )

    rem  El instalador por-usuario deja el python en alguna de estas rutas
    if defined PY_INST_OK (
        set "PY_BASE="
        for %%P in (
            "%LocalAppData%\Programs\Python\Python312\python.exe"
            "%LocalAppData%\Programs\Python\Python312-32\python.exe"
        ) do (
            if not defined PY_BASE if exist "%%~P" set "PY_BASE=%%~P"
        )
        if not defined PY_BASE (
            echo [ERROR] Python no quedo instalado correctamente.
            echo Puede instalarlo manualmente desde  instalador\python-3.12.4-amd64.exe
            echo                                      o  instalador\python-3.12.4-x86.exe
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR] No se encontro Python 3 en el sistema y falta el
        echo         instalador en la carpeta "instalador\".
        pause
        exit /b 1
    )
)

echo [OK] Python base encontrado (!PY_OS_ARCH!): !PY_BASE!
!PY_BASE! --version

rem ------------------------------------------------------------
rem  Paso 2: crear (o recrear) el entorno virtual
rem ------------------------------------------------------------
if exist ".venv" (
    echo [..] Quitando .venv anterior (incompatible con esta PC)...
    rmdir /s /q ".venv"
)
echo [..] Creando entorno virtual...
!PY_BASE! -m venv .venv
if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    pause
    exit /b 1
)
echo [OK] Entorno virtual creado.

rem ------------------------------------------------------------
rem  Paso 3: dependencias (requiere internet la primera vez)
rem ------------------------------------------------------------
:check_deps
echo.
echo [..] Verificando dependencias...
".venv\Scripts\python.exe" -c "import flask, requests" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Dependencias presentes.
    goto :run
)

echo [..] Instalando dependencias desde internet (primera vez, puede tardar)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias.
    echo Revise su conexion a internet e intente otra vez.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

rem ------------------------------------------------------------
rem  Paso 4: arrancar
rem ------------------------------------------------------------
:run
echo.
echo ============================================================
echo  Abra su navegador en:
echo   http://localhost:8090
echo   http://127.0.0.1:8090
echo.
echo  Para acceder desde OTRA PC de la misma red, use la IP que
echo  se muestra en consola al iniciar (se imprime abajo).
echo.
echo  Ctrl+C para detener.
echo ============================================================
echo.

".venv\Scripts\python.exe" app.py

pause