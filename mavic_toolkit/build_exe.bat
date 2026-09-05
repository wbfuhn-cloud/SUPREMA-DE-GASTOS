@echo off
echo Installing dependencies...
pip install pyinstaller

echo.
echo Building executable...
pyinstaller --noconsole --onefile --name "Mavic_Pro_Toolkit" toolkit.py

echo.
echo Done! You can find the executable in the 'dist' folder.
pause
