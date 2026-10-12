import rasterio
from rasterio.windows import from_bounds
import numpy as np
import pandas as pd
import geopandas as gpd

print("1. Opening downloaded WorldPop Iraq GeoTIFF...")
tif_path = "irq_population_100m.tif"

# Exact urban extent of Kirkuk metropolitan area (WGS84 Lon/Lat)
# Bounding: West, South, East, North
bbox_kirkuk = (44.270, 35.380, 44.470, 35.530)

with rasterio.open(tif_path) as src:
    print(f"Raster CRS: {src.crs}, Dimensions: {src.width} x {src.height}")
    
    # Crop window strictly to Kirkuk bounding coordinates
    window = from_bounds(*bbox_kirkuk, transform=src.transform)
    pop_window = src.read(1, window=window)
    win_transform = src.window_transform(window)
    nodata = src.nodata if src.nodata is not None else -99999.0

# Clean nodata and negatives
pop_cleaned = np.where((pop_window == nodata) | (pop_window < 0) | np.isnan(pop_window), 0.0, pop_window)

print(f"2. Extracted Kirkuk Window: {pop_cleaned.shape[0]} rows x {pop_cleaned.shape[1]} cols")

# Convert pixels to georeferenced population points
rows, cols = pop_cleaned.shape
records = []

for r in range(rows):
    for c in range(cols):
        val = float(pop_cleaned[r, c])
        # Only retain cells where people actually reside (filter empty desert/military tarmacs)
        if val >= 1.0:
            lon, lat = rasterio.transform.xy(win_transform, r, c)
            records.append({
                "lon": lon,
                "lat": lat,
                "population": round(val, 2)
            })

df_real = pd.DataFrame(records)
print(f"Extracted {len(df_real):,} residential settlement grid cells.")

# Project coordinates to Metric UTM Zone 38N (EPSG:32638) for exact spatial measurement
gdf = gpd.GeoDataFrame(
    df_real,
    geometry=gpd.points_from_xy(df_real.lon, df_real.lat),
    crs="EPSG:4326"
).to_crs(epsg=32638)

df_real["x_utm"] = gdf.geometry.x.round(1)
df_real["y_utm"] = gdf.geometry.y.round(1)

# Save the true empirical dataset
output_file = "kirkuk_real_population.csv"
df_real.to_csv(output_file, index=False)

total_inhabitants = int(df_real["population"].sum())
print(f"3. Saved to '{output_file}'!")
print(f"Total Census/Satellite Inhabitants in Bound: {total_inhabitants:,}")
print(df_real.head())