"""Load the YAML method catalog and resolve impl references to callables."""
from pathlib import Path
import importlib
import yaml
from typing import Any, Callable

_CATALOG_DIR = Path(__file__).parent / "entries"
_registry: dict[str, dict] = {}


def _resolve(dotpath: str) -> Callable:
    """Resolve 'module.path:function' to a callable."""
    module_path, fn_name = dotpath.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def load_catalog() -> dict[str, dict]:
    """Load all YAML catalog entries. Cached after first call."""
    global _registry
    if _registry:
        return _registry
    for yml in sorted(_CATALOG_DIR.glob("*.yaml")):
        entry = yaml.safe_load(yml.read_text())
        _registry[entry["id"]] = entry
    return _registry


def get_method(method_id: str) -> dict:
    catalog = load_catalog()
    if method_id not in catalog:
        raise KeyError(f"Unknown method: {method_id}. Available: {list(catalog)}")
    return catalog[method_id]


def get_impl(method_id: str) -> tuple[Callable, Callable, Callable]:
    """Return (run, check_assumptions, cost) callables for a method."""
    entry = get_method(method_id)

    # Resolve run from impl field (e.g. "module.path:run_pca")
    impl_module_path, run_fn_name = entry["impl"].rsplit(":", 1)
    impl_mod = importlib.import_module(impl_module_path)
    run_fn = getattr(impl_mod, run_fn_name)

    # check_assumptions always lives in the same module as the run function
    check_fn = getattr(impl_mod, "check_assumptions")

    # Resolve cost from cost_model field if present, else fall back to impl module
    cost_entry = entry.get("cost_model") or entry["impl"]
    cost_module_path, cost_fn_name = cost_entry.rsplit(":", 1)
    cost_mod = importlib.import_module(cost_module_path)
    cost_fn = getattr(cost_mod, cost_fn_name)

    return run_fn, check_fn, cost_fn


def methods_for_intent(intent: str) -> list[dict]:
    """Return all catalog entries that support a given intent."""
    catalog = load_catalog()
    return [e for e in catalog.values() if intent in e.get("intents", [])]


def validate_catalog() -> list[str]:
    """CI validator: return list of error strings (empty = all OK)."""
    errors = []
    for method_id, entry in load_catalog().items():
        for required_field in ("id", "name", "intents", "impl", "citation"):
            if required_field not in entry:
                errors.append(f"{method_id}: missing field '{required_field}'")
        try:
            get_impl(method_id)
        except Exception as e:
            errors.append(f"{method_id}: cannot resolve impl — {e}")
    return errors
