@echo off
cd /d "%~dp0integrations\netease"
where node >nul 2>nul
if errorlevel 1 (
 echo Please install Node.js 22 or later.
 pause
 exit /b 1
)
if not exist node_modules\@neteasecloudmusicapienhanced\api (
 call npm.cmd ci --ignore-scripts --no-audit --no-fund
 if errorlevel 1 (
  pause
  exit /b 1
 )
)
node server.cjs
pause
