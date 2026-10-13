"""Build separate long-format traffic + weather + street Parquet datasets
directly from raw files, using chunked traffic reads.

Outputs:
  data/interim/traffic_weather_metr_la.parquet
  data/interim/traffic_weather_pems_bay.parquet

Expected raw files:
  data/raw/traffic_sensor_data/METR-LA.csv
  data/raw/traffic_sensor_data/PEMS-BAY.csv
  data/raw/weather/metr_la_hourly.csv
  data/raw/weather/pems_bay_hourly.csv
  data/raw/street_data/metr_la_sensor_roads.csv
  data/raw/street_data/pems_bay_sensor_roads.csv

Each traffic measurement becomes one row. Weather is joined by the latest
weather timestamp at or before the traffic timestamp (up to 1 hour old).
Street attributes are joined by sensor_id.
"""

from pathlib import Path
import tempfile

import click
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRAFFIC_DIR = PROJECT_ROOT / "data/raw/traffic_sensor_data"
DEFAULT_WEATHER_DIR = PROJECT_ROOT / "data/raw/weather"
DEFAULT_STREET_DIR = PROJECT_ROOT / "data/raw/street_data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/interim"

DATASETS = {
    "metr_la": {
        "label": "METR-LA",
        "traffic": "METR-LA.csv",
        "weather": "metr_la_hourly.csv",
        "street": "metr_la_sensor_roads.csv",
        "output": "traffic_weather_metr_la.parquet",
    },
    "pems_bay": {
        "label": "PEMS-BAY",
        "traffic": "PEMS-BAY.csv",
        "weather": "pems_bay_hourly.csv",
        "street": "pems_bay_sensor_roads.csv",
        "output": "traffic_weather_pems_bay.parquet",
    },
}

WEATHER_FEATURES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "visibility",
    "wind_speed_10m",
    "cloud_cover",
    "surface_pressure",
    "is_fog",
    "is_rain",
    "is_snow",
    "is_thunderstorm",
]

STREET_FEATURES = [
    "latitude",
    "longitude",
    "osmid",
    "name",
    "highway",
    "lanes",
    "maxspeed",
    "oneway",
    "bridge",
    "tunnel",
    "junction",
    "access",
    "width",
    "length",
    "distance_to_road_m",
    "road_match_status",
]


def read_weather(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Weather CSV not found: {path}")

    weather = pd.read_csv(path)
    required = {"timestamp", *WEATHER_FEATURES}
    missing = required - set(weather.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing weather columns: {sorted(missing)}"
        )

    weather["timestamp"] = pd.to_datetime(weather["timestamp"], errors="raise")
    weather = weather.sort_values("timestamp").reset_index(drop=True)

    if weather["timestamp"].duplicated().any():
        raise ValueError(f"Weather timestamps must be unique: {path}")

    # Normalize weather values to float columns so chunks keep one schema
    # when a later traffic timestamp has no matching weather row.
    weather[WEATHER_FEATURES] = weather[WEATHER_FEATURES].apply(
        pd.to_numeric, errors="coerce"
    ).astype("float64")
    return weather[["timestamp", *WEATHER_FEATURES]]


def read_street(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Sensor-road CSV not found: {path}")

    street = pd.read_csv(path)
    required = {"sensor_id", *STREET_FEATURES}
    missing = required - set(street.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing street columns: {sorted(missing)}"
        )

    street = street[["sensor_id", *STREET_FEATURES]].copy()
    street["sensor_id"] = street["sensor_id"].astype("string")

    if street["sensor_id"].duplicated().any():
        raise ValueError(f"Street sensor IDs must be unique: {path}")

    numeric_features = {
        "latitude", "longitude", "width", "length", "distance_to_road_m"
    }
    for column in numeric_features:
        street[column] = pd.to_numeric(street[column], errors="coerce")

    for column in set(STREET_FEATURES) - numeric_features:
        street[column] = street[column].astype("string")

    return street


def read_traffic_header(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Traffic CSV not found: {path}")

    columns = pd.read_csv(path, nrows=0).columns.tolist()
    if len(columns) < 2:
        raise ValueError(
            f"Expected timestamp/index and sensor columns: {path}"
        )
    if columns[0] not in ("", "Unnamed: 0", "timestamp"):
        raise ValueError(
            f"Expected first column to be timestamp/index, got "
            f"{columns[0]!r} in {path.name}"
        )
    if len(columns[1:]) != len(set(columns[1:])):
        raise ValueError(f"Duplicate sensor columns found in {path.name}")
    return columns


def convert_one(
    dataset_key: str,
    traffic_dir: Path,
    weather_dir: Path,
    street_dir: Path,
    output_dir: Path,
    chunk_size: int,
) -> Path:
    config = DATASETS[dataset_key]
    traffic_path = traffic_dir / config["traffic"]
    weather_path = weather_dir / config["weather"]
    street_path = street_dir / config["street"]
    output_path = output_dir / config["output"]

    # Read small dimension tables once; stream the large traffic matrix.
    weather = read_weather(weather_path)
    street = read_street(street_path)
    header = read_traffic_header(traffic_path)
    sensor_columns = header[1:]

    # Validate that traffic sensor IDs and road sensor IDs have compatible
    # string representations. Unmatched IDs are allowed but reported.
    traffic_sensor_ids = {str(sensor_id) for sensor_id in sensor_columns}
    street_sensor_ids = set(street["sensor_id"].dropna().astype(str))
    matched_ids = traffic_sensor_ids & street_sensor_ids
    print(
        f"{config['label']}: {len(sensor_columns)} traffic sensors; "
        f"{len(matched_ids)} have street metadata; "
        f"{len(traffic_sensor_ids - street_sensor_ids)} do not.",
        flush=True,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f"{output_path.stem}.",
        suffix=".parquet",
        dir=output_dir,
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)

    writer = None
    total_rows = 0
    chunks = 0

    try:
        for chunk in pd.read_csv(traffic_path, chunksize=chunk_size):
            chunks += 1
            chunk = chunk.rename(columns={chunk.columns[0]: "timestamp"})
            chunk["timestamp"] = pd.to_datetime(
                chunk["timestamp"], errors="raise"
            )

            if chunk["timestamp"].duplicated().any():
                raise ValueError(
                    f"Duplicate traffic timestamps in chunk {chunks}"
                )

            # Wide traffic matrix -> one row per timestamp/sensor.
            long_data = chunk.melt(
                id_vars=["timestamp"],
                value_vars=sensor_columns,
                var_name="sensor_id",
                value_name="speed",
            )
            long_data["sensor_id"] = long_data["sensor_id"].astype("string")
            long_data["speed"] = pd.to_numeric(
                long_data["speed"], errors="coerce"
            )
            long_data = long_data.sort_values("timestamp")

            # Attach the latest hourly weather row, no more than 1 hour old.
            merged = pd.merge_asof(
                long_data,
                weather,
                on="timestamp",
                direction="backward",
                tolerance=pd.Timedelta(hours=1),
            )

            # Attach static road attributes by sensor.
            merged = merged.merge(
                street,
                on="sensor_id",
                how="left",
                validate="many_to_one",
            )

            merged["weather_available"] = (
                merged["temperature_2m"].notna().astype("int8")
            )
            merged["street_available"] = (
                merged["road_match_status"].notna().astype("int8")
            )
            merged.insert(0, "dataset", config["label"])

            table = pa.Table.from_pandas(merged, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(
                    str(temp_path),
                    table.schema,
                    compression="snappy",
                )
            elif not table.schema.equals(writer.schema, check_metadata=False):
                raise ValueError(
                    f"Output schema changed at chunk {chunks}; "
                    "check source column types."
                )

            writer.write_table(table)
            total_rows += len(merged)

            print(
                f"{config['label']}: chunk {chunks} | "
                f"{len(chunk):,} timestamps -> {len(merged):,} rows | "
                f"{total_rows:,} total rows",
                flush=True,
            )

        if writer is None:
            raise ValueError(f"No traffic data read for {config['label']}")

        writer.close()
        writer = None
        temp_path.replace(output_path)

    except Exception:
        if writer is not None:
            writer.close()
        temp_path.unlink(missing_ok=True)
        raise

    print(f"Created {output_path}")
    print(f"Total rows: {total_rows:,}")
    return output_path


@click.command()
@click.option(
    "--dataset",
    type=click.Choice(["metr_la", "pems_bay", "both"], case_sensitive=False),
    default="both",
    show_default=True,
    help="Build one region or both as separate files.",
)
@click.option(
    "--chunk-size",
    type=click.IntRange(min=1),
    default=32,
    show_default=True,
    help="Number of timestamp rows loaded per chunk.",
)
@click.option(
    "--traffic-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_TRAFFIC_DIR,
    show_default=True,
)
@click.option(
    "--weather-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_WEATHER_DIR,
    show_default=True,
)
@click.option(
    "--street-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_STREET_DIR,
    show_default=True,
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    show_default=True,
)
def main(
    dataset, chunk_size, traffic_dir, weather_dir, street_dir, output_dir
):
    """Build separate long-format traffic/weather/street Parquet datasets."""
    selected = (
        ["metr_la", "pems_bay"]
        if dataset.lower() == "both"
        else [dataset.lower()]
    )

    failures = []
    for key in selected:
        print(f"\n{'=' * 60}\nProcessing {key}\n{'=' * 60}", flush=True)
        try:
            convert_one(
                key,
                Path(traffic_dir),
                Path(weather_dir),
                Path(street_dir),
                Path(output_dir),
                chunk_size,
            )
        except Exception as exc:
            failures.append((key, exc))
            print(
                f"FAILED {key}: {type(exc).__name__}: {exc}",
                flush=True,
            )

    if failures:
        details = "; ".join(f"{key}: {error}" for key, error in failures)
        raise click.ClickException(details)


if __name__ == "__main__":
    main()
