import logging
from pathlib import Path
import duckdb
import matplotlib.pyplot as plt
import pandas as pd

def analyze_and_plot(config: dict) -> pd.DataFrame:
    curated_dir = Path(config["paths"]["curated_dir"])
    output_dir = Path(config["paths"]["output_dir"])
    con = duckdb.connect(database=":memory:")
    
    query = f"""
        SELECT
            taxi_type,
            COUNT(*) AS total_trips,
            ROUND(SUM(passenger_count), 0) AS total_passengers,
            ROUND(SUM(trip_distance), 2) AS total_distance_miles,
            ROUND(AVG(trip_distance), 2) AS avg_trip_distance,
            ROUND(AVG(fare_amount), 2) AS avg_fare_amount,
            ROUND(AVG(duration_minutes), 2) AS avg_duration_minutes
        FROM read_parquet('{curated_dir}/curated_*.parquet')
        GROUP BY taxi_type
        ORDER BY total_trips DESC
    """
    summary_df = con.execute(query).df()
    total_trips_all = summary_df["total_trips"].sum()
    summary_df["trip_share_pct"] = (summary_df["total_trips"] / total_trips_all * 100).round(2)
    
    summary_path = output_dir / "most_used_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    
    logging.info(f"\n{'='*50}\nSUMMARY RESULT (2024 H1):\n{summary_df.to_string(index=False)}\n{'='*50}")
    
    # สร้างกราฟเปรียบเทียบ
    plt.figure(figsize=(8, 5))
    bars = plt.bar(summary_df["taxi_type"].str.upper(), summary_df["total_trips"] / 1e6, color=['#fec44f', '#78c679'])
    plt.title("NYC Taxi Total Trips (2024 H1) - Yellow vs Green", fontsize=14, fontweight="bold")
    plt.xlabel("Taxi Type", fontsize=12)
    plt.ylabel("Total Trips (Millions)", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2., h + 0.2, f"{h:.2f}M", ha='center', va='bottom', fontweight='bold')
        
    plt.tight_layout()
    chart_path = output_dir / "taxi_comparison_chart.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    
    # พิมพ์คำตอบของโจทย์
    top_taxi = summary_df.iloc[0]
    print("\n" + "="*60)
    print(f"ANSWER: Which taxi type was the most used in 2024 H1?")
    print(f"-> {top_taxi['taxi_type'].upper()} Taxi is the most used taxi type.")
    print(f"-> Total Cleaned Trips: {top_taxi['total_trips']:,} trips ({top_taxi['trip_share_pct']}%)")
    print("="*60 + "\n")
    
    con.close()
    return summary_df
