from _helpers import capture_context_path, setup_screen


SCENARIO = {
    "name": "issue-breadcrumbs",
    "description": "Issue breadcrumbs tab with several breadcrumb categories.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-breadcrumbs")


def capture(page, context):
    return capture_context_path(page, context)
