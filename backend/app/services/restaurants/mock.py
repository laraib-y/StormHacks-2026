from app.schemas.ai import DinnerIntent
from app.schemas.restaurant import RestaurantCandidate
from app.services.restaurants.base import RestaurantProvider

TARGET_COUNT = 12

# Stable catalog so a session can be created with no external API key.
_CATALOG: list[dict] = [
    {
        "external_id": "mock-kinjo-sushi",
        "name": "Kinjo Sushi",
        "cuisine": "Japanese",
        "price": 2,
        "rating": 4.6,
        "description": "Neighborhood sushi counter with a short menu and a casual room.",
        "street": "4500 Kingsway",
    },
    {
        "external_id": "mock-han-river-bbq",
        "name": "Han River BBQ",
        "cuisine": "Korean",
        "price": 2,
        "rating": 4.7,
        "description": "Tabletop grills, banchan, and plenty of space for a group.",
        "street": "1880 Willingdon Ave",
    },
    {
        "external_id": "mock-seoul-night",
        "name": "Seoul Night Kitchen",
        "cuisine": "Korean",
        "price": 2,
        "rating": 4.4,
        "description": "Late bowls, fried chicken, and a lively but unfussy dining room.",
        "street": "4700 Kingsway",
    },
    {
        "external_id": "mock-maple-izakaya",
        "name": "Maple Izakaya",
        "cuisine": "Japanese",
        "price": 2,
        "rating": 4.5,
        "description": "Small plates, skewers, and a relaxed weeknight feel.",
        "street": "329 North Rd",
    },
    {
        "external_id": "mock-little-olive",
        "name": "Little Olive",
        "cuisine": "Mediterranean",
        "price": 2,
        "rating": 4.3,
        "description": "Mezze to share, warm lighting, and an easy group table.",
        "street": "6288 Kingsway",
    },
    {
        "external_id": "mock-cedar-noodle",
        "name": "Cedar Noodle Bar",
        "cuisine": "Chinese",
        "price": 1,
        "rating": 4.2,
        "description": "Hand-pulled noodles and a quick, casual counter.",
        "street": "1601 Burnaby Heights",
    },
    {
        "external_id": "mock-north-shore-tacos",
        "name": "North Shore Tacos",
        "cuisine": "Mexican",
        "price": 1,
        "rating": 4.4,
        "description": "Weekend-style tacos and a patio that works for a crowd.",
        "street": "4125 Hastings St",
    },
    {
        "external_id": "mock-basil-brick",
        "name": "Basil & Brick",
        "cuisine": "Thai",
        "price": 2,
        "rating": 4.5,
        "description": "Curries, salads, and a bright room that stays comfortable.",
        "street": "5055 Canada Way",
    },
    {
        "external_id": "mock-harbor-grill",
        "name": "Harbor Grill",
        "cuisine": "American",
        "price": 3,
        "rating": 4.1,
        "description": "A slightly dressier grill with booths big enough to linger.",
        "street": "7888 6th St",
    },
    {
        "external_id": "mock-pasta-lane",
        "name": "Pasta Lane",
        "cuisine": "Italian",
        "price": 2,
        "rating": 4.3,
        "description": "Fresh pasta, a short wine list, and a friendly noise level.",
        "street": "2500 Boundary Rd",
    },
    {
        "external_id": "mock-spice-route",
        "name": "Spice Route",
        "cuisine": "Indian",
        "price": 2,
        "rating": 4.6,
        "description": "Family-style curries and breads meant to be passed around.",
        "street": "5901 Kingsway",
    },
    {
        "external_id": "mock-pho-lantern",
        "name": "Pho Lantern",
        "cuisine": "Vietnamese",
        "price": 1,
        "rating": 4.7,
        "description": "Steaming bowls, herbs on the side, and a no-fuss welcome.",
        "street": "3180 Grand Promenade",
    },
    {
        "external_id": "mock-green-bowl",
        "name": "Green Bowl",
        "cuisine": "Vegetarian",
        "price": 2,
        "rating": 4.2,
        "description": "Grain bowls and a calm room when the group wants something lighter.",
        "street": "4220 Hastings St",
    },
    {
        "external_id": "mock-copper-pot",
        "name": "The Copper Pot",
        "cuisine": "French",
        "price": 4,
        "rating": 4.8,
        "description": "A slower, dressier dinner if the table decides to celebrate.",
        "street": "6100 McKay Ave",
    },
    {
        "external_id": "mock-burger-club",
        "name": "Burnaby Burger Club",
        "cuisine": "Burgers",
        "price": 1,
        "rating": 4.0,
        "description": "Smash burgers and a casual booth when nobody wants to dress up.",
        "street": "1020 Austin Ave",
    },
]


class MockRestaurantProvider(RestaurantProvider):
    """Returns a curated deck so the product works with no Geoapify key."""

    def search(self, intent: DinnerIntent) -> list[RestaurantCandidate]:
        selected = _select(intent)
        location = intent.location or "Vancouver"
        origin_lat = 49.2488
        origin_lon = -122.9805
        restaurants: list[RestaurantCandidate] = []
        for index, item in enumerate(selected):
            description = item["description"]
            if intent.vibe and intent.vibe.lower() not in description.lower():
                description = f"{description} Fits a {intent.vibe} night."
            restaurants.append(
                RestaurantCandidate(
                    external_id=item["external_id"],
                    name=item["name"],
                    description=description,
                    cuisine=item["cuisine"],
                    price=item["price"],
                    rating=item["rating"],
                    latitude=round(origin_lat + (index - 6) * 0.004, 6),
                    longitude=round(origin_lon + ((index % 4) - 1.5) * 0.005, 6),
                    address=f"{item['street']}, {location}",
                    image_url=None,
                    source="mock",
                )
            )
        return restaurants


def _select(intent: DinnerIntent) -> list[dict]:
    requested = {cuisine.lower() for cuisine in intent.cuisines}

    def cuisine_rank(item: dict) -> int:
        if not requested:
            return 0
        name = item["cuisine"].lower()
        return 0 if any(cuisine in name or name in cuisine for cuisine in requested) else 1

    def price_rank(item: dict) -> int:
        if intent.price_level is None:
            return 0
        return 0 if item["price"] <= intent.price_level else 1

    ordered = sorted(_CATALOG, key=lambda item: (cuisine_rank(item), price_rank(item), -item["rating"]))
    return ordered[:TARGET_COUNT]
