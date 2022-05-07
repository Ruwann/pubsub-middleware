import base64
import io
import json
import typing
from urllib.parse import quote_plus, urlencode

from wsgi_types import WSGIApp, Environ, StartResponse


class PubsubMiddleware:
    """Middleware for pubsub messages"""

    def __init__(
        self,
        application: WSGIApp,
        *,
        content_type: str = "application/json",
        allow_attributes: bool = True,
        attributes_to_query: bool = False,
    ) -> None:
        """PubSub decoding middleware.

        Args:
            application (WSGIApp): WSGI application to wrap.
            content_type (str, optional): Expected content type of the
                base64-encoded pubsub message body.
                Defaults to "application/json".
            allow_attributes (bool, optional): Whether the PubSub message
                is allowed to contain attributes. Returns a 400 resonse if
                False and attributes are given.
                Defaults to True.
            attributes_to_query (bool, optional): Whether to convert PubSub
                message attributes should be converted to query parameters.
                Defaults to False.
        """
        self.application = application
        self.content_type = content_type
        self.allow_attributes = allow_attributes
        self.attributes_to_query = attributes_to_query

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:

        if environ["REQUEST_METHOD"] != "POST":
            return self.application(environ, start_response)

        length = int(environ.get("CONTENT_LENGTH", "0"))
        request_stream = environ["wsgi.input"]
        body = request_stream.read(length)
        message = json.loads(body)
        data = message["message"]["data"]
        pubsub_message = base64.b64decode(data)

        wsgi_input = io.BytesIO(pubsub_message)
        content_length = wsgi_input.getbuffer().nbytes
        wsgi_input.seek(0)
        # TODO: which class to use
        #   werkzeug dev server uses io.BufferedReader
        #   gunicorn uses gunicorn.http.body.Body
        #       https://github.com/benoitc/gunicorn/blob/master/gunicorn/http/body.py#L177
        wsgi_input = io.BufferedReader(wsgi_input)
        environ["wsgi.input"] = wsgi_input
        environ["CONTENT_LENGTH"] = content_length
        environ["CONTENT_TYPE"] = self.content_type

        # Check if attributes were supplied
        if not self.allow_attributes:
            if message["message"]["attributes"]:
                response = self.on_error(message["message"]["attributes"])
                return response(environ, start_response)

        # Transform attributes to query parameters
        if self.attributes_to_query:
            query_params = urlencode(
                message["message"]["attributes"], quote_via=quote_plus
            )
            environ["QUERY_STRING"] = query_params

            environ["RAW_URI"] = f"{environ['PATH_INFO']}?{query_params}"
            if "REQUEST_URI" in environ:
                environ["REQUEST_URI"] = environ["RAW_URI"]

        return self.application(environ, start_response)

    def on_error(self, attributes: typing.Dict[str, str]) -> WSGIApp:
        attrs = ", ".join([f"{key!r}={value!r}" for key, value in attributes.items()])
        resp = AttributeException(
            f"PubSub attributes are not allowed, but found these attributes: {attrs}"
        )
        return resp


class AttributeException:
    """Default error response to return when attributes are present but disallowed."""

    def __init__(self, description) -> None:
        """Init attribute exception."""
        self.description = description

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        status_message = "400 Bad Request"
        body = self.get_body(environ)
        headers = self.get_headers(environ)
        headers.append(("content-length", len(body)))
        start_response(status_message, headers)
        return [body]

    def get_headers(
        self, environ: typing.Optional[Environ] = None
    ) -> typing.List[typing.Tuple[str, str]]:
        """Get response headers."""
        return [
            ("content-type", "application/json"),
        ]

    def get_body(self, environ: typing.Optional[Environ] = None) -> bytes:
        """Get response body."""
        body = {
            "status": 400,
            "type": "about:blank",
            "title": "Pub/Sub message attributes are not allowed",
            "detail": self.description,
        }
        return json.dumps(body).encode()
