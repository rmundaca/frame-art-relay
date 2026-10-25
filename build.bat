@echo off
REM Uso:
REM   build.bat                  (patch: 1.0.0 -> 1.0.1)
REM   build.bat --bump minor     (1.0.0 -> 1.1.0)
REM   build.bat --bump major     (1.0.0 -> 2.0.0)
REM   build.bat --version 1.2.0  (versión exacta)
REM   build.bat --no-bump        (mantiene la versión)
REM   build.bat -m "Nota"        (entrada en changelog)

python "%~dp0build_package.py" %*
