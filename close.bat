@echo off
echo.
echo ========================================================
echo   DISCONNECTING IN 5 SECONDS...
echo   CLICK ON ROBLOX NOW TO GIVE IT FOCUS!
echo ========================================================
echo.
timeout /t 5

@powershell -NoProfile -ExecutionPolicy Bypass -Command "start-process 'C:\Windows\System32\tscon.exe' -ArgumentList '%sessionname% /dest:console' -Verb RunAs"
