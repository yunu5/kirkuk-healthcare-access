"""
Kirkuk Metropolitan Healthcare Accessibility & Siting Model
Methodology: Enhanced Two-Step Floating Catchment Area (E2SFCA) with Gaussian Decay
Demographic source: UN OCHA / WorldPop 2020 constrained building raster (100m)
"""

from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

# Spatial reference systems
EPSG_WGS84 = 4326
EPSG_UTM38N = 32638

# Baseline acute care facilities (MOH Registry)
FACILITY_SPECS = [
    {"name": "Azadi Teaching Hospital", "lat": 35.470424, "lon": 44.411906, "beds": 400},
    {"name": "Kirkuk General Hospital", "lat": 35.465885, "lon": 44.388492, "beds": 400},
    {"name": "Kirkuk Pediatric Hospital", "lat": 35.453999, "lon": 44.385018, "beds": 120},
    {"name": "Al-Nasr Hospital", "lat": 35.423587, "lon": 44.393393, "beds": 180},
]


def load_and_project_facilities(facilities_data: list) -> gpd.GeoDataFrame:
    geometry = [Point(f["lon"], f["lat"]) for f in facilities_data]
    gdf = gpd.GeoDataFrame(facilities_data, geometry=geometry, crs=f"EPSG:{EPSG_WGS84}")
    return gdf.to_crs(epsg=EPSG_UTM38N)


def gaussian_weight(distance_matrix: np.ndarray, threshold: float) -> np.ndarray:
    """Continuous Gaussian distance decay function within threshold d0."""
    decay = (np.exp(-0.5 * (distance_matrix / threshold) ** 2) - np.exp(-0.5)) / (1.0 - np.exp(-0.5))
    return np.where(distance_matrix <= threshold, decay, 0.0)


def compute_e2sfca(pop_df: pd.DataFrame, facilities_gdf: gpd.GeoDataFrame, d0_meters: float = 6000.0) -> pd.DataFrame:
    pop_coords = pop_df[["x_utm", "y_utm"]].to_numpy()
    hosp_coords = np.column_stack([facilities_gdf.geometry.x, facilities_gdf.geometry.y])

    # Pairwise Euclidean metric in meters
    dist_matrix = cdist(pop_coords, hosp_coords, metric="euclidean")
    weights = gaussian_weight(dist_matrix, threshold=d0_meters)

    # Step 1: Facility provider-to-population ratio (R_j)
    weighted_demand = np.sum(pop_df["population"].to_numpy()[:, np.newaxis] * weights, axis=0)
    weighted_demand = np.where(weighted_demand == 0, 1e-6, weighted_demand)
    r_j = (facilities_gdf["beds"].to_numpy() / weighted_demand) * 1000.0

    # Step 2: Population accessibility score (A_i)
    pop_df = pop_df.copy()
    pop_df["access_score"] = np.sum(weights * r_j, axis=1)
    return pop_df


def optimize_facility_locations(pop_df: pd.DataFrame, desert_cutoff: float, n_sites: int = 2) -> np.ndarray:
    deserts = pop_df[pop_df["access_score"] < desert_cutoff]
    if len(deserts) < n_sites:
        return np.empty((0, 2))

    coords = deserts[["x_utm", "y_utm"]].to_numpy()
    weights = deserts["population"].to_numpy()

    kmeans = KMeans(n_clusters=n_sites, random_state=42, n_init=10)
    kmeans.fit(coords, sample_weight=weights)
    return kmeans.cluster_centers_


def run_pipeline(data_path: str = "kirkuk_real_population.csv"):
    if not Path(data_path).exists():
        raise FileNotFoundError(f"Missing processed demographic grid: {data_path}")

    pop_df = pd.read_csv(data_path)
    facilities_gdf = load_and_project_facilities(FACILITY_SPECS)

    # Execute accessibility scoring
    results_df = compute_e2sfca(pop_df, facilities_gdf, d0_meters=6000.0)

    # Evaluate desert baseline (< 1.0 bed per 1,000 residents)
    desert_mask = results_df["access_score"] < 1.0
    total_pop = results_df["population"].sum()
    desert_pop = results_df.loc[desert_mask, "population"].sum()

    print(f"Population Evaluated: {int(total_pop):,}")
    print(f"Healthcare Desert Population: {int(desert_pop):,} ({desert_pop / total_pop * 100:.1f}%)")

    # Siting optimization
    optimal_sites = optimize_facility_locations(results_df, desert_cutoff=1.0, n_sites=2)
    sites_gdf = gpd.GeoDataFrame(
        geometry=[Point(x, y) for x, y in optimal_sites],
        crs=f"EPSG:{EPSG_UTM38N}"
    ).to_crs(epsg=EPSG_WGS84)

    print("\nOptimized Facility Coordinates:")
    for i, pt in enumerate(sites_gdf.geometry, 1):
        print(f"Site {i}: Lat {pt.y:.5f}, Lon {pt.x:.5f}")


if __name__ == "__main__":
    run_pipeline()