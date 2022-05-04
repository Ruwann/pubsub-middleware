import base64
import io
import json

from werkzeug.exceptions import BadRequest


class PubsubMiddleware:
    """Middleware for pubsub messages"""

    def __init__(
        self, application, *, content_type="application/json", allow_attributes=True
    ):
        self.application = application
        self.content_type = content_type
        self.allow_attributes = allow_attributes

    def __call__(self, environ, start_response):

        if environ["REQUEST_METHOD"] != "POST":
            return self.application(environ, start_response)

        # print(environ)
        # when running under gunicorn
        # print(environ['wsgi.input'])  # gunicorn.http.body.Body
        # print(environ['wsgi.input'].reader)  # gunicorn.http.body.LengthReader
        # print(environ['wsgi.input'].buf)  # _io.BytesIO

        length = int(environ.get("CONTENT_LENGTH", "0"))
        request_stream = environ["wsgi.input"]
        body = request_stream.read(length)
        # body = request_stream.peek()
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
        # change content_length
        environ["CONTENT_LENGTH"] = content_length
        # change content_type
        environ["CONTENT_TYPE"] = self.content_type

        # Check if attributes were supplied
        if not self.allow_attributes:
            if message["message"]["attributes"]:
                response = self.on_error(message["message"]["attributes"])
                return response(environ, start_response)

        return self.application(environ, start_response)

    def on_error(self, attributes):
        attrs = ", ".join([f"{key!r}={value!r}" for key, value in attributes.items()])
        bad_req = BadRequest(
            f"PubSub attributes are not allowed, but found these attributes: {attrs}"
        )
        return bad_req
