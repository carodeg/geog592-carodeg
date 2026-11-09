# %% [markdown]
# ## Cartography Assignment
# 
# In this assignment, I will be comparing occurences of the invasive kudzu vine to those of the native mountain laurel in North Carolina, as kudzu harms the growing ability of mountain laurel.
# 
# kudzu (Pueraria_montana): GBIF.org (21 October 2026) GBIF Occurrence Download https://doi.org/10.15468/dl.28fqwd
# 
# mountain laurel (kalmia latifolia): GBIF.org (21 October 2026) GBIF Occurrence Download https://doi.org/10.15468/dl.e3rd7y
# 
# data was filtered to NC, USA, 2025, human observation, and present in GBIF

# %%

import argparse #used to create the two command-line arguments
import numpy as np
from shapely.geometry import Polygon
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# Import the two species datasets
kalmia_latifolia = pd.read_csv(
    "data/Kalmia_latifolia.csv",
    sep="\t" #fix for error
)

pueraria_montana = pd.read_csv(
    "data/Pueraria_montana.csv",
    sep="\t"
)


# %%
# Load NC county boundaries
counties = gpd.read_file("data/counties_nc.json")

# Check the coordinate reference system
print(counties.crs)

nc_counties = counties.to_crs(epsg=32119)

# Plot NC counties
nc_counties.plot(
    edgecolor="black",
    facecolor="white",
    figsize=(10, 6)
)

plt.title("North Carolina Counties")

# %%
# Add species names
kalmia_latifolia["queried_species"] = "Kalmia latifolia"
pueraria_montana["queried_species"] = "Pueraria montana"

# Combine the two datasets
species_df = pd.concat(
    [kalmia_latifolia, pueraria_montana],
    ignore_index=True
)

# Keep the columns needed for mapping
species_df = species_df[
    ["queried_species", "decimalLongitude", "decimalLatitude"]
].copy()

# Ensure coordinates are numeric
species_df["decimalLongitude"] = pd.to_numeric(
    species_df["decimalLongitude"], errors="coerce"
)
species_df["decimalLatitude"] = pd.to_numeric(
    species_df["decimalLatitude"], errors="coerce"
)

# Remove missing or invalid coordinates
species_df = species_df.dropna(
    subset=["decimalLongitude", "decimalLatitude"]
)

species_df = species_df[
    species_df["decimalLongitude"].between(-180, 180)
    & species_df["decimalLatitude"].between(-90, 90)
].copy()


# %%
# Create a GeoDataFrame from latitude and longitude
species_points = gpd.GeoDataFrame(
    species_df.copy(),
    geometry=gpd.points_from_xy(
        species_df["decimalLongitude"],
        species_df["decimalLatitude"]
    ),
    crs="EPSG:4326"
)

# Match NC counties CRS
species_points = species_points.to_crs(nc_counties.crs)

# Plot observations over county boundaries
fig, ax = plt.subplots(figsize=(12, 6))

nc_counties.plot(
    ax=ax,
    facecolor="whitesmoke",
    edgecolor="gray",
    linewidth=0.5
)

colors = {
    "Kalmia latifolia": "green",
    "Pueraria montana": "purple"
}

for species, color in colors.items():
    species_points.loc[
        species_points["queried_species"] == species
    ].plot(
        ax=ax,
        color=color,
        markersize=10,
        alpha=0.5,
        label=species
    )

ax.set_title("Kalmia Latifolia and Pueraria Montana Observations")
ax.legend(title="Species")
ax.set_axis_off()


# %%
# Assign each observation to an NC county- spatial join
points_by_county = gpd.sjoin(
    species_points,
    nc_counties[["County", "FIPS", "geometry"]],
    how="inner",
    predicate="within"
).drop(columns="index_right")


# %%
#count observations by county
counts = (
    points_by_county
    .groupby(["FIPS", "queried_species"])
    .size()
    .unstack(fill_value=0) #unstack the species column to create a separate column for each species, filling missing values with 0
    .reindex(
        columns=["Kalmia latifolia", "Pueraria montana"],
        fill_value=0
    )
)


# Total observations of both species per county
totals = counts.sum(axis=1).rename("total")

# Join totals to NC county boundaries
county_map = nc_counties.merge(
    totals,
    left_on="FIPS",
    right_index=True, 
    how="left"
)

county_map["total"] = county_map["total"].fillna(0)

# Create four choropleths using AI
fig, axes = plt.subplots(
    2, 2,
    figsize=(18, 12),
    layout="constrained"
)

schemes = [
    (None, "Continuous color scale"),
    ("equalinterval", "Equal interval"),
    ("quantiles", "Quantiles"),
    ("fisherjenks", "Natural breaks")
]

for ax, (scheme, title) in zip(axes.flat, schemes):

    options = {
        "column": "total",
        "cmap": "RdPu",
        "edgecolor": "gray",
        "linewidth": 0.5,
        "legend": True,
        "ax": ax
    }

    if scheme is not None:
        options["scheme"] = scheme
        options["k"] = 5

    county_map.plot(**options)

    ax.set_title(title)
    ax.set_axis_off()

plt.savefig(
    "species_classification.png",
    dpi=300,
    bbox_inches="tight"
)


# %%
import numpy as np
from matplotlib.patches import Rectangle

# Attach species counts to county polygons
bivariate = nc_counties.merge(
    counts,
    left_on="FIPS",
    right_index=True,
    how="left"
)

species = ["Kalmia latifolia", "Pueraria montana"]
bivariate[species] = bivariate[species].fillna(0)

# Classify each species
for name in species:
    values = bivariate[name]
    median = values.loc[values > 0].median()

    bivariate[name + "_class"] = np.select(
        [values == 0, values <= median],
        [0, 1],
        default=2
    )

    print(name, "positive-count median:", median)

# Rows = increasing mountain laurel counts
# Columns = increasing kudzu counts
palette = np.array([
    ["#eeeeee", "#c5b5d8", "#80619e"],
    ["#e6b899", "#b992a8", "#785b82"],
    ["#cf763e", "#a35e63", "#63384f"]
])

bivariate["color"] = [
    palette[laurel, kudzu]
    for laurel, kudzu in zip(
        bivariate["Kalmia latifolia_class"],
        bivariate["Pueraria montana_class"]
    )
]

fig, ax = plt.subplots(figsize=(13, 8))

bivariate.plot(
    color=bivariate["color"],
    edgecolor="white",
    linewidth=0.5,
    ax=ax
)

ax.set_title(
    "Mountain Laurel and Kudzu Observations by NC County"
)
ax.set_axis_off()

# Create bivariate legend
legend_ax = ax.inset_axes([0.05, 0.05, 0.19, 0.23])

for laurel in range(3):
    for kudzu in range(3):
        legend_ax.add_patch(
            Rectangle(
                (kudzu, laurel), 1, 1,
                facecolor=palette[laurel, kudzu],
                edgecolor="white"
            )
        )

legend_ax.set_xlim(0, 3)
legend_ax.set_ylim(0, 3)
legend_ax.set_aspect("equal")

legend_ax.set_xticks([0.5, 1.5, 2.5])
legend_ax.set_xticklabels(["None", "Low", "High"])
legend_ax.set_yticks([0.5, 1.5, 2.5])
legend_ax.set_yticklabels(["None", "Low", "High"])

legend_ax.set_xlabel("Kudzu")
legend_ax.set_ylabel("Mountain Laurel")

plt.savefig(
    "species_bivariate.png",
    dpi=300,
    bbox_inches="tight"
)


# %% [markdown]
# 
# Classification schemes can influence our interpretation of species populations by exaggerating differences to make them appear larger, even if recorded data is similar. For example, the quantile map makes the western concentration of observations appear much more widespread, while the other three maps emphasize a smaller number of counties with high counts.

# %% [markdown]
# ## Assignment #2:
# Generate two pngs, one of a proportional symbol and another of a hexagon map.

# %%
# Total observations per county
totals = counts.sum(axis=1).rename("total")

# Join totals to NC county boundaries
county_map = nc_counties.merge(
    totals,
    left_on="FIPS",
    right_index=True,
    how="left"
)

county_map["total"] = county_map["total"].fillna(0)


# %%

# Convert county polygons to centroid points
centers = county_map.geometry.centroid

# %%
#Making proportional Symbol Map more reusable by passing the geographic data into the function rather than relying on variables defined elsewhere.
def propSymbolMap(ax, county_map, centers):

    # Plot county boundaries
    county_map.plot(
        ax=ax,
        facecolor="whitesmoke",
        edgecolor="gray",
        linewidth=0.5
    )

    # Plot proportional circles
    ax.scatter(
        centers.x,
        centers.y,
        s=county_map["total"] * 5, #makes the area of each circle proportional to the number of observations in that county
        color="#8e235c",
        alpha=0.6,
        edgecolors="white",
        linewidths=0.5
    )

    ax.set_title(
        "Mountain Laurel and Kudzu Observations by NC County"
    )
    ax.set_axis_off()

    return ax

#Total observations per county, with larger circles representing more records

# %%
#create a hexagonal grid over NC counties
import numpy as np
from shapely.geometry import Polygon

# Set geographic boundaries and points
states = nc_counties
points = points_by_county.copy()

# Hexagon radius in meters
radius = 20000

xmin, ymin, xmax, ymax = states.total_bounds
hexagons = []

for column, x in enumerate(
    np.arange(xmin - radius, xmax + 2 * radius, 1.5 * radius)
):
    for y in np.arange(
        ymin - radius, ymax + 2 * radius,
        np.sqrt(3) * radius
    ):

        # Offset alternating columns
        center_y = (
            y + (column % 2) * np.sqrt(3) * radius / 2
        )

        angles = np.arange(6) * np.pi / 3

        hexagons.append(
            Polygon([
                (
                    x + radius * np.cos(angle),
                    center_y + radius * np.sin(angle)
                )
                for angle in angles
            ])
        )

# Create GeoDataFrame
grid = gpd.GeoDataFrame(
    {"hex_id": range(len(hexagons))},
    geometry=hexagons,
    crs=states.crs
)

# Keep hexagons that intersect NC
region = states.geometry.union_all()

grid = grid.loc[
    grid.intersects(region)
].copy()

grid.plot(
    edgecolor="gray",
    facecolor="white",
    figsize=(12, 7)
)

plt.title("North Carolina Hexagon Grid")


# %%

# Give each observation a unique ID
points = points.reset_index(drop=True)
points["point_id"] = points.index

# Spatial join points to hexagons
joined = gpd.sjoin(
    points,
    grid[["hex_id", "geometry"]],
    how="inner",
    predicate="intersects"
)

# Avoid counting points twice on shared edges
joined = (
    joined.sort_values("hex_id")
    .drop_duplicates("point_id")
)

# Count records by hexagon and species
hex_counts = (
    joined.groupby(["hex_id", "queried_species"])
    .size()
    .unstack(fill_value=0)
    .reindex(
        columns=["Kalmia latifolia", "Pueraria montana"],
        fill_value=0
    )
)

# Join counts to hexagon grid
grid = grid.merge(
    hex_counts,
    left_on="hex_id",
    right_index=True,
    how="left"
)

species = ["Kalmia latifolia", "Pueraria montana"]

grid[species] = grid[species].fillna(0)

# Calculate total observations
grid["total"] = grid[species].sum(axis=1)


# %%
def hexCountMap(ax, grid, states):

    grid.plot(
        ax=ax,
        column="total",
        cmap="RdPu",
        edgecolor="white",
        linewidth=0.2,
        legend=True,
        legend_kwds={
            "label": "Number of observation records"
        }
    )

    # Add NC county boundaries
    states.boundary.plot(
        ax=ax,
        color="gray",
        linewidth=0.4
    )

    ax.set_title(
        "Mountain Laurel and Kudzu Observations per Hexagon"
    )
    ax.set_axis_off()

    return ax

#Observations aggregated into equally sized geographic cells

# %%
#checking map observations
print("County observations:", county_map["total"].sum())
print("Hexagon observations:", grid["total"].sum())

# %%
def main():

    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Create maps of mountain laurel and kudzu observations in NC"
    )

    # Required argument
    parser.add_argument(
        "map_type",
        choices=["proportional", "hexagon"],
        help="Choose which type of map to create"
    )

    # Optional argument
    parser.add_argument(
        "--output",
        default="species_map.png",
        help="Name of the output PNG file"
    )

    args = parser.parse_args()

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Choose map based on required argument
    if args.map_type == "proportional":

        propSymbolMap(ax, county_map, centers)

    elif args.map_type == "hexagon":

        hexCountMap(ax, grid, states)

    # Save the selected map
    plt.savefig(
        args.output,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

    print(f"Map saved as {args.output}")

# %%
if __name__ == "__main__":
    main()


