from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-events",
    "description": "Issue event list tab.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-events")


def capture(page, context):
    return capture_context_path(page, context)
