"""
Job Manager for RFantibody API - handles async job execution
"""
import uuid
import asyncio
import threading
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback

from .models import JobStatus

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Represents a running or completed job"""
    job_id: str
    status: JobStatus
    created_at: datetime
    config: dict
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[str] = None
    error: Optional[str] = None
    output_dir: Optional[str] = None
    rfdiffusion_outputs: list = field(default_factory=list)
    proteinmpnn_outputs: list = field(default_factory=list)
    rf2_outputs: list = field(default_factory=list)


class JobManager:
    """Manages job queue and execution"""
    
    def __init__(self, max_concurrent_jobs: int = 1):
        self.jobs: Dict[str, Job] = {}
        self.max_concurrent_jobs = max_concurrent_jobs
        self._lock = threading.Lock()
        self._executor_thread: Optional[threading.Thread] = None
        self._job_queue: list = []
        self._running = False
        
    def start(self):
        """Start the job executor thread"""
        self._running = True
        self._executor_thread = threading.Thread(target=self._job_executor, daemon=True)
        self._executor_thread.start()
        logger.info("Job executor started")
        
    def stop(self):
        """Stop the job executor thread"""
        self._running = False
        if self._executor_thread:
            self._executor_thread.join(timeout=5)
        logger.info("Job executor stopped")
        
    def create_job(self, config: dict) -> Job:
        """Create a new job and add to queue"""
        job_id = str(uuid.uuid4())[:8]
        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            config=config
        )
        
        with self._lock:
            self.jobs[job_id] = job
            self._job_queue.append(job_id)
            
        logger.info(f"Created job {job_id}")
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> list:
        """Get all jobs"""
        return list(self.jobs.values())
    
    def _job_executor(self):
        """Background thread that executes jobs from queue"""
        from .pipeline import run_antibody_pipeline
        
        while self._running:
            job_id = None
            
            with self._lock:
                # Count running jobs
                running_count = sum(
                    1 for j in self.jobs.values() 
                    if j.status == JobStatus.RUNNING
                )
                
                # Get next pending job if we have capacity
                if running_count < self.max_concurrent_jobs and self._job_queue:
                    job_id = self._job_queue.pop(0)
                    
            if job_id:
                job = self.jobs.get(job_id)
                if job and job.status == JobStatus.PENDING:
                    self._execute_job(job, run_antibody_pipeline)
            else:
                # No jobs to process, sleep a bit
                import time
                time.sleep(1)
                
    def _execute_job(self, job: Job, pipeline_fn):
        """Execute a single job"""
        logger.info(f"Starting job {job.job_id}")
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.progress = "Starting pipeline..."
        
        try:
            # Run the pipeline
            result = pipeline_fn(
                job_id=job.job_id,
                config=job.config,
                progress_callback=lambda msg: self._update_progress(job.job_id, msg)
            )
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.output_dir = result.get("output_dir")
            job.rfdiffusion_outputs = result.get("rfdiffusion_outputs", [])
            job.proteinmpnn_outputs = result.get("proteinmpnn_outputs", [])
            job.rf2_outputs = result.get("rf2_outputs", [])
            job.progress = "Completed successfully"
            
            logger.info(f"Job {job.job_id} completed successfully")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            job.progress = f"Failed: {str(e)}"
            logger.error(f"Job {job.job_id} failed: {e}\n{traceback.format_exc()}")
            
    def _update_progress(self, job_id: str, message: str):
        """Update job progress"""
        job = self.jobs.get(job_id)
        if job:
            job.progress = message
            logger.info(f"Job {job_id}: {message}")


# Global job manager instance
job_manager = JobManager()
