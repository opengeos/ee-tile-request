import os
import json
import ee
import geemap
import gradio as gr
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from geemap.ee_tile_layers import _get_tile_url_format, _validate_palette
from starlette.middleware.cors import CORSMiddleware
from typing import Any, Dict, List, Optional, Tuple, Union

# # Earth Engine auth
# if "EARTHENGINE_TOKEN" not in os.environ:
#     raise RuntimeError("EARTHENGINE_TOKEN environment variable not found")

# try:
#     geemap.ee_initialize()
# except Exception as e:
#     raise RuntimeError(f"Earth Engine authentication failed: {e}")


def get_env_var(key: str) -> Optional[str]:
    """Retrieves an environment variable or Colab secret for the given key.

    Colab secrets have precedence over environment variables.

    Args:
        key (str): The key that's used to fetch the environment variable.

    Returns:
        Optional[str]: The retrieved key, or None if no environment variable was found.
    """
    if not key:
        return None

    return os.environ.get(key)


def ee_initialize(
    token_name: str = "EARTHENGINE_TOKEN",
    auth_mode: Optional[str] = None,
    auth_args: Optional[Dict[str, Any]] = None,
    project: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Authenticates Earth Engine and initialize an Earth Engine session

    Args:
        token_name (str, optional): The name of the Earth Engine token.
            Defaults to "EARTHENGINE_TOKEN". In Colab, you can also set a secret
            named "EE_PROJECT_ID" to initialize Earth Engine.
        auth_mode (str, optional): The authentication mode, can be one of colab,
            notebook, localhost, or gcloud.
            See https://developers.google.com/earth-engine/guides/auth for more
            details. Defaults to None.
        auth_args (dict, optional): Additional authentication parameters for
            aa.Authenticate(). Defaults to {}.
        user_agent_prefix (str, optional): If set, the prefix (version-less)
            value used for setting the user-agent string. Defaults to "geemap".
        project (str, optional): The Google cloud project ID for Earth Engine.
            Defaults to None.
        kwargs (dict, optional): Additional parameters for ee.Initialize().
            For example, opt_url='https://earthengine-highvolume.googleapis.com'
            to use the Earth Engine High-Volume platform. Defaults to {}.
    """
    import google.oauth2.credentials

    # pylint: disable-next=protected-access
    if ee.data._get_state().credentials is not None:
        return

    if get_env_var("EE_SERVICE_ACCOUNT") is not None:

        key_data = get_env_var("EE_SERVICE_ACCOUNT")

        try:
            email = json.loads(key_data)["client_email"]
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON for key_data: {e}")
        except KeyError:
            raise ValueError("key_data JSON does not contain 'client_email'")
        credentials = ee.ServiceAccountCredentials(email=email, key_data=key_data)
        ee.Initialize(credentials)
        return

    ee_token = get_env_var(token_name)
    if ee_token is not None:

        stored = json.loads(ee_token)
        credentials = google.oauth2.credentials.Credentials(
            None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=stored["client_id"],
            client_secret=stored["client_secret"],
            refresh_token=stored["refresh_token"],
            quota_project_id=stored["project"],
        )

        ee.Initialize(credentials=credentials, **kwargs)
        return

    if auth_args is None:
        auth_args = {}

    if project is None:
        kwargs["project"] = get_env_var("EE_PROJECT_ID")
    else:
        kwargs["project"] = project

    if auth_mode is None:
        # pylint: disable-next=protected-access
        if ee.data._get_state().credentials is None:
            ee.Authenticate()
            ee.Initialize(**kwargs)
            return
        else:
            auth_mode = "notebook"

    auth_args["auth_mode"] = auth_mode

    ee.Authenticate(**auth_args)
    ee.Initialize(**kwargs)


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


ee_initialize()

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
def get_tile_gradio(asset_id, vis_params, start_date, end_date, bbox_str):
    """Wrapper for Gradio that converts string inputs to proper types."""
    # Convert empty strings to None
    start_date = start_date.strip() if start_date and start_date.strip() else None
    end_date = end_date.strip() if end_date and end_date.strip() else None

    # Convert bbox string to list
    bbox = None
    if bbox_str and bbox_str.strip():
        try:
            bbox = [float(x.strip()) for x in bbox_str.split(",")]
        except ValueError:
            return "Error: bbox must be comma-separated numbers (west,south,east,north)"

    return get_tile(asset_id, vis_params, start_date, end_date, bbox)


gradio_ui = gr.Interface(
    fn=get_tile_gradio,
    inputs=[
        gr.Textbox(label="Earth Engine Asset ID", placeholder="e.g., USGS/SRTMGL1_003"),
        gr.Textbox(
            label="Visualization Parameters (JSON)",
            placeholder='{"min":0,"max":5000,"palette":"terrain"}',
        ),
        gr.Textbox(
            label="Start Date (Optional)",
            placeholder="e.g., 2023-01-01",
            value="",
        ),
        gr.Textbox(
            label="End Date (Optional)",
            placeholder="e.g., 2023-12-31",
            value="",
        ),
        gr.Textbox(
            label="Bounding Box (Optional)",
            placeholder="e.g., -122.5,37.5,-122.0,38.0 (west,south,east,north)",
            value="",
        ),
    ],
    outputs="text",
    title="Earth Engine Tile URL Generator",
    description="Supports ee.Image, ee.ImageCollection, ee.FeatureCollection with optional date range and bbox filtering. Tile URL is suitable for basemap usage.",
)

app = gr.mount_gradio_app(app, gradio_ui, path="/")
