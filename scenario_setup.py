import importlib.util
import json
import sys
from pathlib import Path


def load_module(path):
    path = Path(path)
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location("visualshots_setup_scenario", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(path.parent))
        except ValueError:
            pass


def main():
    scenario_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    import django

    django.setup()

    module = load_module(scenario_path)
    context = module.setup() or {}

    with output_path.open("w") as f:
        json.dump(context, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
