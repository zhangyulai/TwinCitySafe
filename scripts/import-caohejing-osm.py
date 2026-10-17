#!/usr/bin/env python3
"""Turn the checked-in public OSM extract into the local GIS feature collection.

The application only consumes the generated GeoJSON.  Keeping the OSM XML and
this converter in the repository makes the competition demo reproducible and
keeps the source attribution with the data.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/public/gis/caohejing-keji-oasis.osm"
TARGET = ROOT / "frontend/public/gis/caohejing-keji-oasis.geojson"


def tags(item: ET.Element) -> dict[str, str]:
    return {tag.attrib["k"]: tag.attrib["v"] for tag in item.findall("tag")}


def feature(geometry: dict, properties: dict) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def main() -> None:
    root = ET.parse(SOURCE).getroot()
    points = {
        item.attrib["id"]: (float(item.attrib["lon"]), float(item.attrib["lat"]))
        for item in root.findall("node")
    }
    features: list[dict] = []

    for item in root.findall("node"):
        item_tags = tags(item)
        if "entrance" not in item_tags:
            continue
        properties = {
            "layer": "entrances",
            "name": item_tags.get("name", "园区出入口"),
            "entrance": item_tags.get("entrance"),
            "osmId": item.attrib["id"],
        }
        features.append(feature({"type": "Point", "coordinates": points[item.attrib["id"]]}, properties))

    for item in root.findall("way"):
        item_tags = tags(item)
        coordinates = [points[ref.attrib["ref"]] for ref in item.findall("nd") if ref.attrib["ref"] in points]
        if len(coordinates) < 2:
            continue
        closed = coordinates[0] == coordinates[-1]
        layer: str | None = None
        if "building" in item_tags:
            layer = "buildings"
        elif "highway" in item_tags:
            layer = "roads"
        elif item_tags.get("natural") == "water" or "waterway" in item_tags:
            layer = "water"
        elif item_tags.get("landuse") in {"grass", "recreation_ground", "meadow", "village_green"} or item_tags.get("leisure") in {"park", "garden"}:
            layer = "green"
        elif "amenity" in item_tags and closed:
            layer = "amenities"
        if layer is None:
            continue
        geometry = {"type": "Polygon", "coordinates": [coordinates]} if closed else {"type": "LineString", "coordinates": coordinates}
        properties = {
            "layer": layer,
            "name": item_tags.get("name") or item_tags.get("name:zh") or ("园区建筑" if layer == "buildings" else "未命名要素"),
            "osmId": item.attrib["id"],
            "building": item_tags.get("building"),
            "highway": item_tags.get("highway"),
            "levels": item_tags.get("building:levels"),
            "height": item_tags.get("height"),
            "surface": item_tags.get("surface"),
        }
        features.append(feature(geometry, {key: value for key, value in properties.items() if value is not None}))

    collection = {
        "type": "FeatureCollection",
        "name": "caohejing-keji-oasis-public-basemap",
        "metadata": {
            "title": "漕河泾科技绿洲公开 GIS 基础图层",
            "crs": "EPSG:4326",
            "source": "OpenStreetMap contributors",
            "license": "ODbL 1.0",
            "sourceUrl": "https://www.openstreetmap.org/copyright",
            "sourceRelation": "16531277",
            "extent": [121.3789, 31.1590, 121.3896, 31.1708],
            "retrievedAt": "2026-10-10",
            "notice": "建筑、道路、绿地和水体来自公开地图；设备、地下管网与事故数据仍为项目仿真资产，不能当作园区实测数据。",
        },
        "features": features,
    }
    TARGET.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts: dict[str, int] = {}
    for item in features:
        layer = item["properties"]["layer"]
        counts[layer] = counts.get(layer, 0) + 1
    print(f"Wrote {TARGET.relative_to(ROOT)}: {counts}")


if __name__ == "__main__":
    main()
