"""
Spark Join Script: MusicBrainz + Wikipedia
Joins your parsed_artists.json (MusicBrainz) with wiki_music.jsonl (Wikipedia)
based on normalized artist/band names.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import lower, trim, regexp_replace, col

def main():
    # Configure Spark for better performance
    spark = SparkSession.builder \
        .appName("MusicWikiJoin") \
        .config("spark.sql.shuffle.partitions", "8") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")  # Reduce verbose logging

    print("Loading MusicBrainz data...")
    # Load all individual JSON files from parsed_artists directory
    # Use multiLine=True because the JSON files are pretty-printed
    artists_df = spark.read.option("multiLine", "true").json("parsed_artists/")

    print("Loading Wikipedia music data...")
    wiki_df = spark.read.json("data/wiki_music.jsonl")
    
    print(f"Loaded {artists_df.count():,} MusicBrainz artists")
    print(f"Loaded {wiki_df.count():,} Wikipedia entities")

    print("Normalizing names for join...")
    # Normalize MusicBrainz artist names - remove "The", special chars, lowercase
    # Use (?i) for case-insensitive regex in PySpark
    # Keep ALL MusicBrainz columns, just add normalized name
    artists_df = artists_df.withColumn(
        "name_norm", 
        lower(trim(regexp_replace(regexp_replace("name", r'(?i)^(the|a|an)\s+', ''), r'[^a-zA-Z0-9 ]', '')))
    )
    
    # Normalize Wikipedia titles - remove "The", special chars, lowercase
    # Keep ALL Wikipedia columns, just add normalized title and rename conflicting columns
    wiki_df = wiki_df.withColumn(
        "title_norm",
        lower(trim(regexp_replace(regexp_replace("title", r'(?i)^(the|a|an)\s+', ''), r'[^a-zA-Z0-9 ]', '')))
    ).withColumnRenamed("type", "wiki_type") \
     .withColumnRenamed("url", "wiki_url")  # Rename URL to avoid conflict with MusicBrainz URL
    
    # Cache the smaller dataset (MusicBrainz) for faster joins
    artists_df.cache()
    print(f"Cached MusicBrainz data for faster joining")

    print("Joining datasets...")
    joined_df = artists_df.join(wiki_df, artists_df.name_norm == wiki_df.title_norm, "inner")
    
    # Count first to trigger the join and see results
    total_joined = joined_df.count()
    print(f"Found {total_joined:,} matches!")
    
    if total_joined == 0:
        print("No matches found! Check your data.")
        spark.stop()
        return
    
    # Show sample matches
    print("\nSample matches (first 10):")
    joined_df.select(
        col("name").alias("mb_name"), 
        col("title").alias("wiki_title"),
        col("url")
    ).show(10, truncate=False)

    print("💾 Saving joined results...")
    # Save as parquet (much faster and smaller than JSON)
    joined_df.write.mode("overwrite").parquet("data/joined_artists.parquet")
    print("Saved data/joined_artists.parquet")
    
    # Optionally save a smaller JSON sample for inspection
    joined_df.limit(100).write.mode("overwrite").json("data/joined_artists_sample.json")
    print("Saved data/joined_artists_sample.json (first 100 records)")

    # Calculate statistics
    print("\nCalculating statistics...")
    unique_wiki_count = joined_df.select("title").distinct().count()
    unique_mb_count = joined_df.select("name").distinct().count()
    total_artists = artists_df.count()
    total_wiki = wiki_df.count()
    match_rate = (unique_mb_count / total_artists * 100) if total_artists > 0 else 0

    print("\n==================== JOIN SUMMARY ====================")
    print(f"MusicBrainz artists total:     {total_artists:,}")
    print(f"Wikipedia entities total:      {total_wiki:,}")
    print(f"Unique MusicBrainz matched:    {unique_mb_count:,} ({match_rate:.1f}%)")
    print(f"Unique Wikipedia matched:      {unique_wiki_count:,}")
    print(f"Total joined records:          {total_joined:,}")
    print("\n✅ Output files created:")
    print("  → data/joined_artists.parquet (main output)")
    print("  → data/joined_artists_sample.json (100 samples)")
    print("======================================================\n")

    spark.stop()
    print("🎉 Join complete!")


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
