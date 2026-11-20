@echo off
setlocal
cd /d "%~dp0"
set "EDERSA_PYTHON=%~dp0..\.venv-streamlit\Scripts\python.exe"
if exist "%EDERSA_PYTHON%" goto run
set "EDERSA_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%EDERSA_PYTHON%" goto run
py -m venv .venv
if errorlevel 1 goto fail
"%EDERSA_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto fail
:run
"%EDERSA_PYTHON%" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false
goto end
:fail
echo No se pudo preparar Python. Revisar su instalacion y la conexion a Internet.
pause
:end
endlocal
