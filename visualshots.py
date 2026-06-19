#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from html import escape
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = TOOL_DIR / "scenarios"
SETUP_RUNNER = TOOL_DIR / "scenario_setup.py"


class VisualshotsError(Exception):
    pass


@dataclass
class Scenario:
    name: str
    path: Path
    description: str
    viewport: dict


@dataclass
class CaptureResult:
    label: str
    status: str
    ref: str
    resolved_ref: str | None
    image: str | None
    error: str | None = None


def run(cmd, cwd, env=None, check=True):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and result.returncode:
        raise VisualshotsError(
            "Command failed (%s) in %s\n%s" % (" ".join(cmd), cwd, result.stdout.strip()))
    return result.stdout


def load_module(path):
    sys.path.insert(0, str(path.parent))
    try:
        module_name = "visualshots_" + path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(path.parent))
        except ValueError:
            pass


def discover_scenarios():
    scenarios = {}
    for path in sorted(SCENARIOS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue

        module = load_module(path)
        meta = getattr(module, "SCENARIO", None)
        if meta is None:
            continue

        name = meta.get("name", path.stem.replace("_", "-"))
        scenarios[name] = Scenario(
            name=name,
            path=path,
            description=meta.get("description", ""),
            viewport=meta.get("viewport", {"width": 1280, "height": 900}),
        )
    return scenarios


def selected_scenarios(all_scenarios, requested):
    names = []
    for chunk in requested:
        names.extend([part.strip() for part in chunk.split(",") if part.strip()])

    if names == ["all"]:
        return list(all_scenarios.values())

    missing = [name for name in names if name not in all_scenarios]
    if missing:
        available = ", ".join(sorted(all_scenarios))
        raise VisualshotsError("Unknown scenario(s): %s. Available: %s" % (", ".join(missing), available))

    return [all_scenarios[name] for name in names]


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(url, process, log_path, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise VisualshotsError("Django server exited early. Log:\n%s" % read_log(log_path))
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.25)

    raise VisualshotsError("Django server did not become ready. Log:\n%s" % read_log(log_path))


def read_log(path):
    if not path.exists():
        return ""
    return path.read_text(errors="replace")[-6000:]


def write_settings(run_dir, port):
    settings_path = run_dir / "visualshots_settings.py"
    settings_path.write_text(
        "\n".join([
            "from pathlib import Path",
            "from bugsink.settings.development import *",
            "",
            "RUN_DIR = Path(__file__).resolve().parent",
            "DATABASES['default']['NAME'] = str(RUN_DIR / 'db.sqlite3')",
            "DATABASES['default']['TEST']['NAME'] = str(RUN_DIR / 'test.sqlite3')",
            "DATABASES['snappea']['NAME'] = str(RUN_DIR / 'snappea.sqlite3')",
            "BUGSINK['BASE_URL'] = 'http://127.0.0.1:%d'" % port,
            "ALLOWED_HOSTS = ['127.0.0.1', 'localhost']",
            "CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:%d']" % port,
            "EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'",
            "",
        ]),
    )
    return settings_path


def python_env(worktree, run_dir, port):
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    pythonpath = [str(run_dir), str(worktree)]
    if existing_pythonpath:
        pythonpath.append(existing_pythonpath)

    env.update({
        "DJANGO_SETTINGS_MODULE": "visualshots_settings",
        "DB": "sqlite",
        "PYTHONPATH": os.pathsep.join(pythonpath),
        "VISUALSHOTS_BASE_URL": "http://127.0.0.1:%d" % port,
        "VISUALSHOTS_RUN_DIR": str(run_dir),
    })
    return env


def prepare_django(worktree, run_dir, port, build_tailwind):
    write_settings(run_dir, port)
    env = python_env(worktree, run_dir, port)

    run([sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "0"], worktree, env=env)
    if build_tailwind:
        run([sys.executable, "manage.py", "tailwind", "build"], worktree, env=env)

    return env


def start_server(worktree, env, port, run_dir):
    log_path = run_dir / "runserver.log"
    log_file = log_path.open("w")
    process = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "127.0.0.1:%d" % port, "--noreload"],
        cwd=worktree,
        env=env,
        text=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_server("http://127.0.0.1:%d/health/ready" % port, process, log_path)
    except Exception:
        process.terminate()
        process.wait(timeout=10)
        log_file.close()
        raise
    return process, log_file, log_path


def stop_server(process, log_file):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    log_file.close()


class Worktree:
    def __init__(self, repo, ref, path):
        self.repo = repo
        self.ref = ref
        self.path = path

    def __enter__(self):
        run(["git", "worktree", "add", "--detach", "--force", str(self.path), self.ref], self.repo)
        return self.path

    def __exit__(self, exc_type, exc, tb):
        run(["git", "worktree", "remove", "--force", str(self.path)], self.repo, check=False)


def resolve_ref(repo, ref):
    return run(["git", "rev-parse", ref], repo).strip()


def merge_base(repo, base_branch, after_ref):
    return run(["git", "merge-base", base_branch, after_ref], repo).strip()


def run_setup(scenario, worktree, env, run_dir):
    context_path = run_dir / "context.json"
    run([sys.executable, str(SETUP_RUNNER), str(scenario.path), str(context_path)], worktree, env=env)
    with context_path.open() as f:
        return json.load(f)


def capture_browser(scenario, context, output_path, browser_name):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise VisualshotsError("Playwright is not installed. Install it with: pip install playwright") from exc

    module = load_module(scenario.path)
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        browser = browser_type.launch()
        page = browser.new_page(viewport=scenario.viewport)
        try:
            result = module.capture(page, context) or {}
            selector = result.get("selector") or context.get("selector") or "body"
            page.locator(selector).screenshot(path=str(output_path))
        finally:
            browser.close()


def capture_ref(repo, scenario, ref, label, output_dir, tmp_root, build_tailwind, allow_unavailable):
    worktree_path = tmp_root / ("worktree-" + label)
    run_dir = tmp_root / ("run-" + label)
    run_dir.mkdir()
    image_path = output_dir / ("%s.png" % label)

    try:
        resolved_ref = resolve_ref(repo, ref)
        port = free_port()
        with Worktree(repo, ref, worktree_path) as worktree:
            env = prepare_django(worktree, run_dir, port, build_tailwind)
            context = run_setup(scenario, worktree, env, run_dir)
            context.update({
                "base_url": "http://127.0.0.1:%d" % port,
                "label": label,
                "ref": ref,
                "resolved_ref": resolved_ref,
            })

            process, log_file, log_path = start_server(worktree, env, port, run_dir)
            try:
                capture_browser(scenario, context, image_path, env["VISUALSHOTS_BROWSER"])
            except Exception as exc:
                raise VisualshotsError("%s\nDjango log:\n%s" % (exc, read_log(log_path))) from exc
            finally:
                stop_server(process, log_file)

        return CaptureResult(label, "ok", ref, resolved_ref, image_path.name)

    except Exception as exc:
        if allow_unavailable:
            return CaptureResult(label, "unavailable", ref, None, None, str(exc))
        raise


def write_metadata(output_dir, scenario, before, after):
    metadata = {
        "scenario": {
            "name": scenario.name,
            "description": scenario.description,
            "viewport": scenario.viewport,
        },
        "captures": {
            "before": before.__dict__ if before else None,
            "after": after.__dict__,
        },
    }
    with (output_dir / "metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")
    return metadata


def write_index(output_dir, metadata):
    scenario = metadata["scenario"]
    before = metadata["captures"]["before"]
    after = metadata["captures"]["after"]

    before_html = "<p>Before unavailable.</p>"
    if before and before["status"] == "ok":
        before_html = '<img src="%s" alt="Before screenshot">' % escape(before["image"])
    elif before and before["error"]:
        before_html = "<pre>%s</pre>" % escape(before["error"])

    after_html = '<img src="%s" alt="After screenshot">' % escape(after["image"])

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Visualshots: {name}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }}
    img {{ max-width: 100%; border: 1px solid #cbd5e1; background: white; }}
    pre {{ white-space: pre-wrap; padding: 12px; background: #fee2e2; border: 1px solid #fecaca; }}
    code {{ background: #e2e8f0; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>{name}</h1>
  <p>{description}</p>
  <p>Viewport: <code>{viewport}</code></p>
  <div class="grid">
    <section>
      <h2>Before</h2>
      <p><code>{before_ref}</code></p>
      {before_html}
    </section>
    <section>
      <h2>After</h2>
      <p><code>{after_ref}</code></p>
      {after_html}
    </section>
  </div>
</body>
</html>
""".format(
        name=escape(scenario["name"]),
        description=escape(scenario["description"]),
        viewport=escape(json.dumps(scenario["viewport"])),
        before_ref=escape(before["resolved_ref"] if before and before["resolved_ref"] else "unavailable"),
        after_ref=escape(after["resolved_ref"]),
        before_html=before_html,
        after_html=after_html,
    )
    (output_dir / "index.html").write_text(html)


def run_command(args):
    repo = Path(args.repo).resolve()
    scenarios = selected_scenarios(discover_scenarios(), args.scenario)
    output_root = Path(args.out).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    after_ref = args.after
    before_ref = None if args.after_only else args.before or merge_base(repo, args.base_branch, after_ref)
    os.environ["VISUALSHOTS_BROWSER"] = args.browser

    with tempfile.TemporaryDirectory(prefix="visualshots-") as tmp:
        tmp_root = Path(tmp)
        for scenario in scenarios:
            scenario_tmp = tmp_root / scenario.name
            scenario_tmp.mkdir()
            output_dir = output_root / scenario.name
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True)

            before = None
            if not args.after_only:
                print("Capturing %s before (%s)" % (scenario.name, before_ref), flush=True)
                before = capture_ref(
                    repo, scenario, before_ref, "before", output_dir, scenario_tmp, args.build_tailwind, True)

            print("Capturing %s after (%s)" % (scenario.name, after_ref), flush=True)
            after = capture_ref(
                repo, scenario, after_ref, "after", output_dir, scenario_tmp, args.build_tailwind, False)

            metadata = write_metadata(output_dir, scenario, before, after)
            write_index(output_dir, metadata)
            print("Wrote %s" % output_dir, flush=True)


def list_command(_args):
    for scenario in discover_scenarios().values():
        print("%s\t%s" % (scenario.name, scenario.description))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture Bugsink branch visual review screenshots.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List scenarios.")
    list_parser.set_defaults(func=list_command)

    run_parser = subparsers.add_parser("run", help="Capture before/after screenshots.")
    run_parser.add_argument("--repo", default=".", help="Bugsink repository path.")
    run_parser.add_argument("--scenario", action="append", required=True, help="Scenario name, comma list, or all.")
    run_parser.add_argument("--after", default="HEAD", help="Branch tip/ref to capture as after.")
    run_parser.add_argument("--before", help="Explicit before ref. Defaults to merge-base(base-branch, after).")
    run_parser.add_argument("--base-branch", default="origin/main", help="Base branch used to find before.")
    run_parser.add_argument("--out", default="results", help="Output directory.")
    run_parser.add_argument("--after-only", action="store_true", help="Only capture the after ref.")
    run_parser.add_argument("--build-tailwind", action="store_true", help="Run `python manage.py tailwind build`.")
    run_parser.add_argument("--browser", default="firefox", choices=["chromium", "firefox", "webkit"])
    run_parser.set_defaults(func=run_command)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except VisualshotsError as exc:
        print("visualshots: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
