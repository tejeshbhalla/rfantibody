#!/bin/bash
# Start the RFantibody API server

cd /root/rfantibody

echo "Starting RFantibody API server..."
echo "API will be available at http://0.0.0.0:8000"
echo "API docs at http://0.0.0.0:8000/docs"
echo ""

PYTHONPATH=src:include/SE3Transformer uvicorn rfantibody.api.main:app --host 0.0.0.0 --port 8000 --reload
