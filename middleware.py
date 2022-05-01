import base64
import io
import json


class PubsubMiddleware:
    """Middleware for pubsub messages"""

    def __init__(self, application, *, content_type='application/json'):
        self.application = application
        self.content_type = content_type

    def __call__(self, environ, start_response):
        iterable = None

        if environ['REQUEST_METHOD'] == 'POST':
            # print(environ)
            # when running under gunicorn
            # print(environ['wsgi.input'])  # gunicorn.http.body.Body
            # print(environ['wsgi.input'].reader)  # gunicorn.http.body.LengthReader
            # print(environ['wsgi.input'].buf)  # _io.BytesIO

            length = int(environ.get('CONTENT_LENGTH', '0'))
            request_stream = environ['wsgi.input']
            body = request_stream.read(length)
            # body = request_stream.peek()
            message = json.loads(body)
            data = message['message']['data']
            pubsub_message = base64.b64decode(data)

            wsgi_input = io.BytesIO(pubsub_message)
            content_length = wsgi_input.getbuffer().nbytes
            wsgi_input.seek(0)
            # TODO: which class to use
            #   werkzeug dev server uses io.BufferedReader
            #   gunicorn uses gunicorn.http.body.Body
            #       https://github.com/benoitc/gunicorn/blob/master/gunicorn/http/body.py#L177
            wsgi_input = io.BufferedReader(wsgi_input)
            environ['wsgi.input'] = wsgi_input
            # change content_length
            environ['CONTENT_LENGTH'] = content_length
            # change content_type
            environ['CONTENT_TYPE'] = self.content_type

        try:
            iterable = self.application(environ, start_response)
            for data in iterable:
                yield data

        finally:
            if hasattr(iterable, 'close'):
                iterable.close()
