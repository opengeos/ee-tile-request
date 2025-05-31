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
def get_tile(asset_id, vis_params=None):
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


@app.post("/tile")
def get_tile_api(req: TileRequest):
    result = get_tile(req.asset_id, req.vis_params)
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
