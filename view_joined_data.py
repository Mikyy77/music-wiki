#!/usr/bin/env python3
"""
Helper script to view and export the joined Spark data
"""

from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder.appName("ViewJoinedData").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    
    # Read the parquet file
    df = spark.read.parquet("data/joined_artists.parquet")
    
    print(f"\nTotal records: {df.count():,}")
    print(f"Columns: {', '.join(df.columns)}\n")
    
    # Show sample
    print("Sample records:")
    df.select("name", "title", "wiki_type", "url").show(20, truncate=False)
    
    # Export as single JSONL file (one JSON per line)
    print("\nExporting to data/joined_artists_flat.jsonl...")
    df.coalesce(1).write.mode("overwrite").json("data/joined_artists_export")
    
    # Find the actual file and rename it
    import os
    import shutil
    export_dir = "data/joined_artists_export"
    json_file = [f for f in os.listdir(export_dir) if f.startswith("part-") and f.endswith(".json")][0]
    shutil.copy(f"{export_dir}/{json_file}", "data/joined_artists_flat.jsonl")
    shutil.rmtree(export_dir)
    
    print("Created data/joined_artists_flat.jsonl")
    print("\nYou can now use regular tools:")
    print("  wc -l data/joined_artists_flat.jsonl")
    print("  cat data/joined_artists_flat.jsonl | jq '.'")
    
    spark.stop()

if __name__ == "__main__":
    main()
