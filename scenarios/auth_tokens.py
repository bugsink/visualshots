from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "auth-tokens",
    "description": "Auth tokens list.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("auth-tokens")


def capture(page, context):
    return capture_context_path(page, context)
