def login(page, base_url, username, password):
    page.goto(base_url + "/accounts/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click("form button")
    page.wait_for_load_state("networkidle")


def goto_and_capture(page, base_url, path, marker, selector="#content"):
    page.goto(base_url + path)
    page.wait_for_selector("text=%s" % marker)
    return {"selector": selector}
