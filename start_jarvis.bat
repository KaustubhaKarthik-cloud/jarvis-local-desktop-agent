@echo off
title JARVIS
cd /d %~dp0
echo Starting JARVIS...
echo.
python jarvis_text_mode.py
if errorlevel 1 (
  echo.
  echo JARVIS exited with an error.
  pause
)
