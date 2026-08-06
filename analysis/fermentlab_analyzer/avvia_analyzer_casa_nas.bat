@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
set "SECRETS_FILE=%REPO_ROOT%\experiments\esp32\fermentation-session-logger\include\secrets.h"

if not exist "%SECRETS_FILE%" (
    echo File secrets non trovato: "%SECRETS_FILE%"
    exit /b 1
)

for /f "tokens=3" %%A in ('findstr /B /C:"#define WIFI_SSID " "%SECRETS_FILE%"') do set "EXPECTED_SSID=%%A"
for /f "tokens=3" %%A in ('findstr /B /C:"#define INFLUX_NAS_URL " "%SECRETS_FILE%"') do set "FERMENTLAB_INFLUX_URL=%%A"
for /f "tokens=3" %%A in ('findstr /B /C:"#define INFLUX_NAS_TOKEN " "%SECRETS_FILE%"') do set "FERMENTLAB_INFLUX_TOKEN=%%A"
for /f "tokens=3" %%A in ('findstr /B /C:"#define INFLUX_NAS_ORG " "%SECRETS_FILE%"') do set "FERMENTLAB_INFLUX_ORG=%%A"
for /f "tokens=3" %%A in ('findstr /B /C:"#define INFLUX_NAS_BUCKET " "%SECRETS_FILE%"') do set "FERMENTLAB_INFLUX_BUCKET=%%A"

set "EXPECTED_SSID=%EXPECTED_SSID:\"=%"
set "EXPECTED_SSID=%EXPECTED_SSID:"=%"
set "FERMENTLAB_INFLUX_URL=%FERMENTLAB_INFLUX_URL:\"=%"
set "FERMENTLAB_INFLUX_URL=%FERMENTLAB_INFLUX_URL:"=%"
set "FERMENTLAB_INFLUX_TOKEN=%FERMENTLAB_INFLUX_TOKEN:\"=%"
set "FERMENTLAB_INFLUX_TOKEN=%FERMENTLAB_INFLUX_TOKEN:"=%"
set "FERMENTLAB_INFLUX_ORG=%FERMENTLAB_INFLUX_ORG:\"=%"
set "FERMENTLAB_INFLUX_ORG=%FERMENTLAB_INFLUX_ORG:"=%"
set "FERMENTLAB_INFLUX_BUCKET=%FERMENTLAB_INFLUX_BUCKET:\"=%"
set "FERMENTLAB_INFLUX_BUCKET=%FERMENTLAB_INFLUX_BUCKET:"=%"

if "%EXPECTED_SSID%"=="" (
    echo Impossibile leggere WIFI_SSID da secrets.h
    exit /b 1
)
if "%FERMENTLAB_INFLUX_URL%"=="" (
    echo Impossibile leggere INFLUX_NAS_URL da secrets.h
    exit /b 1
)
if "%FERMENTLAB_INFLUX_TOKEN%"=="" (
    echo Impossibile leggere INFLUX_NAS_TOKEN da secrets.h
    exit /b 1
)
if "%FERMENTLAB_INFLUX_ORG%"=="" (
    echo Impossibile leggere INFLUX_NAS_ORG da secrets.h
    exit /b 1
)
if "%FERMENTLAB_INFLUX_BUCKET%"=="" (
    echo Impossibile leggere INFLUX_NAS_BUCKET da secrets.h
    exit /b 1
)

for /f "tokens=2 delims=:" %%A in ('netsh wlan show interfaces ^| findstr /R /C:"^[ ]*SSID[ ]*:"') do (
    if not defined CURRENT_SSID set "CURRENT_SSID=%%A"
)
for /f "tokens=* delims= " %%A in ("%CURRENT_SSID%") do set "CURRENT_SSID=%%A"

echo.
echo FermentLab Analyzer - Profilo CASA/NAS
echo Wi-Fi corrente: %CURRENT_SSID%
if /I not "%CURRENT_SSID%"=="%EXPECTED_SSID%" (
    echo ATTENZIONE: rete prevista "%EXPECTED_SSID%", trovata "%CURRENT_SSID%".
    echo Il NAS potrebbe non essere raggiungibile da questa rete.
)
set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python non trovato in "%PYTHON_EXE%".
    echo Crea prima l'ambiente virtuale .venv nella root del repository.
    exit /b 1
)

echo.
echo Installo/verifico dipendenze...
"%PYTHON_EXE%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
if errorlevel 1 exit /b 1

echo.
echo Avvio Streamlit Analyzer...
"%PYTHON_EXE%" -m streamlit run "%SCRIPT_DIR%app.py"

endlocal
