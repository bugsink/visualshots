from _helpers import capture_context_path, context_for, setup_environment


SCENARIO = {
    "name": "resolved-issue",
    "description": "Resolved issue detail page.",
    "viewport": {"width": 1280, "height": 900},
}


def setup():
    from issues.models import Issue, IssueStateManager

    env = setup_environment()
    issue = Issue.objects.get(id=env["rich_issue_id"])
    IssueStateManager.resolve(issue)
    issue.save()

    return context_for(
        "/issues/issue/%s/event/%s/" % (env["rich_issue_id"], env["rich_event_id"]),
        "Resolved",
    )


def capture(page, context):
    return capture_context_path(page, context)
