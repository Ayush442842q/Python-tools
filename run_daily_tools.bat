@echo off
setlocal enabledelayedexpansion

:: Set paths
set "IDE_PATH=C:\Users\ayush\AppData\Local\Programs\Antigravity\Antigravity.exe"
set "AGENT_API_PATH=C:\Users\ayush\.gemini\antigravity\bin\agentapi.bat"
set "LOG_PATH=%~dp0run_daily_tools_log.txt"

echo [%date% %time%] Starting scheduled daily commit task... >> "%LOG_PATH%"

:: Check if Antigravity.exe is running
tasklist /FI "IMAGENAME eq Antigravity.exe" 2>NUL | find /I /N "Antigravity.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [%date% %time%] Antigravity IDE is already running. >> "%LOG_PATH%"
) else (
    echo [%date% %time%] Antigravity IDE is not running. Launching... >> "%LOG_PATH%"
    start "" "%IDE_PATH%"
    
    :: Wait 20 seconds for the IDE and its local language server to fully start
    timeout /t 20 /nobreak >nul
)

:: Trigger the daily task using the CLI agentapi tool
echo [%date% %time%] Triggering new conversation for Python tool generation... >> "%LOG_PATH%"
call "%AGENT_API_PATH%" new-conversation "Generate 5 new unique Python tools, save them to the tools directory, update the README.md to include them, and then run git add, git commit, and git push." >> "%LOG_PATH%" 2>&1

echo [%date% %time%] Task triggered successfully. >> "%LOG_PATH%"
echo ------------------------------------------------------------ >> "%LOG_PATH%"
