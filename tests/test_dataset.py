"""
Unit tests for the 50-task evaluation dataset and loader.
"""

from runwise.evals.dataset import generate_tasks_file, load_tasks, validate_dataset
from runwise.evals.models import Task


def test_dataset_generation_and_loading(tmp_path):
    """Verify tasks.jsonl generates and loads correctly."""
    dest = tmp_path / "tasks.jsonl"
    generate_tasks_file(dest)

    assert dest.exists()
    tasks = load_tasks(dest)
    assert len(tasks) == 50
    assert all(isinstance(t, Task) for t in tasks)


def test_dataset_split_discipline():
    """Verify strictly 35 dev and 15 frozen_holdout tasks (70/30 split)."""
    dev_tasks = load_tasks(split="dev")
    holdout_tasks = load_tasks(split="frozen_holdout")

    assert len(dev_tasks) == 35
    assert len(holdout_tasks) == 15
    assert len(dev_tasks) + len(holdout_tasks) == 50


def test_dataset_task_ids_unique():
    """Verify all 50 task IDs are globally unique."""
    tasks = load_tasks()
    ids = [t.id for t in tasks]
    assert len(ids) == len(set(ids))


def test_dataset_categories_distribution():
    """Verify representation across all 5 core operational categories."""
    tasks = load_tasks()
    stats = validate_dataset(tasks)

    expected_categories = {"cancellation", "refund", "address_update", "inquiry", "adversarial"}
    assert set(stats["categories"].keys()) == expected_categories

    # Every category must have tasks in both dev and holdout
    for cat in expected_categories:
        dev_in_cat = [t for t in tasks if t.category == cat and t.split == "dev"]
        holdout_in_cat = [t for t in tasks if t.category == cat and t.split == "frozen_holdout"]
        assert len(dev_in_cat) > 0, f"Category {cat} missing dev tasks"
        assert len(holdout_in_cat) > 0, f"Category {cat} missing holdout tasks"


def test_information_barrier_integrity():
    """Verify user prompts do not leak internal assertion queries or expected values."""
    tasks = load_tasks()
    for task in tasks:
        # Prompt must be a non-empty human-like message
        assert len(task.user_prompt.strip()) > 10
        # Prompts must never contain raw SQL assertion strings
        assert "SELECT " not in task.user_prompt.upper()
        assert "FROM orders" not in task.user_prompt.lower()
        assert "FROM refunds" not in task.user_prompt.lower()


def test_dataset_ci_split():
    """Verify CI split returns a stratified subset of 5 tasks (1 per category)."""
    ci_tasks = load_tasks(split="ci")
    assert len(ci_tasks) == 5
    categories = {t.category for t in ci_tasks}
    assert categories == {"cancellation", "refund", "address_update", "inquiry", "adversarial"}
    assert all(t.split == "dev" for t in ci_tasks)
