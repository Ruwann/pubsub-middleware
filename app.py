import connexion

from middleware import PubsubMiddleware


def post_greeting(pubsub_message):
    return pubsub_message


app = connexion.FlaskApp(__name__, port=9090, specification_dir="swagger/")
app.add_api("helloworld-api.yaml", arguments={"title": "Hello World Example"})

app.app.wsgi_app = PubsubMiddleware(app.app.wsgi_app)

if __name__ == "__main__":
    app.run()
