<code lang="python">
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


class CurrentUsage(ResourceBase):
    """
    Manages current usage information for the authenticated user.
    """
    resource_name = 'currentusage'

    # The HTML documentation only specifies a GET operation for '/currentusage/'.
    # This endpoint returns a single dictionary representing the user's current usage,
    # not a list of objects and not an object identified by a UUID in the URL path.
    #
    # The inherited ResourceBase.get(uuid=None) method already handles requests
    # to the base resource URL (e.g., /currentusage/) and expects a single
    # object (return_list=False). This perfectly matches the API behavior for
    # retrieving current usage.
    #
    # Therefore, no explicit 'get' or 'list' method override is necessary for
    # CurrentUsage, adhering to the instruction to "Avoid rewriting methods
    # that are already in the ResourceBase" when their behavior aligns.

    # To retrieve the current usage, an instance of CurrentUsage can be created
    # and its inherited 'get' method called without any arguments:
    # >>> current_usage_resource = CurrentUsage()
    # >>> usage_data = current_usage_resource.get()
    # This will result in a GET request to /currentusage/ and return the single
    # dictionary as described in the API documentation.
    #
    # No other HTTP methods (POST, PUT, DELETE) or specific actions are
    # documented for '/currentusage/' in the provided HTML.
</code>