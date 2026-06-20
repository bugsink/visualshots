from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "preferences",
    "description": "User preferences form.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("preferences")


def capture(page, context):
    return capture_context_path(page, context)
