"""
Pipeline execution for RFantibody API
Runs RFdiffusion -> ProteinMPNN -> RF2 in sequence
"""
import os
import glob
import shutil
import subprocess
import tempfile
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

# Default paths
RFANTIBODY_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
WEIGHTS_DIR = os.path.join(RFANTIBODY_ROOT, "weights")
EXAMPLES_DIR = os.path.join(RFANTIBODY_ROOT, "scripts", "examples", "example_inputs")
JOBS_OUTPUT_DIR = os.path.join(RFANTIBODY_ROOT, "jobs_output")

# Default files
DEFAULT_FRAMEWORK_PDB = os.path.join(EXAMPLES_DIR, "hu-4D5-8_Fv.pdb")
DEFAULT_DESIGN_LOOPS = ["L1:8-13", "L2:7", "L3:9-11", "H1:7", "H2:6", "H3:5-13"]


def ensure_output_dir(job_id: str) -> str:
    """Create output directory for a job"""
    output_dir = os.path.join(JOBS_OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "rfdiffusion"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "proteinmpnn"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "rf2"), exist_ok=True)
    return output_dir


def save_pdb_content(content: str, filepath: str) -> str:
    """Save PDB content to file, return path"""
    # If content is a file path that exists, just return it
    if os.path.exists(content):
        return content
    
    # Otherwise treat as PDB content and save
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath


def run_rfdiffusion(
    job_id: str,
    target_pdb: str,
    framework_pdb: str,
    hotspot_residues: list,
    design_loops: list,
    num_designs: int,
    diffusion_steps: int,
    output_dir: str,
    progress_callback: Optional[Callable] = None
) -> list:
    """Run RFdiffusion to generate antibody structures"""
    
    if progress_callback:
        progress_callback("Running RFdiffusion...")
    
    output_prefix = os.path.join(output_dir, "rfdiffusion", "ab_des")
    
    # Format hotspot residues for config
    hotspots_str = "[" + ",".join(hotspot_residues) + "]"
    loops_str = "[" + ",".join(design_loops) + "]"
    
    cmd = [
        "poetry", "run", "python",
        os.path.join(RFANTIBODY_ROOT, "scripts", "rfdiffusion_inference.py"),
        "--config-name", "antibody",
        f"antibody.target_pdb={target_pdb}",
        f"antibody.framework_pdb={framework_pdb}",
        f"inference.ckpt_override_path={os.path.join(WEIGHTS_DIR, 'RFdiffusion_Ab.pt')}",
        f"ppi.hotspot_res={hotspots_str}",
        f"antibody.design_loops={loops_str}",
        f"inference.num_designs={num_designs}",
        f"inference.final_step={diffusion_steps}",
        f"diffuser.T={diffusion_steps}",
        "inference.deterministic=True",
        f"inference.output_prefix={output_prefix}"
    ]
    
    logger.info(f"Running RFdiffusion: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        cwd=RFANTIBODY_ROOT,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error(f"RFdiffusion failed: {result.stderr}")
        raise RuntimeError(f"RFdiffusion failed: {result.stderr[-500:]}")
    
    # Find output files
    output_files = glob.glob(f"{output_prefix}*.pdb")
    logger.info(f"RFdiffusion generated {len(output_files)} structures")
    
    return output_files


def run_proteinmpnn(
    job_id: str,
    input_pdbs: list,
    output_dir: str,
    progress_callback: Optional[Callable] = None
) -> list:
    """Run ProteinMPNN to design sequences"""
    
    if progress_callback:
        progress_callback("Running ProteinMPNN...")
    
    # Create input directory for ProteinMPNN
    mpnn_input_dir = os.path.join(output_dir, "proteinmpnn_input")
    mpnn_output_dir = os.path.join(output_dir, "proteinmpnn")
    os.makedirs(mpnn_input_dir, exist_ok=True)
    
    # Copy input PDBs
    for pdb in input_pdbs:
        shutil.copy(pdb, mpnn_input_dir)
    
    cmd = [
        "poetry", "run", "python",
        os.path.join(RFANTIBODY_ROOT, "scripts", "proteinmpnn_interface_design.py"),
        "-pdbdir", mpnn_input_dir,
        "-outpdbdir", mpnn_output_dir,
        "-seqs_per_struct", "1"
    ]
    
    logger.info(f"Running ProteinMPNN: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        cwd=RFANTIBODY_ROOT,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error(f"ProteinMPNN failed: {result.stderr}")
        raise RuntimeError(f"ProteinMPNN failed: {result.stderr[-500:]}")
    
    # Find output files
    output_files = glob.glob(os.path.join(mpnn_output_dir, "*.pdb"))
    logger.info(f"ProteinMPNN generated {len(output_files)} sequences")
    
    return output_files


def run_rf2(
    job_id: str,
    input_pdbs: list,
    output_dir: str,
    progress_callback: Optional[Callable] = None
) -> list:
    """Run RF2 for structure prediction/validation"""
    
    if progress_callback:
        progress_callback("Running RF2...")
    
    # Create input directory for RF2
    rf2_input_dir = os.path.join(output_dir, "rf2_input")
    rf2_output_dir = os.path.join(output_dir, "rf2")
    os.makedirs(rf2_input_dir, exist_ok=True)
    
    # Copy input PDBs
    for pdb in input_pdbs:
        shutil.copy(pdb, rf2_input_dir)
    
    # RF2 needs to run from its config directory
    rf2_config_dir = os.path.join(RFANTIBODY_ROOT, "src", "rfantibody", "rf2")
    
    cmd = [
        "poetry", "run", "python",
        os.path.join(RFANTIBODY_ROOT, "scripts", "rf2_predict.py"),
        f"input.pdb_dir={rf2_input_dir}",
        f"output.pdb_dir={rf2_output_dir}"
    ]
    
    logger.info(f"Running RF2: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        cwd=rf2_config_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error(f"RF2 failed: {result.stderr}")
        raise RuntimeError(f"RF2 failed: {result.stderr[-500:]}")
    
    # Find output files
    output_files = glob.glob(os.path.join(rf2_output_dir, "*.pdb"))
    logger.info(f"RF2 generated {len(output_files)} predictions")
    
    return output_files


def run_antibody_pipeline(
    job_id: str,
    config: dict,
    progress_callback: Optional[Callable] = None
) -> dict:
    """
    Run the full antibody design pipeline
    
    Args:
        job_id: Unique job identifier
        config: Pipeline configuration with:
            - target_pdb: Target protein PDB content or path
            - framework_pdb: Framework PDB content/path (optional)
            - hotspot_residues: List of hotspot residues
            - design_loops: List of loops to design (optional)
            - num_designs: Number of designs
            - diffusion_steps: Number of diffusion steps
            - run_full_pipeline: Whether to run full pipeline
        progress_callback: Optional callback for progress updates
        
    Returns:
        dict with output file paths
    """
    
    # Create output directory
    output_dir = ensure_output_dir(job_id)
    
    if progress_callback:
        progress_callback("Preparing input files...")
    
    # Prepare target PDB
    target_pdb = save_pdb_content(
        config["target_pdb"],
        os.path.join(output_dir, "target.pdb")
    )
    
    # Prepare framework PDB (use default if not provided)
    framework_pdb = config.get("framework_pdb")
    if framework_pdb:
        framework_pdb = save_pdb_content(
            framework_pdb,
            os.path.join(output_dir, "framework.pdb")
        )
    else:
        framework_pdb = DEFAULT_FRAMEWORK_PDB
    
    # Get design parameters
    hotspot_residues = config["hotspot_residues"]
    design_loops = config.get("design_loops") or DEFAULT_DESIGN_LOOPS
    num_designs = config.get("num_designs", 1)
    diffusion_steps = config.get("diffusion_steps", 50)
    run_full_pipeline = config.get("run_full_pipeline", True)
    
    # Step 1: RFdiffusion
    rfdiffusion_outputs = run_rfdiffusion(
        job_id=job_id,
        target_pdb=target_pdb,
        framework_pdb=framework_pdb,
        hotspot_residues=hotspot_residues,
        design_loops=design_loops,
        num_designs=num_designs,
        diffusion_steps=diffusion_steps,
        output_dir=output_dir,
        progress_callback=progress_callback
    )
    
    proteinmpnn_outputs = []
    rf2_outputs = []
    
    if run_full_pipeline and rfdiffusion_outputs:
        # Step 2: ProteinMPNN
        proteinmpnn_outputs = run_proteinmpnn(
            job_id=job_id,
            input_pdbs=rfdiffusion_outputs,
            output_dir=output_dir,
            progress_callback=progress_callback
        )
        
        # Step 3: RF2
        if proteinmpnn_outputs:
            rf2_outputs = run_rf2(
                job_id=job_id,
                input_pdbs=proteinmpnn_outputs,
                output_dir=output_dir,
                progress_callback=progress_callback
            )
    
    if progress_callback:
        progress_callback("Pipeline completed!")
    
    return {
        "output_dir": output_dir,
        "rfdiffusion_outputs": rfdiffusion_outputs,
        "proteinmpnn_outputs": proteinmpnn_outputs,
        "rf2_outputs": rf2_outputs
    }
