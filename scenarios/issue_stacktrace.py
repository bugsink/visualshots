from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-stacktrace",
    "description": "Issue stacktrace tab with frames containing different missing information.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-stacktrace")


def capture(page, context):
    return capture_context_path(page, context)
