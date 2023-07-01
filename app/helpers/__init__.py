"""Helper functions for the app."""


def test_data(data_set: list) -> None:
    """Test the data.

    Args:
    ----
        data_set (list): List of data.
    """
    count: int
    for index, item in enumerate(data_set, 1):
        count = index
        print(item)
    print(f"{count} parkeergarages gevonden")


def get_unique_number(lat: float, lon: float) -> int:
    """Generate a unique number for the location.

    Args:
    ----
        lat (float): The latitude of the location.
        lon (float): The longitude of the location.

    Returns:
    -------
        int: The unique number.
    """
    try:
        lat_int = int(lat * 1e7)
        lon_int = int(lon * 1e7)

        val = abs((lat_int << 16 & 0xFFFF0000) | (lon_int & 0x0000FFFF))
        return val % 2147483647
    except Exception as error:  # noqa: BLE001
        print(f"Error: {error}")
        print(
            f"Error: {error} - lat: {lat} - lon: {lon} - lat_int: {lat_int} - lon_int: {lon_int}",  # noqa: E501
        )
    return None
