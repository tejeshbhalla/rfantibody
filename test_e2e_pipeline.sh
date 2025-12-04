#!/bin/bash
# End-to-end test of the full RFantibody pipeline:
# 1. RFdiffusion - Generate antibody structure
# 2. ProteinMPNN - Design sequence for the structure  
# 3. RF2 - Predict/validate structure

set -e

echo "========================================"
echo "RFantibody Full Pipeline E2E Test"
echo "========================================"

cd /root/RFantibody

# Create output directories
mkdir -p /root/RFantibody/scripts/examples/example_outputs
mkdir -p /root/RFantibody/scripts/examples/proteinmpnn/example_outputs
mkdir -p /root/RFantibody/scripts/examples/rf2/example_outputs

echo ""
echo "=== Step 1: RFdiffusion - Antibody Structure Generation ==="
echo "Running RFdiffusion inference..."

poetry run python scripts/rfdiffusion_inference.py \
    --config-name antibody \
    antibody.target_pdb=/root/RFantibody/scripts/examples/example_inputs/rsv_site3.pdb \
    antibody.framework_pdb=/root/RFantibody/scripts/examples/example_inputs/hu-4D5-8_Fv.pdb \
    inference.ckpt_override_path=/root/RFantibody/weights/RFdiffusion_Ab.pt \
    'ppi.hotspot_res=[T305,T456]' \
    'antibody.design_loops=[L1:8-13,L2:7,L3:9-11,H1:7,H2:6,H3:5-13]' \
    inference.num_designs=1 \
    inference.final_step=50 \
    diffuser.T=50 \
    inference.deterministic=True \
    inference.output_prefix=/root/RFantibody/scripts/examples/example_outputs/ab_des

echo "RFdiffusion complete!"

# Check if output was created
if ls /root/RFantibody/scripts/examples/example_outputs/ab_des*.pdb 1> /dev/null 2>&1; then
    echo "  Output PDB files created successfully"
    ls -la /root/RFantibody/scripts/examples/example_outputs/ab_des*.pdb
else
    echo "  ERROR: No output PDB files found"
    exit 1
fi

echo ""
echo "=== Step 2: ProteinMPNN - Sequence Design ==="
echo "Running ProteinMPNN on RFdiffusion outputs..."

# Copy RFdiffusion output to ProteinMPNN input directory
mkdir -p /root/RFantibody/scripts/examples/proteinmpnn/example_inputs
cp /root/RFantibody/scripts/examples/example_outputs/ab_des*.pdb \
   /root/RFantibody/scripts/examples/proteinmpnn/example_inputs/

poetry run python scripts/proteinmpnn_interface_design.py \
    -pdbdir /root/RFantibody/scripts/examples/proteinmpnn/example_inputs \
    -outpdbdir /root/RFantibody/scripts/examples/proteinmpnn/example_outputs \
    -seqs_per_struct 1

echo "ProteinMPNN complete!"

# Check if output was created
if ls /root/RFantibody/scripts/examples/proteinmpnn/example_outputs/*.pdb 1> /dev/null 2>&1; then
    echo "  Output PDB files created successfully"
    ls -la /root/RFantibody/scripts/examples/proteinmpnn/example_outputs/*.pdb
else
    echo "  ERROR: No ProteinMPNN output files found"
    exit 1
fi

echo ""
echo "=== Step 3: RF2 - Structure Prediction/Validation ==="
echo "Running RF2 on ProteinMPNN outputs..."

# Copy ProteinMPNN output to RF2 input directory
mkdir -p /root/RFantibody/scripts/examples/rf2/example_inputs
cp /root/RFantibody/scripts/examples/proteinmpnn/example_outputs/*.pdb \
   /root/RFantibody/scripts/examples/rf2/example_inputs/ 2>/dev/null || true

# Run RF2 from the correct config directory
cd /root/RFantibody/src/rfantibody/rf2
poetry run python /root/RFantibody/scripts/rf2_predict.py \
    input.pdb_dir=/root/RFantibody/scripts/examples/rf2/example_inputs \
    output.pdb_dir=/root/RFantibody/scripts/examples/rf2/example_outputs

echo "RF2 complete!"

cd /root/RFantibody

echo ""
echo "========================================"
echo "Full Pipeline Test Complete!"
echo "========================================"
echo ""
echo "Outputs:"
echo "  RFdiffusion: /root/RFantibody/scripts/examples/example_outputs/"
echo "  ProteinMPNN: /root/RFantibody/scripts/examples/proteinmpnn/example_outputs/"
echo "  RF2:         /root/RFantibody/scripts/examples/rf2/example_outputs/"
