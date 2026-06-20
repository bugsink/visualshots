from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-history",
    "description": "Issue history tab.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-history")


def capture(page, context):
    return capture_context_path(page, context)
