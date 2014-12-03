class ApiClientError(Exception):
    def __init__(self, message, status_code=None, request_id=''):
        super(ApiClientError, self).__init__(message, status_code, request_id)

        self.message = message
        self.status_code = status_code
        self.request_id = request_id

    def __repr__(self):
        return "<{s.__class__.__name__}(" \
               "'{s.message}', status_code={s.status_code}, request_id='{s.request_id}')>".format(s=self)


class PermissionError(ApiClientError):
    pass


class ClientError(ApiClientError):
    pass


class ServerError(ApiClientError):
    pass


class AuthError(ApiClientError):
    pass
