class ApiClientError(Exception):
    pass


class PermissionError(ApiClientError):
    pass


class ClientError(ApiClientError):
    pass


class ServerError(ApiClientError):
    pass


class AuthError(ApiClientError):
    pass
