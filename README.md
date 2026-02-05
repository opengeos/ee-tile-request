---
title: Ee Tile Request
emoji: 😻
colorFrom: pink
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Earth Engine Tile URL Generator
---

# Earth Engine Tile URL Generator

A FastAPI service that generates tile URLs for Google Earth Engine assets, suitable for use with web mapping libraries like Leaflet, Mapbox, or OpenLayers.

## Features

- Generate tile URLs for Earth Engine Images, ImageCollections, and FeatureCollections
- Optional date range filtering for ImageCollections
- Optional bounding box filtering for spatial subsetting
- Customizable visualization parameters
- REST API and web UI (Gradio)
- FastAPI auto-generated documentation

## Setup

### Prerequisites

- Python 3.12+
- Google Earth Engine account with authentication token

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ee-tile-request
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your Earth Engine token:
```bash
export EARTHENGINE_TOKEN="your_token_here"
```

## Running the App

### Local Development

```bash
uvicorn main:app --host 0.0.0.0 --port 7860 --reload
```

### Docker

```bash
docker build -t ee-tile-request .
docker run -p 7860:7860 -e EARTHENGINE_TOKEN="your_token" ee-tile-request
```

### Access Points

- **Web UI**: http://localhost:7860
- **API Documentation**: http://localhost:7860/docs
- **API Endpoint**: POST http://localhost:7860/tile

## API Usage

### Endpoint

`POST /tile`

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `asset_id` | string | Yes | Earth Engine asset ID (e.g., "USGS/SRTMGL1_003") or ee expression |
| `vis_params` | object | No | Visualization parameters (min, max, palette, bands, etc.) |
| `start_date` | string | No | Start date for filtering (format: "YYYY-MM-DD") |
| `end_date` | string | No | End date for filtering (format: "YYYY-MM-DD") |
| `bbox` | array | No | Bounding box [west, south, east, north] in degrees |

### Examples

#### Basic Request

```bash
curl -X POST "http://localhost:7860/tile" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "USGS/SRTMGL1_003",
    "vis_params": {
      "min": 0,
      "max": 5000,
      "palette": ["blue", "green", "red"]
    }
  }'
```

#### With Date Range Filtering

Filter Sentinel-2 imagery to a specific time period:

```bash
curl -X POST "http://localhost:7860/tile" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "COPERNICUS/S2_SR",
    "start_date": "2023-06-01",
    "end_date": "2023-08-31",
    "vis_params": {
      "bands": ["B4", "B3", "B2"],
      "min": 0,
      "max": 3000
    }
  }'
```

#### With Bounding Box Filtering

Filter to San Francisco Bay Area:

```bash
curl -X POST "http://localhost:7860/tile" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "COPERNICUS/S2_SR",
    "bbox": [-122.5, 37.5, -122.0, 38.0],
    "vis_params": {
      "bands": ["B4", "B3", "B2"],
      "min": 0,
      "max": 3000
    }
  }'
```

#### Combined Filters

Date range and spatial filtering together:

```bash
curl -X POST "http://localhost:7860/tile" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "COPERNICUS/S2_SR",
    "start_date": "2023-07-01",
    "end_date": "2023-07-31",
    "bbox": [-122.5, 37.5, -122.0, 38.0],
    "vis_params": {
      "bands": ["B4", "B3", "B2"],
      "min": 0,
      "max": 3000
    }
  }'
```

### Response

```json
{
  "tile_url": "https://earthengine.googleapis.com/v1/projects/.../maps/.../tiles/{z}/{x}/{y}"
}
```

### Using with Web Mapping Libraries

#### Leaflet

```javascript
const tileUrl = response.tile_url;
L.tileLayer(tileUrl, {
  attribution: 'Google Earth Engine',
  maxZoom: 18
}).addTo(map);
```

#### Mapbox GL JS

```javascript
map.addSource('ee-tiles', {
  'type': 'raster',
  'tiles': [response.tile_url],
  'tileSize': 256
});

map.addLayer({
  'id': 'ee-layer',
  'type': 'raster',
  'source': 'ee-tiles'
});
```

## Web UI (Gradio)

Access the web interface at http://localhost:7860 to:
- Enter Earth Engine asset IDs
- Specify visualization parameters as JSON
- Get tile URLs instantly
- No need to write code

## Supported Data Types

- **Images** (`ee.Image`): Single images with optional clipping to bbox
- **ImageCollections** (`ee.ImageCollection`): Filtered by date and/or bbox
- **FeatureCollections** (`ee.FeatureCollection`): Filtered by bbox

## Notes

- Date filtering only works with ImageCollections
- Bounding box format: `[west, south, east, north]` in WGS84 degrees
- All filtering parameters are optional and backward compatible
- Check the FastAPI docs at `/docs` for interactive API testing

## License

MIT

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
