import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
APP_ROOT = PROJECT_ROOT / "app"
PYTHON_SOURCE_ROOTS = (APP_ROOT, PROJECT_ROOT / "tests", PROJECT_ROOT / "scripts")


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    return tuple(imported)


def _is_application_package(module: str) -> bool:
    if module != "app" and not module.startswith("app."):
        return False
    return PROJECT_ROOT.joinpath(*module.split(".")).is_dir()


def test_services_do_not_depend_on_higher_or_concrete_layers() -> None:
    forbidden = ("app.adapters", "app.agent", "app.api", "app.composition")
    violations: list[str] = []
    for path in sorted((APP_ROOT / "services").rglob("*.py")):
        for imported in _imports(path):
            if imported.startswith(forbidden):
                violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


def test_core_exceptions_are_transport_framework_independent() -> None:
    imported = _imports(APP_ROOT / "core" / "exceptions.py")
    assert not any(module.startswith(("fastapi", "starlette")) for module in imported)


def test_package_initializers_do_not_define_implicit_public_apis() -> None:
    violations: list[str] = []
    for path in sorted(APP_ROOT.rglob("__init__.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                violations.append(str(path.relative_to(APP_ROOT)))
            elif isinstance(node, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                ):
                    violations.append(str(path.relative_to(APP_ROOT)))
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "__all__"
            ):
                violations.append(str(path.relative_to(APP_ROOT)))
    assert violations == []


def test_internal_code_imports_concrete_application_modules() -> None:
    violations: list[str] = []
    for root in PYTHON_SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module is not None:
                    if _is_application_package(node.module):
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT)} -> {node.module}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if _is_application_package(alias.name):
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)} -> {alias.name}"
                            )
    assert violations == []
