# kirkuk-healthcare-access
Spatial accessibility modeling (E2SFCA) and data-driven clinic siting in Kirkuk using UN/WorldPop gridded demographics and MOH hospital capacities.

# Kirkuk Healthcare Accessibility & Spatial Optimization

An empirical spatial data science pipeline and interactive dashboard evaluating acute healthcare accessibility across metropolitan Kirkuk, Iraq, using the Enhanced Two-Step Floating Catchment Area (E2SFCA) model and weighted $k$-means facility siting.

## Methodology

- **Accessibility Model:** Enhanced Two-Step Floating Catchment Area (E2SFCA) with continuous Gaussian distance decay ($d_0 = 6\text{ km}$).
- **Spatial Optimization:** Weighted $k$-means clustering targeting high-density populations within designated healthcare deserts ($A_i < 1.0\text{ beds / 1,000 capita}$).
- **Projection System:** Projected into **UTM Zone 38N (EPSG:32638)** for ground-metric Euclidean distance computation.

## Data Sources

1. **Demographics:** Gridded human population counts derived from UN OCHA / WorldPop 2020 constrained building footprint rasters (`irq_ppp_2020_UNadj.tif`) aggregated to 100m grid units.
2. **Healthcare Supply:** Acute care hospital locations and licensed operational bed capacities referenced from Iraqi Ministry of Health baseline specifications.

## Project Structure

- `app.py`: Interactive Streamlit analytical dashboard featuring real-time sensitivity sliders and Folium spatial heatmaps.
- `spatial_analysis.py`: Standalone scientific modeling script implementing the E2SFCA mathematical matrix operations and $k$-means optimization.
- `process_raster.py`: Data ingestion script extracting population centroids from the official GeoTIFF raster.
- `kirkuk_real_population.csv`: Pre-extracted metropolitan population grid points used for lightweight deployment.

## Local Setup

```bash
git clone [https://github.com/YOUR_USERNAME/kirkuk-healthcare-access.git](https://github.com/YOUR_USERNAME/kirkuk-healthcare-access.git)
cd kirkuk-healthcare-access

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
