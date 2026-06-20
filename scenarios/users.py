from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "users",
    "description": "Users list.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("users")


def capture(page, context):
    return capture_context_path(page, context)
