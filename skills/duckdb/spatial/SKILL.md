---
name: spatial
license: CC-BY-4.0
description: Answer spatial-data questions with DuckDB, including coordinate work, distance calculations, spatial joins, containment checks, density analysis, and geographic format conversion. Use when the user mentions maps, locations, coordinates, nearby places, GeoJSON, Shapefile, GeoPackage, GPX, GeoParquet, or Overture Maps data.
---

# Spatial

Treat the user's request as either a spatial question or a spatial dataset to inspect.

## Step 1 - Understand What The User Needs

Classify the question:

| Pattern | Data source | Key functions |
| --- | --- | --- |
| "Find X near Y" with no user file | Overture Maps on S3 | `ST_Distance_Spheroid`, bbox filtering |
| "How far between A and B" | Geocoded points or user data | `ST_Distance_Spheroid` |
| "Which points fall inside polygons" | User files | `ST_Contains` |
| "Analyze this GeoJSON, Shapefile, or GPX" | User file | `ST_Read`, measurement functions |
| "Show density or hotspots" | User data or Overture | H3 hex binning |
| "Convert to GeoJSON or GeoPackage" | User file | `COPY TO (FORMAT GDAL)` |
| "Count buildings or roads in an area" | Overture Maps | bbox filtering plus aggregation |

If the question involves real-world places, POIs, buildings, roads, or boundaries and the user has not provided a file, use **Overture Maps**. Read [references/overture.rst](references/overture.rst) for S3 paths and schema.

For spatial function syntax, read [references/functions.rst](references/functions.rst).

## Step 2 - Write And Run The Query

Always start with:

```sql
LOAD spatial;
SET geometry_always_xy = true;
```

Add extensions as needed:

- Overture or other remote data: `LOAD httpfs; CREATE SECRET (TYPE S3, PROVIDER config, REGION 'us-west-2');`
- H3 hex binning: `INSTALL h3 FROM community; LOAD h3;`

### Key Principles

**bbox filtering first**: When querying Overture, always filter on `bbox.xmin`, `bbox.xmax`, `bbox.ymin`, and `bbox.ymax` before any spatial function. This uses Parquet predicate pushdown and avoids downloading the full dataset.

**Always set `geometry_always_xy = true`**: This ensures all spatial functions interpret coordinates as longitude, latitude. Without it, spheroid functions assume latitude first and return incorrect results.

**Use spheroid functions for real-world distances**: `ST_Distance_Spheroid` returns meters on WGS84. Plain `ST_Distance` uses planar coordinates and is usually wrong for longitude and latitude.

**`POINT_2D` requirement**: Spheroid functions such as `ST_Distance_Spheroid`, `ST_Area_Spheroid`, and `ST_DWithin_Spheroid` require `POINT_2D` inputs rather than generic `GEOMETRY`. Extract coordinates first:

```sql
ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D
```

**CSV with lat/lng needs conversion**: Use `ST_Point(longitude, latitude)`, with longitude first.

Run the query in a single shell call. Prefer a heredoc for multi-line SQL so shell quoting does not break complex spatial queries:

```bash
duckdb <<'SQL'
LOAD spatial;
<ADDITIONAL_SETUP>
<YOUR_QUERY>
SQL
```

## Step 3 - Present Results

- For tabular results, show the data directly.
- For spatial results, consider exporting to GeoJSON for visualization with `COPY TO 'result.geojson' WITH (FORMAT GDAL, DRIVER 'GeoJSON')`.
- For distance or area results, use human-readable units such as `km` or `m`.
- For density or hotspot results, describe the pattern and offer to export the result for visualization.

If the query fails:

- **`duckdb: command not found`** -> open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), install DuckDB, then retry
- **Missing extension** -> run `INSTALL spatial; LOAD spatial;` or `INSTALL h3 FROM community; LOAD h3;`
- **S3 access denied** -> suggest checking AWS credentials
- **No results with Overture** -> widen the bounding box, check category spelling, or try a broader search
