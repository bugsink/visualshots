from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-details",
    "description": "Issue event details tab with request, user, tags, contexts, modules, SDK, and extra data.",
    "viewport": {"width": 1280, "height": 1100},
}


def setup():
    return setup_screen("issue-details")


def capture(page, context):
    return capture_context_path(page, context)
