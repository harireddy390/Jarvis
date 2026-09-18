@echo off
title BUDDY AI Assistant - Starting...
echo.
echo  ██████╗ ██╗   ██╗██████╗ ██████╗ ██╗   ██╗
echo  ██╔══██╗██║   ██║██╔══██╗██╔══██╗╚██╗ ██╔╝
echo  ██████╔╝██║   ██║██║  ██║██║  ██║ ╚████╔╝
echo  ██╔══██╗██║   ██║██║  ██║██║  ██║  ╚██╔╝
echo  ██████╔╝╚██████╔╝██████╔╝██████╔╝   ██║
echo  ╚═════╝  ╚═════╝ ╚═════╝ ╚═════╝    ╚═╝
echo.
echo  [1/3] Starting Chrome with remote debugging...
start "" "C:\Users\HARI REDDY\AppData\Local\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
timeout /t 3 /nobreak >nul

echo  [2/3] Launching BUDDY AI Assistant...
cd /d "C:\Users\HARI REDDY\JARVIS"

echo  [3/3] Ready! Say "Hey Buddy" or press F8 to activate.
echo.
start "" "C:\Users\HARI REDDY\JARVIS\venv\Scripts\pythonw.exe" main.py
exit