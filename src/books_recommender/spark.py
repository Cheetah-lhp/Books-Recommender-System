from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def create_spark(config: dict[str, Any]):
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "PySpark is required. Install the project with: pip install -e ."
        ) from exc

    spark_config = config["spark"]
    builder = (
        SparkSession.builder.appName(str(spark_config["app_name"]))
        .master(str(spark_config["master"]))
        .config("spark.driver.memory", str(spark_config["driver_memory"]))
        .config("spark.sql.shuffle.partitions", str(spark_config["shuffle_partitions"]))
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
    )
    checkpoint_dir = Path(config["paths"]["checkpoints"])
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    spark = builder.getOrCreate()
    # Hadoop's local checkpoint implementation requires winutils.exe on Windows.
    # ALS can run without SparkContext checkpointing for local development/tests.
    if os.name != "nt":
        spark.sparkContext.setCheckpointDir(str(checkpoint_dir))
    spark.sparkContext.setLogLevel("WARN")
    return spark
