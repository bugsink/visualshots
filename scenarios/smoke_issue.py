from _helpers import goto_and_capture, login


SCENARIO = {
    "name": "smoke-issue",
    "description": "Issue event detail page with a synthetic Python exception.",
    "viewport": {"width": 1280, "height": 900},
}

USERNAME = "visualshots-issue@example.org"
PASSWORD = "admin"
PROJECT_NAME = "Visualshots Issue Project"
ISSUE_TYPE = "VisualshotsError"
ISSUE_VALUE = "Synthetic exception for screenshot review"


def setup():
    from django.contrib.auth import get_user_model

    from events.factories import create_event, create_event_data
    from issues.factories import get_or_create_issue
    from projects.models import Project, ProjectMembership, ProjectRole

    user = get_user_model().objects.create_user(username=USERNAME, email=USERNAME, password=PASSWORD)
    project = Project.objects.create(name=PROJECT_NAME, issue_count=1, stored_event_count=1, digested_event_count=1)
    ProjectMembership.objects.create(project=project, user=user, role=ProjectRole.ADMIN, accepted=True)

    event_data = create_event_data(exception_type=ISSUE_TYPE)
    event_data["exception"]["values"][0]["value"] = ISSUE_VALUE
    event_data["request"] = {
        "url": "https://example.invalid/visualshots",
        "method": "GET",
    }
    event_data["breadcrumbs"] = {
        "values": [
            {"category": "visualshots", "message": "Created synthetic event"},
        ],
    }

    issue, _ = get_or_create_issue(project, event_data)
    issue.calculated_type = ISSUE_TYPE
    issue.calculated_value = ISSUE_VALUE
    issue.stored_event_count = 1
    issue.save(update_fields=["calculated_type", "calculated_value", "stored_event_count"])

    event = create_event(project, issue, event_data=event_data, project_digest_order=1)

    return {
        "username": USERNAME,
        "password": PASSWORD,
        "path": "/issues/issue/%s/event/%s/details/" % (issue.id, event.id),
        "marker": ISSUE_TYPE,
        "selector": "#content",
    }


def capture(page, context):
    login(page, context["base_url"], context["username"], context["password"])
    return goto_and_capture(page, context["base_url"], context["path"], context["marker"], context["selector"])
