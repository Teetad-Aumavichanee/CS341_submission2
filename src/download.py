import logging
from pathlib import Path
import requests

def download_data(config: dict) -> list[dict]:
    raw_dir = Path(config["paths"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    year = config["year"]
    months = config["months"]
    taxi_types = config["taxi_types"]
    base_url = config["base_url"]
    
    downloaded_files = []
    
    for taxi in taxi_types:
        for month in months:
            filename = f"{taxi}_tripdata_{year}-{month:02d}.parquet"
            filepath = raw_dir / filename
            url = f"{base_url}/{filename}"
            
            # ตรวจสอบว่ามีไฟล์อยู่แล้วหรือไม่ (Idempotent)
            if filepath.exists() and filepath.stat().st_size > 0:
                logging.info(f"[SKIP] พบไฟล์แล้ว: {filename}")
                downloaded_files.append({"taxi_type": taxi, "month": month, "path": str(filepath)})
                continue
                
            logging.info(f"[DOWNLOADING] กำลังดาวน์โหลด: {url} ...")
            try:
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(filepath, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192 * 16):
                            f.write(chunk)
                logging.info(f"[SUCCESS] ดาวน์โหลดเสร็จสิ้น: {filename}")
                downloaded_files.append({"taxi_type": taxi, "month": month, "path": str(filepath)})
            except Exception as e:
                logging.error(f"[ERROR] ดาวน์โหลดล้มเหลว {filename}: {e}")
                if filepath.exists():
                    filepath.unlink()
                    
    return downloaded_files
