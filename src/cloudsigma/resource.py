class BurstUsage(ResourceBase):
    resource_name = 'burstusage'
    """
    Burst Usage Resource.

    This class provides methods to interact with the /burstusage/ API endpoint.
    It inherits common functionalities from ResourceBase for listing objects.
    """
    # The base ResourceBase.list() method already handles GET /burstusage/
    # and supports filtering via `query_params` (e.g., date__gte, date__lt).
    # No custom methods are needed based on the provided HTML.


class DailyBurstUsage(ResourceBase):
    resource_name = 'dailyburstusage'
    """
    Daily Burst Usage Resource.

    This class provides methods to interact with the /dailyburstusage/ API endpoint.
    It inherits common functionalities from ResourceBase for listing objects.
    """
    # Similar to BurstUsage, the base ResourceBase.list() method handles
    # GET /dailyburstusage/ and supports filtering by date via `query_params`.
    # No custom methods are needed based on the provided HTML.
