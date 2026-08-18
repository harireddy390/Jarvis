@echo off
start "" "C:\Users\HARI REDDY\AppData\Local\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
timeout /t 3 /nobreak >nul
cd /d "C:\Users\HARI REDDY\JARVIS"
start "" "C:\Users\HARI REDDY\JARVIS\venv\Scripts\pythonw.exe" main.py
exit