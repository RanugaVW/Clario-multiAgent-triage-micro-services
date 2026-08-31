#!/bin/bash
echo "Starting Clario services in separate terminal tabs..."

# Open GNOME terminal with 5 tabs, each running a specific service and staying open afterward
gnome-terminal \
  --tab --title="Frontend" -- bash -c "cd frontend && npm run dev; exec bash" \
  --tab --title="Spring Boot" -- bash -c "cd clario-app && ./mvnw spring-boot:run; exec bash" \
  --tab --title="ML Worker" -- bash -c "cd clario-ml-sidecar && source .venv/bin/activate && python -m app.worker; exec bash" \
  --tab --title="ML API" -- bash -c "cd clario-ml-sidecar && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload; exec bash" \
  --tab --title="Voice To Text" -- bash -c "cd services/voice-to-text-service && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload; exec bash"

echo "All services launched in new terminal tabs!"
