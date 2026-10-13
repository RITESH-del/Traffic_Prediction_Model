
import osmnx as ox
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import MultiPoint


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SENSOR_DIR = PROJECT_ROOT / "data/raw/traffic_sensor_data"
OUTPUT_DIR = PROJECT_ROOT / "data/raw/street_data"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Set to None to process all sensor locations.
MAX_SENSORS = None

# Buffer around the full sensor region, in meters.
REGION_BUFFER = 1500

# Flag matches farther than this distance for review.
MAX_MATCH_DISTANCE = 250

ROAD_ATTRIBUTES = [
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
    "service",
    "surface",
    "width",
    "length",
]


# --------------------------------------------------
# Load sensor coordinates
# --------------------------------------------------

def load_sensors(sensor_file, latitude_column="latitude",
                 longitude_column="longitude"):

    sensor_path = SENSOR_DIR / sensor_file

    if not sensor_path.exists():
        print(f"Sensor file not found: {sensor_path}")
        return None

    sensors = pd.read_csv(sensor_path)

    required = {latitude_column, longitude_column}
    missing = required - set(sensors.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {missing}. "
            f"Available columns: {sensors.columns.tolist()}"
        )

    sensors = sensors.copy()

    sensors[latitude_column] = pd.to_numeric(
        sensors[latitude_column], errors="coerce"
    )
    sensors[longitude_column] = pd.to_numeric(
        sensors[longitude_column], errors="coerce"
    )

    sensors = sensors.dropna(
        subset=[latitude_column, longitude_column]
    )

    sensors = sensors[
        sensors[latitude_column].between(-90, 90)
        & sensors[longitude_column].between(-180, 180)
    ].copy()

    if sensors.empty:
        raise ValueError("No valid sensor coordinates found.")

    # Keep the original sensor identifier when available.
    id_column = next(
        (c for c in ["sensor_id", "sensor", "id"]
         if c in sensors.columns),
        None,
    )

    if id_column:
        sensors["sensor_id"] = sensors[id_column].astype(str)
    else:
        sensors["sensor_id"] = sensors.index.astype(str)

    # Remove duplicate coordinates.
    sensors = sensors.drop_duplicates(
        subset=[latitude_column, longitude_column]
    ).copy()

    if MAX_SENSORS is not None:
        sensors = sensors.head(MAX_SENSORS).copy()

    sensors = sensors.reset_index(drop=True)

    print(f"Loaded {len(sensors)} sensor locations.")

    return sensors, latitude_column, longitude_column


# --------------------------------------------------
# Download road network once and cache it
# --------------------------------------------------

def fetch_street_data(name, sensors,
                      latitude_column="latitude",
                      longitude_column="longitude"):

    roads_path = OUTPUT_DIR / f"{name}_roads.geojson"

    # Reuse the saved network on later runs.
    if roads_path.exists():
        print(f"Using cached road network: {roads_path.name}")
        return gpd.read_file(roads_path)

    print(f"{name}: preparing one regional road download...")

    sensor_points = gpd.GeoDataFrame(
        sensors[["sensor_id", latitude_column, longitude_column]].copy(),
        geometry=gpd.points_from_xy(
            sensors[longitude_column],
            sensors[latitude_column],
        ),
        crs="EPSG:4326",
    )

    # Project coordinates into meters before buffering.
    projected = sensor_points.to_crs(
        sensor_points.estimate_utm_crs()
    )

    region = (
        MultiPoint(list(projected.geometry))
        .convex_hull
        .buffer(REGION_BUFFER)
    )

    region_wgs84 = gpd.GeoSeries(
        [region],
        crs=projected.crs,
    ).to_crs("EPSG:4326").iloc[0]

    print("Downloading roads from OpenStreetMap...")

    graph = ox.graph_from_polygon(
        region_wgs84,
        network_type="drive",
        simplify=True,
    )

    print(
        f"Downloaded graph: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges"
    )

    roads = ox.graph_to_gdfs(
        graph,
        nodes=False,
        edges=True,
    ).reset_index()

    available = [
        col for col in ROAD_ATTRIBUTES
        if col in roads.columns
    ]

    roads = roads[available + ["geometry"]].copy()

    roads = gpd.GeoDataFrame(
        roads,
        geometry="geometry",
        crs="EPSG:4326",
    )

    roads.to_file(roads_path, driver="GeoJSON")

    print(f"Saved {len(roads)} road segments to {roads_path}")

    return roads


# --------------------------------------------------
# Match sensors to nearest road segments
# --------------------------------------------------

def match_sensors_to_roads(name, sensors, roads,
                           latitude_column="latitude",
                           longitude_column="longitude"):

    output_path = OUTPUT_DIR / f"{name}_sensor_roads.csv"

    sensor_points = gpd.GeoDataFrame(
        sensors.copy(),
        geometry=gpd.points_from_xy(
            sensors[longitude_column],
            sensors[latitude_column],
        ),
        crs="EPSG:4326",
    )

    # Use a metric CRS for distance calculations.
    metric_crs = sensor_points.estimate_utm_crs()

    sensor_points = sensor_points.to_crs(metric_crs)
    roads_metric = roads.to_crs(metric_crs)

    matched = gpd.sjoin_nearest(
        sensor_points,
        roads_metric,
        how="left",
        distance_col="distance_to_road_m",
    )

    # Handle ties where a sensor is equally close to multiple roads.
    matched = (
        matched.sort_values("distance_to_road_m")
        .drop_duplicates(subset=["sensor_id"])
        .copy()
    )

    matched["road_match_status"] = matched[
        "distance_to_road_m"
    ].le(MAX_MATCH_DISTANCE).map({
        True: "matched",
        False: "review",
    })

    # CSV output doesn't need geometry.
    matched = matched.drop(
        columns=["geometry", "index_right"],
        errors="ignore",
    )

    matched.to_csv(output_path, index=False)

    print(f"Saved sensor-road matches: {output_path}")
    print("\nMatch status:")
    print(matched["road_match_status"].value_counts())

    return matched


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    ox.settings.use_cache = True
    ox.settings.log_console = True

    datasets = [
        {
            "name": "metr_la",
            "sensor_file": "graph_sensor_locations_la.csv",
        },
        {
            "name": "pems_bay",
            "sensor_file": "graph_sensor_locations_bay.csv",
        },
    ]

    for dataset in datasets:
        name = dataset["name"]

        print(f"\n{'=' * 50}")
        print(f"Processing {name}")
        print(f"{'=' * 50}")

        try:
            result = load_sensors(dataset["sensor_file"])

            if result is None:
                continue

            sensors, lat_col, lon_col = result

            roads = fetch_street_data(
                name=name,
                sensors=sensors,
                latitude_column=lat_col,
                longitude_column=lon_col,
            )

            match_sensors_to_roads(
                name=name,
                sensors=sensors,
                roads=roads,
                latitude_column=lat_col,
                longitude_column=lon_col,
            )

        except Exception as exc:
            print(f"Failed to process {name}: {exc}")

    print("\nProcessing finished.")
