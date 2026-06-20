from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-list",
    "description": "Issue list for one project with several ingested issues.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-list")


def capture(page, context):
    return capture_context_path(page, context)
