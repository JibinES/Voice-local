#!/bin/bash
set -euo pipefail

# =============================================================================
# Start NVIDIA MPS (Multi-Process Service) for GPU sharing
# =============================================================================

echo "Starting NVIDIA MPS daemon..."

# Check if MPS is already running
if nvidia-smi | grep -q "MPS server"; then
    echo "MPS is already running."
    exit 0
fi

# Set MPS pipe and log directories
export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps
export CUDA_MPS_LOG_DIRECTORY=/tmp/nvidia-mps-log

mkdir -p "$CUDA_MPS_PIPE_DIRECTORY"
mkdir -p "$CUDA_MPS_LOG_DIRECTORY"

# Set compute mode to exclusive process (recommended for MPS)
# This may require root
sudo nvidia-smi -i 0 -c EXCLUSIVE_PROCESS 2>/dev/null || true

# Start MPS control daemon
nvidia-cuda-mps-control -d

echo "NVIDIA MPS daemon started."
echo "  Pipe directory: $CUDA_MPS_PIPE_DIRECTORY"
echo "  Log directory:  $CUDA_MPS_LOG_DIRECTORY"
echo ""
echo "To stop MPS: echo quit | nvidia-cuda-mps-control"
