#!/bin/bash
# Test script for full RFantibody pipeline:
# 1. RFdiffusion - Antibody structure diffusion
# 2. ProteinMPNN - Sequence design
# 3. RF2 - Structure prediction/validation

set -e

echo "========================================"
echo "Testing RFantibody Pipeline Components"
echo "========================================"

cd /root/RFantibody

# Test 1: Check if all imports work
echo ""
echo "=== Test 1: Checking Python imports ==="
poetry run python -c "
import sys
print('Python version:', sys.version)

print('Importing RFdiffusion modules...')
from rfantibody.rfdiffusion.inference import model_runners
from rfantibody.rfdiffusion.diffusion import Diffuser
print('  RFdiffusion: OK')

print('Importing ProteinMPNN modules...')
from rfantibody.proteinmpnn.struct_manager import StructManager
from rfantibody.proteinmpnn.sample_features import SampleFeatures
import rfantibody.proteinmpnn.util_protein_mpnn as mpnn_util
print('  ProteinMPNN: OK')

print('Importing RF2 modules...')
from rfantibody.rf2.modules.model_runner import AbPredictor
from rfantibody.rf2.modules.preprocess import Preprocess
print('  RF2: OK')

print('')
print('All imports successful!')
"

echo ""
echo "=== Test 2: Checking weights/models exist ==="
if [ -f "/root/RFantibody/weights/RFdiffusion_Ab.pt" ]; then
    echo "  RFdiffusion weights: OK"
else
    echo "  RFdiffusion weights: MISSING"
fi

if [ -f "/root/RFantibody/weights/ProteinMPNN_v48_noise_0.2.pt" ]; then
    echo "  ProteinMPNN weights: OK"
else
    echo "  ProteinMPNN weights: MISSING"
fi

if [ -f "/root/RFantibody/weights/RF2_ab.pt" ]; then
    echo "  RF2 weights: OK"
else
    echo "  RF2 weights: MISSING (run: wget -O weights/RF2_ab.pt https://files.ipd.uw.edu/pub/RFantibody/RF2_ab.pt)"
fi

echo ""
echo "=== Test 3: Check example inputs ==="
if [ -f "/root/RFantibody/scripts/examples/example_inputs/rsv_site3.pdb" ]; then
    echo "  RFdiffusion example target: OK"
else
    echo "  RFdiffusion example target: MISSING"
fi

if [ -f "/root/RFantibody/scripts/examples/example_inputs/hu-4D5-8_Fv.pdb" ]; then
    echo "  RFdiffusion example framework: OK"
else
    echo "  RFdiffusion example framework: MISSING"
fi

echo ""
echo "========================================"
echo "Pipeline Component Checks Complete"
echo "========================================"
