"""Python script for Garages Amsterdam data."""

from odp_amsterdam import Garage, ODPAmsterdam

from app.cities import City


class Municipality(City):
    """Manage the location data of Amsterdam."""

    def __init__(self) -> None:
        """Initialize the class."""
        super().__init__(
            name="Amsterdam",
            country="Netherlands",
        )

    async def async_get_locations(self) -> list[Garage]:
        """Get garage data from API.

        Returns
        -------
            list: List of garages.

        """
        async with ODPAmsterdam() as client:
            garages: list[Garage] = await client.all_garages()
            print(f"{self.name} - data has been retrieved")
            return garages
