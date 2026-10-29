@echo off
setlocal

:: Move to the folder where this .bat lives, so the shell starts in the right place
cd /d "%~dp0"

set "SCRIPT=eclipse_shell.py"

:: Make sure the script actually exists before we try to run it
if not exist "%SCRIPT%" (
    echo [ERROR] Could not find "%SCRIPT%" in:
    echo         %cd%
    echo.
    echo Put this .bat file in the same folder as eclipse_shell.py.
    pause
    exit /b 1
)

:: Try launchers in order of preference
where py >nul 2>&1
if %errorlevel%==0 (
    py "%SCRIPT%" %*
    goto :done
)

where python >nul 2>&1
if %errorlevel%==0 (
    python "%SCRIPT%" %*
    goto :done
)

where python3 >nul 2>&1
if %errorlevel%==0 (
    python3 "%SCRIPT%" %*
    goto :done
)

:: Nothing worked
echo [ERROR] Could not find Python on this system.
echo.
echo Tried: py, python, python3
echo Make sure Python is installed and on your PATH.
echo   Download: https://www.python.org/downloads/
echo   During install, check "Add Python to PATH".
echo.
pause
exit /b 1

:done
:: If Python exited with an error, keep the window open so the user can read it
if %errorlevel% neq 0 (
    echo.
    echo [Eclipse Shell exited with code %errorlevel%]
    pause
)

endlocal