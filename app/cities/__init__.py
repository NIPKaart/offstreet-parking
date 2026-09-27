"""General class for cities."""


class City:
    """General class for cities."""

    def __init__(
        self,
        name: str,
        country: str,
    ) -> None:
        """Initialize the class."""
        self.name = name
        self.country = country
