"""
Travel time estimation.

MVP uses the Haversine formula (straight-line distance) multiplied by a
road factor to approximate real driving distance. This is accurate enough
for scheduling purposes and requires no external API.

To upgrade to Google Maps: set TRAVEL_PROVIDER=google_maps in .env and
implement get_travel_minutes_google() below. The rest of the codebase
calls get_travel_minutes() and never needs to change.
"""
import math
from app.core.config import settings


def haversine_distance_km(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Straight-line distance between two GPS points in kilometers."""
    R = 6371.0  # Earth's mean radius in km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_travel_minutes(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    avg_speed_kmh: float = 40.0,
    road_factor: float = 1.3,
) -> int:
    """
    Estimate driving time in minutes between two coordinates.

    road_factor: Roads are typically 30% longer than straight-line distance.
    avg_speed_kmh: Conservative urban average including traffic stops.

    Tune per company:
      Dense city (NYC):   road_factor=1.5, speed=25
      Suburban (Dallas):  road_factor=1.3, speed=40
      Rural:              road_factor=1.15, speed=65
    """
    if (from_lat, from_lon) == (to_lat, to_lon):
        return 0

    straight_km = haversine_distance_km(from_lat, from_lon, to_lat, to_lon)
    road_km = straight_km * road_factor
    hours = road_km / avg_speed_kmh

    return max(1, round(hours * 60))


def travel_delta_minutes(
    prev_lat: float,
    prev_lon: float,
    new_lat: float,
    new_lon: float,
    next_lat: float | None,
    next_lon: float | None,
    avg_speed_kmh: float = 40.0,
    road_factor: float = 1.3,
) -> int:
    """
    Extra driving time added by inserting a new stop between prev and next.

    If inserting at the end of the route (next is None), returns travel time
    to the new stop only. Otherwise returns the net extra time:
      travel(prev→new) + travel(new→next) - travel(prev→next)
    A negative result means the insertion actually shortens the route.
    """
    to_new = get_travel_minutes(prev_lat, prev_lon, new_lat, new_lon, avg_speed_kmh, road_factor)

    if next_lat is None or next_lon is None:
        return to_new

    from_new = get_travel_minutes(new_lat, new_lon, next_lat, next_lon, avg_speed_kmh, road_factor)
    direct = get_travel_minutes(prev_lat, prev_lon, next_lat, next_lon, avg_speed_kmh, road_factor)

    return to_new + from_new - direct
