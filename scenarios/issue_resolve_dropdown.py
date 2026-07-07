from _helpers import goto_and_capture, login, setup_screen


SCENARIO = {
    "name": "issue-resolve-dropdown",
    "description": "Issue detail page with the resolve dropdown menu open.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    return setup_screen("issue-details")


def capture(page, context):
    login(page, context["base_url"], context["username"], context["password"])
    result = goto_and_capture(page, context["base_url"], context["path"], context["marker"], context["selector"])
    page.locator("form .dropdown").first.hover()
    page.wait_for_selector("button[value='resolved_next']:visible")
    return result
