#!/usr/bin/env bash
# One container, one public port. nginx fronts the Streamlit UI and the demo API.
set -euo pipefail
cd "$(dirname "$0")/../.."

export DEMO_API_URL="http://127.0.0.1:8000"
export DEMO_STATE_PATH="${DEMO_STATE_PATH:-/tmp/soc-demo-budget.json}"

uvicorn --factory soc_demo.api:app_factory --host 127.0.0.1 --port 8000 --no-access-log &
streamlit run "$(python -c 'import soc_demo.ui as m; print(m.__file__)')" \
  --server.port 8501 --server.address 127.0.0.1 --server.headless true \
  --server.enableCORS false --server.enableXsrfProtection false \
  --server.fileWatcherType none --browser.gatherUsageStats false &
nginx -c "$PWD/deploy/hf-space/nginx.conf" -g 'daemon off;' &

# if any of the three exits, exit so the Space restarts instead of serving half an app
wait -n
exit 1
