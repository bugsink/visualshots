from _helpers import goto_and_capture, login


SCENARIO = {
    "name": "smoke-projects",
    "description": "Authenticated projects list with a team-owned project.",
    "viewport": {"width": 1280, "height": 900},
}

USERNAME = "visualshots-projects@example.org"
PASSWORD = "admin"
PROJECT_NAME = "Visualshots Project"
TEAM_NAME = "Visualshots Team"


def setup():
    from django.contrib.auth import get_user_model

    from projects.models import Project, ProjectMembership, ProjectRole
    from teams.models import Team, TeamMembership, TeamRole

    user = get_user_model().objects.create_user(username=USERNAME, email=USERNAME, password=PASSWORD)
    team = Team.objects.create(name=TEAM_NAME)
    TeamMembership.objects.create(team=team, user=user, role=TeamRole.ADMIN, accepted=True)

    project = Project.objects.create(name=PROJECT_NAME, team=team, issue_count=0, stored_event_count=0)
    ProjectMembership.objects.create(project=project, user=user, role=ProjectRole.ADMIN, accepted=True)

    return {
        "username": USERNAME,
        "password": PASSWORD,
        "path": "/projects/",
        "marker": PROJECT_NAME,
        "selector": "#content",
    }


def capture(page, context):
    login(page, context["base_url"], context["username"], context["password"])
    return goto_and_capture(page, context["base_url"], context["path"], context["marker"], context["selector"])
