"""Tests for APP_PROFILES / Scenario -- the fix that replaced sampling a
single homogeneous task profile from Table II's abstract ranges with
picking one of the four real app types (matching
scripts/{ReSACO,three_tier}/config/applications.xml exactly), weighted by
usage_percentage, mirroring how EdgeCloudSim's IdleActiveLoadGenerator
actually assigns an app type per device."""

from collections import Counter

from resaco.scenario import APP_PROFILES, sample_scenario, sample_scenario_pool


def test_four_app_profiles_matching_applications_xml():
    names = {p.name for p in APP_PROFILES}
    assert names == {"AUGMENTED_REALITY", "HEALTH_APP", "HEAVY_COMP_APP", "INFOTAINMENT_APP"}


def test_usage_percentages_sum_to_100():
    assert sum(p.usage_percentage for p in APP_PROFILES) == 100


def test_heavy_comp_app_task_length_exceeds_old_table_ii_range():
    # The old Table II-sampled range topped out at 10000 -- HEAVY_COMP_APP's
    # real mean (45000) was never reachable before this fix, understating
    # exactly the kind of long, expensive task the paper's own env's
    # applications.xml actually generates.
    heavy = next(p for p in APP_PROFILES if p.name == "HEAVY_COMP_APP")
    assert heavy.task_length == 45000


def test_sample_scenario_picks_one_of_the_real_profiles():
    scenario = sample_scenario(__import__("random").Random(1))
    assert scenario.app_profile in APP_PROFILES
    assert 200 <= scenario.number_of_mobile_devices <= 2000


def test_sample_scenario_pool_app_mix_roughly_matches_usage_percentage():
    scenarios = sample_scenario_pool(2000, seed=1)
    counts = Counter(s.app_profile.name for s in scenarios)
    total = sum(counts.values())
    for profile in APP_PROFILES:
        observed_pct = 100 * counts.get(profile.name, 0) / total
        # generous tolerance -- this is a statistical sanity check, not a
        # precise distribution match
        assert abs(observed_pct - profile.usage_percentage) < 5, (
            f"{profile.name}: expected ~{profile.usage_percentage}%, got {observed_pct:.1f}%"
        )
