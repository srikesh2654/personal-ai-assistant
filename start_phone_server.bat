@echo off
REM Starts SERENE's phone server. Leave this window open while using her on your phone.
REM Then open  http://<this-pc-ip>:8765  on your phone (same Wi-Fi).
cd /d "%~dp0"
echo Starting SERENE phone server on port 8765 ...
echo Open http://192.168.1.42:8765 on your phone (same Wi-Fi). Ctrl+C to stop.
.venv\Scripts\python.exe -m serene.server
pause
