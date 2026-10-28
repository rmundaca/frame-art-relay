@echo off
REM Usage:
REM   build.bat                  (patch: 1.0.0 -> 1.0.1)
REM   build.bat --bump minor     (1.0.0 -> 1.1.0)
REM   build.bat --bump major     (1.0.0 -> 2.0.0)
REM   build.bat --version 1.2.0  (exact version)
REM   build.bat --no-bump        (keep the version)
REM   build.bat -m "Note"        (changelog entry)

python "%~dp0build_package.py" %*
