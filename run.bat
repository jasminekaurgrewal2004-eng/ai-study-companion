@echo off
cd /d "%~dp0"
echo Starting Lumen Study Companion...
echo Open http://127.0.0.1:8000 in your browser
echo Press Ctrl+C to stop the server
echo.
python manage.py runserver
pause
