"""
Pydantic models for RFantibody API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AntibodyDesignRequest(BaseModel):
    """Request model for antibody design job"""
    
    # Target protein PDB (required) - can be file content or path
    target_pdb: str = Field(..., description="Target protein PDB file content or path")
    
    # Framework PDB (optional - uses default if not provided)
    framework_pdb: Optional[str] = Field(
        None, 
        description="Antibody framework PDB file content or path. Uses default hu-4D5-8_Fv if not provided"
    )
    
    # Hotspot residues on target (required)
    hotspot_residues: List[str] = Field(
        ..., 
        description="List of hotspot residues on target, e.g. ['T305', 'T456']"
    )
    
    # Design loops configuration (optional - uses sensible defaults)
    design_loops: Optional[List[str]] = Field(
        None,
        description="CDR loops to design, e.g. ['L1:8-13', 'H3:5-13']. Uses defaults if not provided"
    )
    
    # Number of designs to generate
    num_designs: int = Field(
        default=1, 
        ge=1, 
        le=10,
        description="Number of antibody designs to generate (1-10)"
    )
    
    # Diffusion steps (affects quality vs speed)
    diffusion_steps: int = Field(
        default=50,
        ge=15,
        le=200,
        description="Number of diffusion steps (15-200). Higher = better quality but slower"
    )
    
    # Run full pipeline or just RFdiffusion
    run_full_pipeline: bool = Field(
        default=True,
        description="Run full pipeline (RFdiffusion + ProteinMPNN + RF2) or just RFdiffusion"
    )


class JobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Response model for job status query"""
    job_id: str
    status: JobStatus
    progress: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class JobResultResponse(BaseModel):
    """Response model for job results"""
    job_id: str
    status: JobStatus
    output_files: Optional[List[str]] = None
    rfdiffusion_outputs: Optional[List[str]] = None
    proteinmpnn_outputs: Optional[List[str]] = None
    rf2_outputs: Optional[List[str]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    gpu_available: bool
    models_loaded: bool
