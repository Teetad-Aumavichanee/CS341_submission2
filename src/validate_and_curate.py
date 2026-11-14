import logging
from pathlib import Path
import duckdb
import pandas as pd

def process_and_curate(files: list[dict], config: dict) -> pd.DataFrame:
    curated_dir = Path(config["paths"]["curated_dir"])
    output_dir = Path(config["paths"]["output_dir"])
    curated_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    con = duckdb.connect(database=":memory:")
    dq_records = []
    
    for item in files:
        taxi = item["taxi_type"]
        month = item["month"]
        filepath = item["path"]
        
        pickup_col = "tpep_pickup_datetime" if taxi == "yellow" else "lpep_pickup_datetime"
        dropoff_col = "tpep_dropoff_datetime" if taxi == "yellow" else "lpep_dropoff_datetime"
        
        logging.info(f"[VALIDATE & CURATE] กำลังประมวลผล {taxi} เดือน {month:02d}...")
        
        # 1. รันการตรวจสอบ Data Quality ตาม Logic เดิมใน submission 1 คือ:
        # passenger_count > 0 (ต้องมีผู้โดยสารมากกว่า 0)
        # pickup_datetime < dropoff_datetime (เวลาขึ้นต้องมาก่อนเวลาลง)
        # fare_amount > 0 (ค่าโดยสารต้องมากกว่า 0)
        validation_query = f"""
            SELECT
                COUNT(*) as total_rows,
                SUM(CASE WHEN passenger_count > 0 THEN 1 ELSE 0 END) as valid_passenger,
                SUM(CASE WHEN {pickup_col} < {dropoff_col} THEN 1 ELSE 0 END) as valid_time_order,
                SUM(CASE WHEN fare_amount > 0 THEN 1 ELSE 0 END) as valid_fare,
                SUM(CASE WHEN passenger_count IS NULL THEN 1 ELSE 0 END) as null_passengers,
                SUM(CASE WHEN passenger_count <= 0 THEN 1 ELSE 0 END) as non_positive_passengers,
                SUM(CASE WHEN {pickup_col} >= {dropoff_col} THEN 1 ELSE 0 END) as invalid_time,
                SUM(CASE WHEN fare_amount <= 0 THEN 1 ELSE 0 END) as non_positive_fare
            FROM read_parquet('{filepath}')
        """
        val_res = con.execute(validation_query).fetchone()
        total_rows = val_res[0]
        
        # 2. ทำความสะอาดและสร้าง Curated Parquet
        # กำหนด Standard Schema กลางสำหรับแท็กซี่ทั้งสองประเภท
        curated_file = curated_dir / f"curated_{taxi}_{config['year']}-{month:02d}.parquet"
        
        clean_copy_query = f"""
            COPY (
                SELECT
                    '{taxi}' AS taxi_type,
                    CAST({pickup_col} AS TIMESTAMP) AS pickup_datetime,
                    CAST({dropoff_col} AS TIMESTAMP) AS dropoff_datetime,
                    CAST(PULocationID AS INTEGER) AS pickup_location_id,
                    CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
                    CAST(passenger_count AS INTEGER) AS passenger_count,
                    CAST(trip_distance AS DOUBLE) AS trip_distance,
                    CAST(fare_amount AS DOUBLE) AS fare_amount,
                    CAST(total_amount AS DOUBLE) AS total_amount,
                    ROUND(EPOCH(CAST({dropoff_col} AS TIMESTAMP) - CAST({pickup_col} AS TIMESTAMP)) / 60.0, 2) AS duration_minutes
                FROM read_parquet('{filepath}')
                WHERE
                    passenger_count > 0 AND
                    {pickup_col} < {dropoff_col} AND
                    fare_amount > 0
            ) TO '{curated_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
        """
        con.execute(clean_copy_query)
        
        # นับจำนวนแถวที่ผ่าน (Curated count)
        cleaned_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{curated_file}')").fetchone()[0]
        dropped_rows = total_rows - cleaned_count
        retention_rate = round((cleaned_count / total_rows * 100), 2) if total_rows > 0 else 0
        
        dq_records.append({
            "taxi_type": taxi,
            "month": f"{config['year']}-{month:02d}",
            "total_raw_rows": total_rows,
            "cleaned_rows": cleaned_count,
            "dropped_rows": dropped_rows,
            "retention_rate_pct": retention_rate,
            "invalid_passenger_count": val_res[5] + val_res[4],
            "invalid_time_order": val_res[6],
            "invalid_fare_amount": val_res[7]
        })
        
        logging.info(f"[SUCCESS] {curated_file.name}: เก็บได้ {cleaned_count:,} / {total_rows:,} แถว ({retention_rate}%)")
    
    dq_df = pd.DataFrame(dq_records)
    dq_df.to_csv(output_dir / "data_quality_report.csv", index=False)
    
    # ดึงตัวอย่าง Curated Data เก็บเป็น CSV เล็กๆ ใน output
    sample_path = output_dir / "curated_sample.csv"
    con.execute(f"""
        COPY (
            SELECT * FROM read_parquet('{curated_dir}/curated_*.parquet') LIMIT 10
        ) TO '{sample_path}' (HEADER, DELIMITER ',');
    """)
    
    con.close()
    return dq_df
