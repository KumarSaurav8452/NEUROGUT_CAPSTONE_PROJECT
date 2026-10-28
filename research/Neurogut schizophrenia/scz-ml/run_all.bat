@echo off
rem NEUROGUT SCZ classifier: runs every stage unattended, see ..\PRD_SCZ_ML_Training.md
rem   run_all.bat         full run   -> results\SUMMARY.md   (about 1-2 h)
rem   run_all.bat quick   smoke test -> results_quick\SUMMARY.md (a few minutes)
rem Finished stages are cached in results\parts\, so rerunning resumes after a crash.
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONPATH=%~dp0src
set PYTHONUTF8=1
set PYTHONWARNINGS=ignore
set LOG=logs\run_all.log
if /i "%1"=="quick" set LOG=logs\run_quick.log

python -c "import catboost, boruta, networkx, statsmodels, xgboost, sklearn" 2>nul || python -m pip install --user -q -r requirements.txt

echo === tests === > %LOG%
python -m pytest -q tests >> %LOG% 2>&1 || goto :fail

echo === run %1 === >> %LOG%
if /i "%1"=="quick" (
    python -m sczml.run --quick >> %LOG% 2>&1 || goto :fail
) else (
    python -m sczml.run >> %LOG% 2>&1 || goto :fail
)
echo exit=0 >> %LOG%
echo Done. See results\SUMMARY.md (log: %LOG%)
exit /b 0

:fail
echo exit=1 >> %LOG%
echo FAILED. See %LOG%
exit /b 1
