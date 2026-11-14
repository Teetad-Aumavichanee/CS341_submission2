import argparse
import logging
from pathlib import Path
import time
import yaml

from src.download import download_data
from src.validate_and_curate import process_and_curate
from src.analyze import analyze_and_plot

def setup_logger(log_dir: str):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / "pipeline.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

def main():
    parser = argparse.ArgumentParser(description="NYC Taxi 2024 H1 Reproducible Data Pipeline")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    
    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    setup_logger(config["paths"]["log_dir"])
    logging.info(">>> เริ่มต้นรัน Data Pipeline <<<")
    start_time = time.time()
    
    # 1. Ingestion / Download
    files = download_data(config)
    
    # 2. Validation & Curate to Parquet
    process_and_curate(files, config)
    
    # 3. Analytics & Visualization
    analyze_and_plot(config)
    
    duration = time.time() - start_time
    logging.info(f">>> เสร็จสิ้นกระบวนการ Pipeline ในเวลา {duration:.2f} วินาที <<<")

if __name__ == "__main__":
    main()
