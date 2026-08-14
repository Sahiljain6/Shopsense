import base64

import httpx

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"


def identify_image(image_bytes: bytes, api_key: str) -> list[str]:
    """Send image bytes to Google Cloud Vision, return a ranked list of
    descriptive labels/entities (web entities first — they tend to be more
    specific product/brand names — then general labels). Raises httpx.HTTPError
    on failure; caller is responsible for turning that into a friendly error."""

    encoded = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "requests": [{
            "image": {"content": encoded},
            "features": [
                {"type": "WEB_DETECTION", "maxResults": 6},
                {"type": "LABEL_DETECTION", "maxResults": 8}
            ]
        }]
    }

    with httpx.Client(timeout=15) as client:
        response = client.post(
            VISION_ENDPOINT,
            params={"key": api_key},
            json=payload
        )
        response.raise_for_status()

    data = response.json()
    result = (data.get("responses") or [{}])[0]

    web_entities = [
        entity.get("description")
        for entity in result.get("webDetection", {}).get("webEntities", [])
        if entity.get("description")
    ]

    labels = [
        annotation.get("description")
        for annotation in result.get("labelAnnotations", [])
        if annotation.get("description")
    ]

    combined: list[str] = []
    for item in web_entities + labels:
        if item and item not in combined:
            combined.append(item)

    return combined
