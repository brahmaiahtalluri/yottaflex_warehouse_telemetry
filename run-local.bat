@echo off
echo ==================================================================
echo YottaFlex.ai Warehouse Telemetry and Risk Platform - Windows Launcher
echo ==================================================================

echo [1/3] Verifying Deterministic Seed Dataset (Seed: 20261022)...
py -3 generator\generate_dataset.py --seed 20261022 --scale starter --out-dir data\seed
if errorlevel 1 exit /b 1
py -3 generator\validate_dataset.py --data-dir data\seed --seed 20261022 --scale starter --skip-repro
if errorlevel 1 exit /b 1

echo [2/3] Starting Spring Boot (Java 25) Backend in new window on http://localhost:8080 ...
start "YottaFlex Spring Boot Backend" cmd /k "cd backend && mvn spring-boot:run"

echo [3/3] Starting ReactJS (Vite) Frontend on http://localhost:5173 ...
cd frontend
call npm ci
if errorlevel 1 exit /b 1
call npm run dev
