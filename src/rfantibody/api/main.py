"""
RFantibody API - FastAPI application for antibody design
"""
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import torch
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    AntibodyDesignRequest,
    JobResponse,
    JobStatusResponse,
    JobResultResponse,
    HealthResponse,
    JobStatus
)
from .job_manager import job_manager, Job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting RFantibody API...")
    job_manager.start()
    logger.info("RFantibody API started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down RFantibody API...")
    job_manager.stop()
    logger.info("RFantibody API stopped")


# Create FastAPI app
app = FastAPI(
    title="RFantibody API",
    description="API for antibody design using RFdiffusion, ProteinMPNN, and RF2",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        gpu_available=torch.cuda.is_available(),
        models_loaded=True  # Could add actual model check here
    )


@app.post("/design", response_model=JobResponse)
async def create_design_job(request: AntibodyDesignRequest):
    """
    Create a new antibody design job.
    
    The job runs asynchronously. Use the returned job_id to check status and get results.
    
    Required inputs:
    - target_pdb: PDB content or file path of target protein
    - hotspot_residues: List of residues to target, e.g. ["T305", "T456"]
    
    Optional inputs:
    - framework_pdb: Antibody framework (default: hu-4D5-8_Fv)
    - design_loops: CDR loops to design (default: L1-L3, H1-H3)
    - num_designs: Number of designs (1-10)
    - diffusion_steps: Quality setting (15-200)
    - run_full_pipeline: Run all 3 steps or just RFdiffusion
    """
    
    # Build config from request
    config = {
        "target_pdb": request.target_pdb,
        "framework_pdb": request.framework_pdb,
        "hotspot_residues": request.hotspot_residues,
        "design_loops": request.design_loops,
        "num_designs": request.num_designs,
        "diffusion_steps": request.diffusion_steps,
        "run_full_pipeline": request.run_full_pipeline
    }
    
    # Create job
    job = job_manager.create_job(config)
    
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        message="Job created and queued for processing",
        created_at=job.created_at
    )


@app.post("/design/upload", response_model=JobResponse)
async def create_design_job_with_upload(
    target_pdb: UploadFile = File(..., description="Target protein PDB file"),
    hotspot_residues: str = Form(..., description="Comma-separated hotspot residues, e.g. 'T305,T456'"),
    framework_pdb: Optional[UploadFile] = File(None, description="Optional antibody framework PDB"),
    design_loops: Optional[str] = Form(None, description="Comma-separated design loops, e.g. 'L1:8-13,H3:5-13'"),
    num_designs: int = Form(1, ge=1, le=10),
    diffusion_steps: int = Form(50, ge=15, le=200),
    run_full_pipeline: bool = Form(True)
):
    """
    Create a new antibody design job with file uploads.
    
    Use this endpoint to upload PDB files directly.
    """
    
    # Read target PDB
    target_content = (await target_pdb.read()).decode('utf-8')
    
    # Read framework PDB if provided
    framework_content = None
    if framework_pdb:
        framework_content = (await framework_pdb.read()).decode('utf-8')
    
    # Parse hotspot residues
    hotspots = [r.strip() for r in hotspot_residues.split(',')]
    
    # Parse design loops if provided
    loops = None
    if design_loops:
        loops = [l.strip() for l in design_loops.split(',')]
    
    # Build config
    config = {
        "target_pdb": target_content,
        "framework_pdb": framework_content,
        "hotspot_residues": hotspots,
        "design_loops": loops,
        "num_designs": num_designs,
        "diffusion_steps": diffusion_steps,
        "run_full_pipeline": run_full_pipeline
    }
    
    # Create job
    job = job_manager.create_job(config)
    
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        message="Job created and queued for processing",
        created_at=job.created_at
    )


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the status of a job"""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error
    )


@app.get("/jobs/{job_id}/results", response_model=JobResultResponse)
async def get_job_results(job_id: str):
    """Get the results of a completed job"""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job.status == JobStatus.PENDING:
        raise HTTPException(status_code=400, detail="Job is still pending")
    
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Job is still running")
    
    return JobResultResponse(
        job_id=job.job_id,
        status=job.status,
        output_files=job.rfdiffusion_outputs + job.proteinmpnn_outputs + job.rf2_outputs,
        rfdiffusion_outputs=job.rfdiffusion_outputs,
        proteinmpnn_outputs=job.proteinmpnn_outputs,
        rf2_outputs=job.rf2_outputs,
        error=job.error
    )


@app.get("/jobs/{job_id}/download/{filename}")
async def download_output_file(job_id: str, filename: str):
    """Download a specific output file from a job"""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed")
    
    # Find file in outputs
    all_files = job.rfdiffusion_outputs + job.proteinmpnn_outputs + job.rf2_outputs
    matching = [f for f in all_files if os.path.basename(f) == filename]
    
    if not matching:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    
    return FileResponse(
        matching[0],
        media_type="chemical/x-pdb",
        filename=filename
    )


@app.get("/jobs", response_model=List[JobStatusResponse])
async def list_jobs():
    """List all jobs"""
    
    jobs = job_manager.get_all_jobs()
    return [
        JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error=job.error
        )
        for job in jobs
    ]


# Run with: uvicorn rfantibody.api.main:app --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
