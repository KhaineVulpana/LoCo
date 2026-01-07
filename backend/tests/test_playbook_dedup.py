from app.ace.playbook import Playbook


def test_deduplicate_merges_counts():
    playbook = Playbook()
    id_one = playbook.add_bullet('strategies_and_hard_rules', 'Use caching')
    id_two = playbook.add_bullet('strategies_and_hard_rules', 'use caching')

    playbook.bullets[id_one].helpful_count = 1
    playbook.bullets[id_two].harmful_count = 2

    playbook.deduplicate()

    assert playbook.get_bullet_count() == 1
    remaining = next(iter(playbook.bullets.values()))
    assert remaining.helpful_count == 1
    assert remaining.harmful_count == 2


def test_prune_harmful_removes_bullets():
    playbook = Playbook()
    bullet_id = playbook.add_bullet('troubleshooting_and_pitfalls', 'Avoid null refs')
    playbook.bullets[bullet_id].harmful_count = 3

    playbook.prune_harmful(threshold=3)

    assert playbook.get_bullet_count() == 0
