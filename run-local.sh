#!/usr/bin/env bash
set -e

echo "=================================================================="
echo "YottaFlex.ai Warehouse Telemetry & Risk Platform — Local Launcher"
echo "=================================================================="

echo "[1/3] Verifying Deterministic Seed Dataset (Seed: 20261022)..."
python3 generator/generate_dataset.py --seed 20261022 --scale starter --out-dir data/seed
python3 generator/validate_dataset.py --data-dir data/seed --seed 20261022 --scale starter --skip-repro

echo "[2/3] Starting Spring Boot (Java 25) Backend on http://localhost:8080 ..."
(cd backend && mvn spring-boot:run) &
BACKEND_PID=$!

echo "[3/3] Starting ReactJS (Vite) Frontend on http://localhost:5173 ..."
cd frontend
npm ci
npm run dev

kill $BACKEND_PID 2>/dev/null || true
