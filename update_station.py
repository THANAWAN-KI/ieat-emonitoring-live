import json
import sys
from pathlib import Path
from typing import Any

import requests


SOURCE_URL = (
    "https://emonitor.ieat.go.th/"
    "call_feed/geog/GeoData/station_all.json"
)

OUTPUT_FILE = Path("station.geojson")
TIMEOUT = 90


def safe_number(value: Any) -> float | None:
    """แปลงค่าเป็นตัวเลข และเปลี่ยน 9999 เป็น null."""
    if value in (None, "", "-", "null"):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number == 9999:
        return None

    return number


def safe_text(value: Any) -> str | None:
    """แปลงค่าเป็นข้อความ โดยตัดค่าว่างออก."""
    if value in (None, "", "-"):
        return None

    return str(value).strip()


def download_source() -> dict[str, Any]:
    print(f"Downloading: {SOURCE_URL}")

    response = requests.get(
        SOURCE_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "IEAT-GeoJSON-Updater/1.0",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("type") != "FeatureCollection":
        raise RuntimeError(
            "ข้อมูลต้นทางไม่ใช่ GeoJSON FeatureCollection"
        )

    features = data.get("features")

    if not isinstance(features, list):
        raise RuntimeError("ไม่พบรายการ features")

    if not features:
        raise RuntimeError("ข้อมูลต้นทางไม่มี Feature")

    return data


def clean_feature(
    feature: dict[str, Any],
) -> dict[str, Any] | None:
    geometry = feature.get("geometry") or {}
    properties = feature.get("properties") or {}

    if geometry.get("type") != "Point":
        return None

    coordinates = geometry.get("coordinates")

    if (
        not isinstance(coordinates, list)
        or len(coordinates) < 2
    ):
        return None

    try:
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
    except (TypeError, ValueError):
        return None

    if not (-180 <= longitude <= 180):
        return None

    if not (-90 <= latitude <= 90):
        return None

    code = safe_text(properties.get("Code"))
    station_th = safe_text(properties.get("StationTH"))
    station_en = safe_text(properties.get("StationEN"))
    station_short = safe_text(
        properties.get("StationShort")
    )

    # ตัดรายการประกอบที่ไม่ใช่สถานีจริง
    if code in (None, "0"):
        return None

    if not any((station_th, station_en, station_short)):
        return None

    # เลือกเฉพาะฟิลด์ที่จำเป็นและใช้ชื่อที่ ArcGIS รองรับ
    cleaned_properties = {
        "Code": code,
        "StationShort": station_short,
        "StationTH": station_th,
        "StationEN": station_en,
        "IndustryZone": safe_text(
            properties.get("IndustryZone")
        ),
        "Zone": safe_text(properties.get("Zone")),
        "StationType": safe_text(
            properties.get("Type")
        ),
        "TimeBase": safe_text(
            properties.get("TimeBase")
        ),
        "LastUpdate": safe_text(
            properties.get("LastUpdate")
        ),
        "LastUpdate_TH": safe_text(
            properties.get("LastUpdate-TH")
        ),
        "LastUpdate_EN": safe_text(
            properties.get("LastUpdate-EN")
        ),
        "StationActive": safe_text(
            properties.get("StationActive")
        ),
        "Status": safe_text(properties.get("Status")),
        "Comment": safe_text(
            properties.get("Comment")
        ),
        "GroupCode": safe_text(
            properties.get("Group")
        ),

        # ข้อมูลอุตุนิยมวิทยา
        "WD": safe_number(properties.get("WD")),
        "WS": safe_number(properties.get("WS")),
        "TEMP": safe_number(
            properties.get(
                "TEMP",
                properties.get("Temp"),
            )
        ),
        "RH": safe_number(properties.get("RH")),
        "BP": safe_number(properties.get("BP")),
        "RAIN": safe_number(properties.get("RAIN")),
        "SRAD": safe_number(properties.get("SRAD")),

        # ข้อมูลคุณภาพอากาศ
        "PM25": safe_number(properties.get("PM25")),
        "PM10": safe_number(properties.get("PM10")),
        "TSP": safe_number(properties.get("TSP")),
        "SO2": safe_number(properties.get("SO2")),
        "NO2": safe_number(properties.get("NO2")),
        "NOx": safe_number(properties.get("NOx")),
        "NO": safe_number(properties.get("NO")),
        "CO": safe_number(properties.get("CO")),
        "AQI": safe_number(properties.get("AQI")),
        "H2S": safe_number(properties.get("H2S")),
        "CH4": safe_number(properties.get("CH4")),
        "NMHC": safe_number(properties.get("NMHC")),
        "THC": safe_number(properties.get("THC")),
    }

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                longitude,
                latitude,
            ],
        },
        "properties": cleaned_properties,
    }


def main() -> None:
    source = download_source()

    output_features = []

    for feature in source["features"]:
        cleaned = clean_feature(feature)

        if cleaned is not None:
            output_features.append(cleaned)

    if not output_features:
        raise RuntimeError(
            "ไม่เหลือสถานีหลังการตรวจสอบข้อมูล"
        )

    output = {
        "type": "FeatureCollection",
        "name": "IEAT_eMonitoring",
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
            },
        },
        "features": output_features,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Created {OUTPUT_FILE} "
        f"with {len(output_features)} stations."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"UPDATE FAILED: {error}", file=sys.stderr)
        sys.exit(1)
