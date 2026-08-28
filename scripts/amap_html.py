"""Render the standalone official AMap JS API 2.0 map document."""

from __future__ import annotations

import json
import base64
from html import escape
from pathlib import Path
from typing import Final
from collections.abc import Mapping

from gis_data import Dataset, GisRow
from amap_config import AMapConfig
from image_store import ImageMetadata
from gis_common import SEVERITY_WEIGHT

PROBLEM_COLOR_FALLBACK: Final = "gray"
PROBLEM_COLORS: Final = {"盲道占用": "orange", "盲道破损": "red", "规划问题": "purple"}
SEVERITY_WEIGHT_FALLBACK: Final = 0.5


def _problem_color(problem_type: str) -> str:
    """Return the stable marker color for a known or custom problem type."""
    return PROBLEM_COLORS.get(problem_type, PROBLEM_COLOR_FALLBACK)


def _severity_weight(severity: str) -> float:
    """Return the stable heatmap weight for a known or custom severity."""
    return SEVERITY_WEIGHT.get(severity, SEVERITY_WEIGHT_FALLBACK)

MAP_FIELDS: Final = (
    ("编号", "id"), ("城市", "city"), ("区域", "district"), ("街道", "street"),
    ("问题类型", "problem_type"), ("子类型", "subtype"), ("严重程度", "severity"),
    ("置信度", "confidence"), ("描述", "description"), ("检测时间", "detected_at"),
    ("数据来源", "data_source"),
)


def _popup(
    row: GisRow,
    attachments: Mapping[str, tuple[ImageMetadata, ...]] | None = None,
    image_root: Path | None = None,
) -> str:
    rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(str(getattr(row, key)))}</td></tr>"
        for label, key in MAP_FIELDS
    )
    images = ""
    if attachments is not None and image_root is not None:
        image_markup = []
        for metadata in attachments.get(row.id, ()):
            path = image_root / metadata.path
            if path.exists():
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                image_markup.append(
                    f'<img src="data:{escape(metadata.content_type)};base64,{encoded}" '
                    'style="display:block;max-width:240px;max-height:180px;object-fit:contain;margin-top:6px;">'
                )
        images = "".join(image_markup)
    return f"<table>{rows}</table>{images}"


def build_amap_html(
    dataset: Dataset,
    config: AMapConfig,
    attachments: Mapping[str, tuple[ImageMetadata, ...]] | None = None,
    image_root: Path | None = None,
) -> str:
    """Build an official AMap JS 2.0 HTML document from validated rows."""
    payload = [
        {
            "id": row.id,
            "city": row.city.value,
            "longitude": row.longitude,
            "latitude": row.latitude,
                "problem_type": row.problem_type,
                "subtype": row.subtype,
            "severity": row.severity,
            "color": _problem_color(row.problem_type),
            "weight": _severity_weight(row.severity),
            "popup": _popup(row, attachments, image_root),
        }
        for row in dataset.rows
    ]
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    safe_key = escape(config.js_key, quote=True)
    security = f"window._AMapSecurityConfig={{securityJsCode:{json.dumps(config.security_js_code)}}};"
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>盲道问题GIS标注图</title>
<style>
html,body,#amap-map{{width:100%;height:100%;margin:0}}
table{{border-collapse:collapse;font:13px sans-serif}}
th,td{{padding:2px 8px;text-align:left;vertical-align:top}}
th{{color:#5a6b7b;white-space:nowrap}}
.gis-pin{{position:relative;width:24px;height:24px;border:2px solid #fff;border-radius:50% 50% 50% 0;box-sizing:border-box;box-shadow:0 2px 5px rgba(15,23,42,.35);transform:rotate(-45deg);}}
.gis-pin-dot{{position:absolute;left:6px;top:6px;width:8px;height:8px;border-radius:50%;background:#fff;}}
.gis-cluster{{display:flex;align-items:center;justify-content:center;width:34px;height:34px;border:2px solid #fff;border-radius:50%;box-sizing:border-box;background:#0f766e;color:#fff;font:700 12px/1 Arial,sans-serif;box-shadow:0 2px 6px rgba(15,23,42,.35);}}
</style>
<script>{security}</script>
<script src="https://webapi.amap.com/maps?v=2.0&key={safe_key}&plugin=AMap.MarkerCluster,AMap.HeatMap,AMap.ToolBar,AMap.Scale,AMap.MapType"></script>
</head><body><div id="amap-map"></div><script>
const AMAP_DATA={payload_json};
window.__AMAP_READY__=false; window.__AMAP_ERROR__=null;
try {{
  const map=new AMap.Map('amap-map',{{zoom:11,center:[101.778,36.617]}}); window.__AMAP_MAP__=map;
  map.addControl(new AMap.ToolBar()); map.addControl(new AMap.Scale()); map.addControl(new AMap.MapType());
   const clusterData=AMAP_DATA.map(item=>({{lnglat:[item.longitude,item.latitude],weight:item.weight,data:item}})); window.__AMAP_DATA__=clusterData;
   const cluster=new AMap.MarkerCluster(map,clusterData,{{gridSize:60,maxZoom:18,zoomOnClick:true,averageCenter:true,
     renderClusterMarker:context=>{{const count=Number(context.count||0); context.marker.setContent(`<div class="gis-cluster" title="${{count}} 个点位">${{count}}</div>`); context.marker.setAnchor('center');}},
     renderMarker:context=>{{const item=Array.isArray(context.data)?context.data[0]?.data:context.data?.data??context.data; if(item?.color){{context.marker.setContent(`<div class="gis-pin" style="background:${{item.color}}" title="${{item.problem_type||'问题点位'}}"><span class="gis-pin-dot"></span></div>`); context.marker.setAnchor('bottom-center');}} if(item?.popup){{context.marker.setTitle(item.problem_type); context.marker.on('click',()=>new AMap.InfoWindow({{content:item.popup,offset:[0,-30]}}).open(map,context.marker.getPosition()));}}}}}}); window.__AMAP_CLUSTER__=cluster;
   if (AMAP_DATA.length === 1) {{
     map.setZoomAndCenter(15,[AMAP_DATA[0].longitude,AMAP_DATA[0].latitude],true);
   }} else if (AMAP_DATA.length > 1) {{
     const longitudes=AMAP_DATA.map(item=>item.longitude); const latitudes=AMAP_DATA.map(item=>item.latitude);
     const bounds=new AMap.Bounds([Math.min(...longitudes),Math.min(...latitudes)],[Math.max(...longitudes),Math.max(...latitudes)]);
     map.setBounds(bounds,true,[80,80,80,80]);
     if (map.getZoom() > 16) map.setZoom(16,true);
   }}
  const heatmap=new AMap.HeatMap(map,{{radius:25,opacity:[0,0.8]}}); heatmap.setDataSet({{data:AMAP_DATA.map(item=>({{lng:item.longitude,lat:item.latitude,count:item.weight}})),max:1}}); heatmap.hide(); window.__AMAP_HEATMAP__=heatmap;
   window.__setExportView=(city)=>{{const views={{'西宁':[101.778,36.617],'格尔木':[94.903,36.407]}}; const view=views[city]; if(!view) throw new Error('Unknown city'); map.setZoomAndCenter(13,view);}}; window.__AMAP_READY__=true;
}} catch (error) {{ window.__AMAP_ERROR__=String(error); }}
</script></body></html>'''
