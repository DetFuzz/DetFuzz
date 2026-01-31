from pathlib import Path
import os
import sys
import time
import shutil
from typing import List, Tuple, Dict
from inputs import prepare_inputs
from payload_producer import produce_payloads, parse_result_to_json
from output_writer import write_payload_files
from analyzer import analyzer

# Execution Mode: 1 = Print "URL Path + coarse_category" only, 2 = Print full debug information
OUTPUT_MODE = "1"  

def set_proxy(proxy_url: str) -> None:
    os.environ['http_proxy'] = proxy_url
    os.environ['https_proxy'] = proxy_url


def show_progress(i: int, total: int) -> None:
    width = 40
    ratio = (i / total) if total else 0
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    percent = int(ratio * 100)
    sys.stdout.write(f"\r[{bar}] {percent}% ({i}/{total})")
    sys.stdout.flush()


def clean_output_dir(base_output: Path) -> None:
    if base_output.exists():
        shutil.rmtree(base_output)
    base_output.mkdir(parents=True, exist_ok=True)


def process_jobs(workspace: Path, vendor: str, product: str, jobs: List[Dict[str, str]], output_mode: str = "2") -> None:
    total = len(jobs)
    if total == 0:
        print("No input files found.")
        return

    base_output = workspace / vendor / product / "output"
    clean_output_dir(base_output)

    show_progress(0, total)
    durations: List[Tuple[str, float]] = []
    t0 = time.time()
    for idx, job in enumerate(jobs, start=1):
        t_start = time.time()
        label = job.get("URI", job["UI_INFO"]) or job["UI_INFO"]
        
        if output_mode == "2":
            print(f"\n[Task {idx}/{total}] Process: {label}")
            print("-" * 60)
            print(f"\n>>> Phase: Functional Analysis (analyzer)")
        
        job = analyzer(job)
        
        if output_mode == "2":
            print(f"\n>>> Phase: Payload Generation (produce_payloads)")
        result_json = produce_payloads(job)
        
        if output_mode == "2":
            print(f"\n>>> Phase: Writing to Output File (write_payload_files)")
        write_payload_files(
            vendor, 
            product, 
            job["UI_INFO"], 
            result_json, 
            workspace, 
            uri=job.get("URI", ""), 
            output_mode=output_mode,
            data_packet=job.get("DATA_PACKET", "")
        )
        
        show_progress(idx, total)
        durations.append((label, time.time() - t_start))

    total_elapsed = time.time() - t0
    print("Per-task elapsed time:")
    for ui, sec in durations:
        print(f"  {ui}: {sec:.2f}s")
    print(f"Total elapsed: {total_elapsed:.2f}s")


def main():
    if OUTPUT_MODE == "2":
        print("=" * 60)
        print("Phase: Program Startup")
        print("=" * 60)
    workspace = Path(__file__).resolve().parent
    vendor = "Tenda"
    product = "AC18"
    # set_proxy("http://127.0.0.1:2005")
    
    if OUTPUT_MODE == "2":
        print("\n" + "=" * 60)
        print("Phase: Preparing Input Data")
        print("=" * 60)
    jobs = prepare_inputs(workspace, vendor, product, OUTPUT_MODE)
    if OUTPUT_MODE == "2":
        print(f"Loaded {len(jobs)} input files\n")
    
    if OUTPUT_MODE == "2":
        print("=" * 60)
        print("Phase: Starting Task Execution")
        print("=" * 60)
    
    # Inject OUTPUT_MODE into each job
    for job in jobs:
        job["OUTPUT_MODE"] = OUTPUT_MODE
    
    process_jobs(workspace, vendor, product, jobs, OUTPUT_MODE)


if __name__ == "__main__":
    main()


