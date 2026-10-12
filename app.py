import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Kirkuk Healthcare Desert Analytics",
    page_icon="",
    layout="wide"
)

st.title("Kirkuk Healthcare Spatial Accessibility & Siting Analytics")
st.caption("Empirical E2SFCA Accessibility Modeling based on UN-Adjusted WorldPop 100m Demographics & Official MOH Hospital Capacities.")

# 1. Load Empirical Data
@st.cache_data
def load_data():
    pop_df = pd.read_csv("kirkuk_real_population.csv")
    # Subsample slightly for responsive browser map rendering
    if len(pop_df) > 5000:
        pop_df = pop_df.sample(5000, random_state=42).copy()
    return pop_df

pop_df = load_data()

# Hospital Registry
HOSPITALS = [
    {"name": "Azadi Teaching Hospital", "lat": 35.470424, "lon": 44.411906, "beds": 400},
    {"name": "Kirkuk General Hospital", "lat": 35.465885, "lon": 44.388492, "beds": 400},
    {"name": "Kirkuk Pediatric Hospital", "lat": 35.453999, "lon": 44.385018, "beds": 120},
    {"name": "Al-Nasr Hospital", "lat": 35.423587, "lon": 44.393393, "beds": 180}
]

hosp_df = pd.DataFrame(HOSPITALS)

# Project Hospitals to UTM Zone 38N
pts = [Point(h["lon"], h["lat"]) for h in HOSPITALS]
hosp_gdf = gpd.GeoDataFrame(HOSPITALS, geometry=pts, crs="EPSG:4326").to_crs(epsg=32638)
hosp_df["x_utm"] = hosp_gdf.geometry.x
hosp_df["y_utm"] = hosp_gdf.geometry.y

# 2. Sidebar Analytical Controls
st.sidebar.header("Analytical Parameters")

d0_km = st.sidebar.slider("Travel Catchment Threshold (km):", min_value=2.0, max_value=10.0, value=6.0, step=0.5)
d0 = d0_km * 1000.0

desert_cutoff = st.sidebar.slider("Healthcare Desert Cutoff (Beds / 1k capita):", min_value=0.5, max_value=2.5, value=1.0, step=0.1)

n_clinics = st.sidebar.slider("Simulate Optimal New Clinics (K-Means):", min_value=1, max_value=5, value=2)

# 3. Compute E2SFCA Algorithm
pop_pts = pop_df[["x_utm", "y_utm"]].values
hosp_pts = hosp_df[["x_utm", "y_utm"]].values

D = cdist(pop_pts, hosp_pts, metric="euclidean")

def gaussian_decay(distance, max_dist):
    w = (np.exp(-0.5 * (distance / max_dist)**2) - np.exp(-0.5)) / (1.0 - np.exp(-0.5))
    return np.where(distance <= max_dist, w, 0.0)

W = gaussian_decay(D, d0)

# Step 1: Supply to Demand (R_j)
demand = np.sum(pop_df["population"].values[:, np.newaxis] * W, axis=0)
demand = np.where(demand == 0, 1e-6, demand)
R_j = (hosp_df["beds"].values / demand) * 1000.0

# Step 2: Per-Capita Access Score (A_i)
pop_df["access_score"] = np.sum(W * R_j, axis=1)
pop_df["is_desert"] = pop_df["access_score"] < desert_cutoff

total_pop = int(pop_df["population"].sum())
desert_pop = int(pop_df[pop_df["is_desert"]]["population"].sum())
desert_pct = (desert_pop / total_pop) * 100.0

# 4. K-Means Optimization for New Facilities
desert_subset = pop_df[pop_df["is_desert"]]
if len(desert_subset) >= n_clinics:
    kmeans = KMeans(n_clusters=n_clinics, random_state=42, n_init=10)
    kmeans.fit(desert_subset[["x_utm", "y_utm"]].values, sample_weight=desert_subset["population"].values)
    new_sites_utm = kmeans.cluster_centers_

    new_sites_gdf = gpd.GeoDataFrame(
        geometry=[Point(p[0], p[1]) for p in new_sites_utm],
        crs="EPSG:32638"
    ).to_crs(epsg=4326)
    new_sites_coords = [(pt.y, pt.x) for pt in new_sites_gdf.geometry]
else:
    new_sites_coords = []

# 5. Dashboard KPI Cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Analyzed Population", f"{total_pop:,}")
col2.metric("Total Acute Beds", f"{hosp_df['beds'].sum():,}")
col3.metric("Desert Population", f"{desert_pop:,}", delta=f"{desert_pct:.1f}% of total", delta_color="inverse")
col4.metric("Proposed New Sites", n_clinics)

# 6. Data Prep for Folium HeatMap
clean_pop = pop_df.dropna(subset=["lat", "lon", "access_score"]).copy()
max_score = clean_pop["access_score"].max()
if max_score > 0:
    clean_pop["norm_score"] = clean_pop["access_score"] / max_score
else:
    clean_pop["norm_score"] = 0.0

heat_data = [
    [float(r["lat"]), float(r["lon"]), float(r["norm_score"])]
    for _, r in clean_pop.iterrows()
]

# 7. Interactive Folium Map
m = folium.Map(
    location=[35.460, 44.395],
    zoom_start=12,
    tiles=None
)

folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    attr="Google Satellite",
    name="Satellite Hybrid"
).add_to(m)

folium.TileLayer(
    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr="OpenStreetMap",
    name="Street Map"
).add_to(m)

HeatMap(
    heat_data,
    radius=15,
    blur=20,
    min_opacity=0.35,
    gradient={0.2: "#0000ff", 0.4: "#00ffff", 0.7: "#ffff00", 1.0: "#ff0000"}
).add_to(m)

for _, h in hosp_df.iterrows():
    folium.Marker(
        location=[float(h["lat"]), float(h["lon"])],
        popup=f"<b>{h['name']}</b><br>Bed Capacity: {h['beds']}",
        tooltip=h["name"],
        icon=folium.Icon(color="red", icon="plus-sign")
    ).add_to(m)

for idx, (lat, lon) in enumerate(new_sites_coords, 1):
    folium.Marker(
        location=[float(lat), float(lon)],
        popup=f"<b>Optimal Recommended Clinic #{idx}</b><br>Lat: {lat:.5f}, Lon: {lon:.5f}",
        tooltip=f"Proposed Site #{idx}",
        icon=folium.Icon(color="green", icon="star")
    ).add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width="100%", height=650, returned_objects=[])

if new_sites_coords:
    st.subheader("📍 Algorithm Recommended Clinic Coordinates")
    coords_df = pd.DataFrame(new_sites_coords, columns=["Latitude", "Longitude"])
    coords_df.index = [f"Recommended Facility #{i+1}" for i in range(len(coords_df))]
    st.dataframe(coords_df.style.format("{:.5f}"))