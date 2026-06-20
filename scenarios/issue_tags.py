from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-tags",
    "description": "Issue tags tab with percentages.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-tags")


def capture(page, context):
    return capture_context_path(page, context)
