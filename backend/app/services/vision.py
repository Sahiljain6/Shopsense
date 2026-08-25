import base64
import httpx

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
FREE_HF_VISION_ENDPOINT = "https://api-inference.huggingface.co/models/google/vit-base-patch16-224"
FREE_HF_BLIP_ENDPOINT = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"


def identify_image_free(image_bytes: bytes) -> list[str]:
    """100% Free image identification using Hugging Face's open vision models (0 API key required)."""
    try:
        # 1. Try free ViT image classifier
        with httpx.Client(timeout=10) as client:
            resp = client.post(FREE_HF_VISION_ENDPOINT, content=image_bytes)
            if resp.status_code == 200:
                results = resp.json()
                if isinstance(results, list):
                    labels = [item.get("label") for item in results if item.get("label")]
                    if labels:
                        clean_labels = [l.split(",")[0].strip() for l in labels[:5]]
                        return clean_labels

        # 2. Try free BLIP image captioner
        with httpx.Client(timeout=10) as client:
            resp = client.post(FREE_HF_BLIP_ENDPOINT, content=image_bytes)
            if resp.status_code == 200:
                results = resp.json()
                if isinstance(results, list) and len(results) > 0:
                    caption = results[0].get("generated_text", "")
                    if caption:
                        words = [w.strip() for w in caption.split() if len(w) > 3]
                        return words[:5]
    except Exception as error:
        print(f"Free Hugging Face Vision API notice: {error}")

    return ["product", "item", "gadget"]


def identify_image(image_bytes: bytes, api_key: str | None = None) -> list[str]:
    """Identify image tags using Google Cloud Vision if key is provided,
    or 100% free Hugging Face Open Vision models if key is missing/blank.
    """
    if api_key and api_key.strip():
        try:
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

            if combined:
                return combined
        except Exception as error:
            print(f"Google Vision API fallback to free vision: {error}")

    # 100% Free fallback when no Google API Key is provided
    return identify_image_free(image_bytes)
