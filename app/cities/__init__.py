"""General class for cities."""


class City:
    """General class for cities."""

    def __init__(  # noqa: PLR0913
        self,
        name: str,
        country: str,
        country_id: int,
        province_id: int,
        geo_code: str,
        phone_code: str,
    ) -> None:
        """Initialize the class."""
        self.name = name
        self.country = country
        self.country_id = country_id
        self.province_id = province_id
        self.geo_code = geo_code
        self.phone_code = phone_code
