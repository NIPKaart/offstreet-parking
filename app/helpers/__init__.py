"""Helper functions for the app."""


def test_data(data_set):
    """Test the data.

    Args:
        data_set (list): List of data.
    """
    count: int
    for index, item in enumerate(data_set, 1):
        count = index
        print(item)
    print(f"{count} parkeergarages gevonden")


def get_unique_number(lat, lon):
    """Generate a unique number for the location.

    Args:
        lat (float): The latitude of the location.
        lon (float): The longitude of the location.

    Returns:
        int: The unique number.
    """
    try:
        lat_int = int((lat * 1e7))
        lon_int = int((lon * 1e7))

        val = abs((lat_int << 16 & 0xFFFF0000) | (lon_int & 0x0000FFFF))
        val = val % 2147483647
        return val
    except Exception as error:
        print(f"Error: {error}")
        print(
            "marking OD_LOC_ID as -1 getting exception inside get_unique_number function"
        )
    return None
