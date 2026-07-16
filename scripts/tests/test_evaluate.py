"""Tests for evaluate.py's --auto mode: every interactive prompt (date,
ITE/policy selection, plot mode) must be skippable without blocking on
input(), which is exactly the new behavior added for batch/CI runs."""

import evaluate


def test_select_option_auto_returns_all_without_prompting():
    assert evaluate.select_option(["a", "b", "c"], "Policy", auto=True) == "ALL"


def test_select_date_folder_auto_returns_latest_without_prompting():
    date_folders = ["01-01-2026_00-00", "15-06-2026_12-00", "16-07-2026_09-30"]
    assert evaluate.select_date_folder(date_folders, auto=True) == date_folders[-1]


def test_select_ite_and_policy_auto_returns_all_for_both(monkeypatch):
    log_data = {
        "ite1": {"POLICY_A": {}, "POLICY_B": {}},
        "ite2": {"POLICY_A": {}},
    }
    selected_ites, ite_part, selected_policies, policy_part = evaluate.select_ite_and_policy(
        log_data, auto=True
    )
    assert set(selected_ites) == {"ite1", "ite2"}
    assert ite_part == "all_ites"
    assert set(selected_policies) == {"POLICY_A", "POLICY_B"}
    assert policy_part == "all_policies"


def test_parse_args_rejects_auto_without_choice(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evaluate.py", "--auto"])
    import pytest
    with pytest.raises(SystemExit):
        evaluate.parse_args()


def test_parse_args_accepts_auto_with_choice(monkeypatch):
    monkeypatch.setattr("sys.argv", ["evaluate.py", "ReSACO", "--auto"])
    args = evaluate.parse_args()
    assert args.choice == "ReSACO"
    assert args.auto is True


def test_prompt_for_evaluation_choice_accepts_numeric_and_name():
    assert evaluate.prompt_for_evaluation_choice("1") == "1"
    assert evaluate.prompt_for_evaluation_choice("ReSACO") == "1"
    assert evaluate.prompt_for_evaluation_choice("resaco") == "1"  # case-insensitive


def test_prompt_for_evaluation_choice_rejects_unknown_name():
    import pytest
    with pytest.raises(SystemExit):
        evaluate.prompt_for_evaluation_choice("not_a_real_choice")


def test_evaluation_menu_has_all_four_options():
    assert set(evaluate.EVALUATION_MENU.keys()) == {"1", "2", "3", "4"}
    assert evaluate.EVALUATION_MENU["1"]["name"] == "ReSACO"
    assert evaluate.EVALUATION_MENU["2"]["name"] == "three_tier"
    assert evaluate.EVALUATION_MENU["3"]["name"] == "ReSACO_convergence"
    assert evaluate.EVALUATION_MENU["4"]["name"] == "ReSACO_compare_algorithms"
