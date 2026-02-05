import os
import json
import ee
import geemap
import gradio as gr
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from geemap.ee_tile_layers import _get_tile_url_format, _validate_palette
from starlette.middleware.cors import CORSMiddleware

# Earth Engine auth
if "EARTHENGINE_TOKEN" not in os.environ:
    raise RuntimeError("EARTHENGINE_TOKEN environment variable not found")

try:
    geemap.ee_initialize()
except Exception as e:
    raise RuntimeError(f"Earth Engine authentication failed: {e}")


# ---- Shared Tile Logic ----
def get_tile(asset_id, vis_params=None, start_date=None, end_date=None, bbox=None):
    try:
        if asset_id.startswith("ee."):
            ee_object = eval(asset_id)
        else:
            data_dict = ee.data.getAsset(asset_id)
            data_type = data_dict["type"]
            if data_type == "IMAGE":
                ee_object = ee.Image(asset_id)
            elif data_type == "IMAGE_COLLECTION":
                ee_object = ee.ImageCollection(asset_id)
            elif data_type in ["TABLE", "TABLE_COLLECTION"]:
                ee_object = ee.FeatureCollection(asset_id)
            else:
                raise ValueError(f"Unsupported data type: {data_type}")

        # Apply date range filtering for ImageCollections
        if start_date or end_date:
            if isinstance(ee_object, ee.ImageCollection):
                if start_date and end_date:
                    ee_object = ee_object.filterDate(start_date, end_date)
                elif start_date:
                    ee_object = ee_object.filterDate(start_date, "2100-01-01")
                elif end_date:
                    ee_object = ee_object.filterDate("1970-01-01", end_date)
            else:
                raise ValueError(
                    "Date filtering is only supported for ImageCollections"
                )

        # Apply bounding box filtering
        if bbox:
            if len(bbox) != 4:
                raise ValueError(
                    "bbox must be a list of 4 values: [west, south, east, north]"
                )
            geometry = ee.Geometry.BBox(*bbox)
            if isinstance(ee_object, ee.ImageCollection):
                ee_object = ee_object.filterBounds(geometry)
            elif isinstance(ee_object, ee.FeatureCollection):
                ee_object = ee_object.filterBounds(geometry)
            elif isinstance(ee_object, ee.Image):
                ee_object = ee_object.clip(geometry)
            else:
                raise ValueError(
                    f"Bounding box filtering not supported for {type(ee_object)}"
                )

        if vis_params is None:
            vis_params = {}
        if isinstance(vis_params, str):
            if len(vis_params) == 0:
                vis_params = "{}"
            if vis_params.startswith("{") and vis_params.endswith("}"):
                vis_params = json.loads(vis_params)
            else:
                raise ValueError(f"Unsupported vis_params type: {type(vis_params)}")
        elif isinstance(vis_params, dict):
            pass
        else:
            raise ValueError(f"Unsupported vis_params type: {type(vis_params)}")

        if "palette" in vis_params:
            vis_params["palette"] = _validate_palette(vis_params["palette"])

        url = _get_tile_url_format(ee_object, vis_params)
        return url
    except Exception as e:
        return f"Error: {str(e)}"


# ---- FastAPI ----
app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class TileRequest(BaseModel):
    asset_id: str
    vis_params: dict | None = None
    start_date: str | None = None
    end_date: str | None = None
    bbox: list[float] | None = None  # [west, south, east, north]


@app.post("/tile")
def get_tile_api(req: TileRequest):
    result = get_tile(
        req.asset_id, req.vis_params, req.start_date, req.end_date, req.bbox
    )
    if isinstance(result, str) and result.startswith("Error"):
        raise HTTPException(status_code=400, detail=result)
    return {"tile_url": result}


# ---- Gradio UI ----
gradio_ui = gr.Interface(
    fn=get_tile,
    inputs=[
        gr.Textbox(label="Earth Engine Asset ID", placeholder="e.g., USGS/SRTMGL1_003"),
        gr.Textbox(
            label="Visualization Parameters (JSON)",
            placeholder='{"min":0,"max":5000,"palette":"terrain"}',
        ),
    ],
    outputs="text",
    title="Earth Engine Tile URL Generator",
    description="Supports ee.Image, ee.ImageCollection, ee.FeatureCollection. Tile URL is suitable for basemap usage.",
)

app = gr.mount_gradio_app(app, gradio_ui, path="/")
