from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "projects",
    "description": "Project list with memberships and issue counts.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("projects")


def capture(page, context):
    return capture_context_path(page, context)
