from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-grouping",
    "description": "Issue grouping tab.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-grouping")


def capture(page, context):
    return capture_context_path(page, context)
