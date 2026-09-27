"""Python script for Park and Ride Hamburg data."""

from hamburg import ParkAndRide, UDPHamburg

from app.cities import City


class Municipality(City):
    """Manage the location data of Hamburg."""

    def __init__(self) -> None:
        """Initialize the class."""
        super().__init__(
            name="Hamburg",
            country="Germany",
        )
        self.limit = 40

    async def async_get_locations(self) -> list[ParkAndRide]:
        """Get parking data from API.

        Args:
        ----
            limit (int): Number of garages to retrieve.

        """
        async with UDPHamburg() as client:
            parking: list[ParkAndRide] = await client.park_and_rides(limit=self.limit)
            print(f"{self.name} - data has been retrieved")
            return parking
