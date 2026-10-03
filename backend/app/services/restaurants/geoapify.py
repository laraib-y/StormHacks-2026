import logging

import httpx

from app.schemas.ai import DinnerIntent
from app.schemas.restaurant import RestaurantCandidate
from app.services.restaurants.base import RestaurantProvider
from app.services.restaurants.mock import MockRestaurantProvider

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
PLACES_URL = "https://api.geoapify.com/v2/places"
MIN_RESULTS = 10
MAX_RESULTS = 15

_CATEGORY_BY_CUISINE = {
    "japanese": "catering.restaurant.japanese",
    "korean": "catering.restaurant.korean",
    "chinese": "catering.restaurant.chinese",
    "italian": "catering.restaurant.italian",
    "indian": "catering.restaurant.indian",
    "thai": "catering.restaurant.thai",
    "mexican": "catering.restaurant.mexican",
    "vietnamese": "catering.restaurant.vietnamese",
    "pizza": "catering.restaurant.pizza",
    "burgers": "catering.restaurant.burger",
    "burger": "catering.restaurant.burger",
    "seafood": "catering.restaurant.seafood",
    "french": "catering.restaurant.french",
    "greek": "catering.restaurant.greek",
    "american": "catering.restaurant.american",
}

_CUISINE_LABELS = {
    "japanese": "Japanese",
    "sushi": "Japanese",
    "korean": "Korean",
    "chinese": "Chinese",
    "italian": "Italian",
    "pizza": "Pizza",
    "indian": "Indian",
    "thai": "Thai",
    "mexican": "Mexican",
    "vietnamese": "Vietnamese",
    "burger": "Burgers",
    "seafood": "Seafood",
    "french": "French",
    "greek": "Greek",
    "american": "American",
    "barbecue": "Barbecue",
    "steak": "Steakhouse",
    "mediterranean": "Mediterranean",
    "asian": "Asian",
}


class GeoapifyRestaurantProvider(RestaurantProvider):
    """Loads one restaurant deck from Geoapify and falls back to mock data."""

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        fallback: RestaurantProvider | None = None,
    ) -> None:
        self.api_key = api_key
        self._client = client
        self.fallback = fallback or MockRestaurantProvider()

    def search(self, intent: DinnerIntent) -> list[RestaurantCandidate]:
        try:
            found = self._search_live(intent)
        except Exception as exc:
            logger.warning("Geoapify request failed (%s). Using mock restaurants.", exc)
            found = []

        if len(found) >= MIN_RESULTS:
            return found[:MAX_RESULTS]

        padded = _pad(found, self.fallback.search(intent))
        if len(padded) >= MIN_RESULTS:
            return padded[:MAX_RESULTS]
        return self.fallback.search(intent)[:MAX_RESULTS]

    def _search_live(self, intent: DinnerIntent) -> list[RestaurantCandidate]:
        if not self.api_key.strip():
            raise RuntimeError("GEOAPIFY_API_KEY is not configured")

        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=8.0)
        try:
            latitude, longitude = self._geocode(client, intent.location or "Vancouver")
            categories = _categories(intent)
            features = self._places(client, latitude, longitude, intent.radius, categories)
            if len(features) < MIN_RESULTS and categories != "catering.restaurant":
                general = self._places(client, latitude, longitude, intent.radius, "catering.restaurant")
                features = _merge_features(features, general)
        finally:
            if owns_client:
                client.close()

        restaurants: list[RestaurantCandidate] = []
        seen: set[str] = set()
        for feature in features:
            candidate = normalize_geoapify_feature(feature)
            if candidate is None or candidate.external_id in seen:
                continue
            seen.add(candidate.external_id)
            restaurants.append(candidate)
            if len(restaurants) >= MAX_RESULTS:
                break
        return restaurants

    def _geocode(self, client: httpx.Client, location: str) -> tuple[float, float]:
        response = client.get(
            GEOCODE_URL,
            params={"text": location, "limit": 1, "format": "json", "apiKey": self.api_key},
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            raise RuntimeError(f"No geocoding result for {location}")
        return float(results[0]["lat"]), float(results[0]["lon"])

    def _places(
        self,
        client: httpx.Client,
        latitude: float,
        longitude: float,
        radius: int,
        categories: str,
    ) -> list[dict]:
        response = client.get(
            PLACES_URL,
            params={
                "categories": categories,
                "filter": f"circle:{longitude},{latitude},{radius}",
                "bias": f"proximity:{longitude},{latitude}",
                "limit": MAX_RESULTS,
                "apiKey": self.api_key,
            },
        )
        response.raise_for_status()
        features = response.json().get("features") or []
        if not isinstance(features, list):
            raise RuntimeError("Geoapify places response was not a feature list")
        return features


def normalize_geoapify_feature(feature: dict) -> RestaurantCandidate | None:
    """Map one Geoapify feature into the internal restaurant model."""

    properties = feature.get("properties") or {}
    name = properties.get("name") or properties.get("address_line1")
    if not isinstance(name, str) or not name.strip():
        return None

    latitude = _float_or_none(properties.get("lat"))
    longitude = _float_or_none(properties.get("lon"))
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if (latitude is None or longitude is None) and isinstance(coordinates, list) and len(coordinates) >= 2:
        longitude = longitude if longitude is not None else _float_or_none(coordinates[0])
        latitude = latitude if latitude is not None else _float_or_none(coordinates[1])

    raw = {}
    datasource = properties.get("datasource")
    if isinstance(datasource, dict) and isinstance(datasource.get("raw"), dict):
        raw = datasource["raw"]

    categories = properties.get("categories") if isinstance(properties.get("categories"), list) else []
    place_id = properties.get("place_id") or f"{name}:{latitude}:{longitude}"
    address = properties.get("formatted") or properties.get("address_line2")

    return RestaurantCandidate(
        external_id=str(place_id)[:128],
        name=name.strip()[:160],
        description=_description(properties, categories),
        cuisine=_cuisine(categories),
        price=_price(raw),
        rating=_rating(raw.get("rating", properties.get("rating"))),
        latitude=latitude,
        longitude=longitude,
        address=str(address)[:255] if address else None,
        image_url=_image_url(properties.get("image") or raw.get("image")),
        source="geoapify",
    )


def _categories(intent: DinnerIntent) -> str:
    found: list[str] = []
    for cuisine in intent.cuisines:
        category = _CATEGORY_BY_CUISINE.get(cuisine.lower())
        if category and category not in found:
            found.append(category)
    if not found:
        return "catering.restaurant"
    return ",".join(found)


def _cuisine(categories: list) -> str | None:
    for category in categories:
        if not isinstance(category, str):
            continue
        tail = category.split(".")[-1].replace("_", " ").lower()
        for keyword, label in _CUISINE_LABELS.items():
            if keyword in tail:
                return label
    return "Restaurant"


def _description(properties: dict, categories: list) -> str | None:
    for key in ("description", "operator", "website"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip() and not value.startswith("http"):
            return value.strip()[:500]
    if categories:
        readable = ", ".join(
            str(category).split(".")[-1].replace("_", " ")
            for category in categories
            if isinstance(category, str)
        )
        if readable:
            return f"Listed as {readable}."
    return None


def _price(raw: dict) -> int | None:
    value = raw.get("price_level")
    try:
        price = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= price <= 4:
        return price
    return None


def _rating(value: object) -> float | None:
    try:
        rating = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if 0 <= rating <= 5:
        return round(rating, 2)
    return None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith("https://") or value.startswith("http://"):
        return value[:512]
    return None


def _merge_features(primary: list[dict], extra: list[dict]) -> list[dict]:
    merged = list(primary)
    seen = {((item.get("properties") or {}).get("place_id")) for item in primary}
    for item in extra:
        place_id = (item.get("properties") or {}).get("place_id")
        if place_id in seen:
            continue
        seen.add(place_id)
        merged.append(item)
    return merged


def _pad(primary: list[RestaurantCandidate], backup: list[RestaurantCandidate]) -> list[RestaurantCandidate]:
    names = {item.name.lower() for item in primary}
    combined = list(primary)
    for item in backup:
        if item.name.lower() in names:
            continue
        names.add(item.name.lower())
        combined.append(item)
        if len(combined) >= TARGET_PAD:
            break
    return combined


TARGET_PAD = 12
