@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv-test\Scripts\python.exe" (
  echo Environnement du testeur absent. Suivez README.md, section Tester au microphone.
  pause
  popd
  exit /b 1
)
".venv-test\Scripts\python.exe" "tester.py" --prepare
if errorlevel 1 (
  pause
  popd
  exit /b 1
)
".venv-test\Scripts\python.exe" "tester.py" %*
set "TEST_EXIT_CODE=%ERRORLEVEL%"
if not "%TEST_EXIT_CODE%"=="0" pause
popd
exit /b %TEST_EXIT_CODE%
