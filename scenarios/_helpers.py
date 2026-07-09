import copy
import json
import os
import random
import uuid
from datetime import timedelta
from pathlib import Path


USERNAME = "visualshots-admin@example.org"
PASSWORD = "admin"


def login(page, base_url, username=USERNAME, password=PASSWORD):
    page.goto(base_url + "/accounts/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click("form button")
    page.wait_for_load_state("networkidle")


def goto_and_capture(page, base_url, path, marker, selector="#content"):
    page.goto(base_url + path)
    page.wait_for_selector("text=%s" % marker)
    return {"selector": selector}


def context_for(path, marker, selector="#content"):
    return {
        "username": USERNAME,
        "password": PASSWORD,
        "path": path,
        "marker": marker,
        "selector": selector,
    }


def setup_screen(screen):
    env = setup_environment()
    paths = {
        "projects": ("/projects/", "Visualshots Application"),
        "issue-list": ("/issues/%s/" % env["project_id"], "VisualshotsCheckoutError"),
        "issue-stacktrace": (
            "/issues/issue/%s/event/%s/" % (env["frames_issue_id"], env["frames_event_id"]),
            "CapturedStacktraceFo",
        ),
        "issue-details": (
            "/issues/issue/%s/event/%s/details/" % (env["rich_issue_id"], env["rich_event_id"]),
            "VisualshotsCheckoutError",
        ),
        "issue-breadcrumbs": (
            "/issues/issue/%s/event/%s/breadcrumbs/" % (env["rich_issue_id"], env["rich_event_id"]),
            "Payment authorization failed",
        ),
        "issue-events": (
            "/issues/issue/%s/events/" % env["rich_issue_id"],
            "VisualshotsCheckoutError",
        ),
        "issue-tags": (
            "/issues/issue/%s/tags/" % env["rich_issue_id"],
            "region",
        ),
        "issue-grouping": (
            "/issues/issue/%s/grouping/" % env["rich_issue_id"],
            "Issue Grouping",
        ),
        "issue-history": (
            "/issues/issue/%s/history/" % env["rich_issue_id"],
            "Add comment as manual annotation",
        ),
        "users": ("/users/", "visualshots-inactive@example.org"),
        "auth-tokens": ("/bsmain/auth_tokens/", "Visualshots API automation token"),
        "preferences": ("/accounts/preferences/", "User Preferences"),
    }
    path, marker = paths[screen]
    return context_for(path, marker)


def capture_context_path(page, context):
    login(page, context["base_url"], context["username"], context["password"])
    return goto_and_capture(page, context["base_url"], context["path"], context["marker"], context["selector"])


def samples_dir():
    configured = os.environ.get("SAMPLES_DIR")
    if configured:
        return Path(configured)

    repo = Path(os.environ["VISUALSHOTS_REPO"])
    return repo.parent / "event-samples"


def load_sample(relative_path):
    with (samples_dir() / relative_path).open() as f:
        return json.load(f)


def unique_event(sample, suffix):
    event = copy.deepcopy(sample)
    event["event_id"] = uuid.uuid5(uuid.NAMESPACE_URL, suffix).hex
    return event


def setup_environment():
    from django.contrib.auth import get_user_model

    from bsmain.models import AuthToken
    from events.models import Event, IssueEventCountsPerHour, ProjectEventCountsPerHour
    from projects.models import Project, ProjectMembership, ProjectRole, ProjectVisibility
    from teams.models import Team, TeamMembership, TeamRole

    user = get_user_model().objects.create_superuser(username=USERNAME, email=USERNAME, password=PASSWORD)
    get_user_model().objects.create_user(
        username="visualshots-inactive@example.org",
        email="visualshots-inactive@example.org",
        password=PASSWORD,
        is_active=False,
    )
    get_user_model().objects.create_user(
        username="visualshots-member@example.org",
        email="visualshots-member@example.org",
        password=PASSWORD,
    )

    team = Team.objects.create(name="Visualshots Team")
    TeamMembership.objects.create(team=team, user=user, role=TeamRole.ADMIN, accepted=True)

    project = Project.objects.create(
        name="Visualshots Application",
        team=team,
        visibility=ProjectVisibility.TEAM_MEMBERS,
    )
    ProjectMembership.objects.create(project=project, user=user, role=ProjectRole.ADMIN, accepted=True)

    other_project = Project.objects.create(
        name="Visualshots Joinable Project",
        team=team,
        visibility=ProjectVisibility.JOINABLE,
    )
    ProjectMembership.objects.create(project=other_project, user=user, role=ProjectRole.MEMBER, accepted=False)

    AuthToken.objects.create(
        token="a" * 40,
        description="Visualshots API automation token",
    )
    AuthToken.objects.create(
        token="b" * 40,
        description="Short-lived deployment token",
    )

    rich_sample = load_sample("bugsink/visualshots-rich.json")
    frames_sample = load_sample("bugsink/frames-with-missing-info.json")

    rich_event = ingest_sample(project, unique_event(rich_sample, "visualshots-rich-main"))
    frames_event = ingest_sample(project, unique_event(frames_sample, "visualshots-frames-main"))

    for index, sample_name in enumerate([
        "bugsink/contexts.json",
        "bugsink/exception-group.json",
        "sentry/javascript-exception-fallback-to-message-whistles.json",
    ], start=1):
        sample = load_sample(sample_name)
        ingest_sample(project, unique_event(sample, "visualshots-list-%s-%s" % (index, sample_name)))

    # Only patch denormalized counts and sparkline bucket data after real ingestion is complete.
    # The ingest path relies on these counters while creating issues/events; changing them earlier makes Bugsink lie to
    # itself during setup and can break later ingestion in surprising ways.
    for issue in project.issue_set.all():
        events = list(Event.objects.filter(issue=issue).order_by("digest_order"))
        issue.stored_event_count = len(events)
        issue.digested_event_count = max(len(events), 9)
        issue.save(update_fields=["stored_event_count", "digested_event_count"])
        seed_issue_sparkline(IssueEventCountsPerHour, project, issue, events)
        seed_issue_list_sparkline(IssueEventCountsPerHour, project, issue, events)

    project.issue_count = project.issue_set.filter(is_deleted=False).count()
    project.stored_event_count = Event.objects.filter(project=project).count()
    project.digested_event_count = max(project.stored_event_count, 37)
    project.save(update_fields=["issue_count", "stored_event_count", "digested_event_count"])
    seed_project_list_sparkline(ProjectEventCountsPerHour, project)

    return {
        "username": USERNAME,
        "password": PASSWORD,
        "project_id": project.id,
        "rich_issue_id": str(rich_event.issue.id),
        "rich_event_id": str(rich_event.id),
        "frames_issue_id": str(frames_event.issue.id),
        "frames_event_id": str(frames_event.id),
    }


def ingest_sample(project, event_data):
    from compat.dsn import get_header_value
    from events.models import Event
    from django.test import Client
    from django.utils import timezone

    if "timestamp" not in event_data:
        event_data["timestamp"] = timezone.now().isoformat()

    response = Client().post(
        "/api/%s/store/" % project.id,
        json.dumps(event_data),
        content_type="application/json",
        headers={
            "X-Sentry-Auth": get_header_value("http://%s@visualshots.invalid/%s" % (project.sentry_key, project.id)),
        },
    )
    if response.status_code != 200:
        raise RuntimeError("Could not ingest %s: %s" % (event_data.get("event_id"), response.content.decode()))

    return Event.objects.get(project=project, event_id=event_data["event_id"])


def seed_issue_sparkline(bucket_model, project, issue, events):
    from django.utils import timezone

    from events.sparklines import get_sparkline_range

    if not events:
        return

    rng = random.Random(str(issue.id))
    now = timezone.now()
    start, _end, _interval = get_sparkline_range(now)
    buckets = [start + timedelta(hours=i * 6) for i in range(12, 28)]
    last_digest_order = events[-1].digest_order

    for index, bucket in enumerate(buckets):
        count = rng.randint(0, 7)
        if index in (3, 9, 14):
            count += rng.randint(5, 14)
        if index == len(buckets) - 1:
            count = max(count, 1)

        bucket_model.objects.update_or_create(
            project=project,
            issue=issue,
            bucket=bucket,
            defaults={
                "count": count,
                "digest_order": last_digest_order,
            },
        )


def seed_issue_list_sparkline(bucket_model, project, issue, events):
    from django.utils import timezone

    from events.usage import hour_bucket

    if not events:
        return

    current_hour = hour_bucket(timezone.now())
    last_digest_order = events[-1].digest_order
    pattern = [1, 3, 2, 8, 4, 2, 12, 3, 5, 1, 7, 2, 4, 1, 10, 5, 3, 2, 6, 1, 4, 2, 9, 13]

    for age in range(24):
        count = pattern[age]

        bucket_model.objects.update_or_create(
            project=project,
            issue=issue,
            bucket=current_hour - timedelta(hours=age),
            defaults={
                "count": count,
                "digest_order": last_digest_order,
            },
        )


def seed_project_list_sparkline(bucket_model, project):
    from django.db.models import Sum
    from django.utils import timezone

    from events.models import IssueEventCountsPerHour
    from events.usage import hour_bucket

    current_hour = hour_bucket(timezone.now())
    for age in range(24):
        bucket = current_hour - timedelta(hours=age)
        count = IssueEventCountsPerHour.objects.filter(project=project, bucket=bucket).aggregate(
            count=Sum("count"))["count"]
        if count:
            bucket_model.objects.update_or_create(
                project=project,
                bucket=bucket,
                defaults={"count": count},
            )
