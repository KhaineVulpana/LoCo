from app.ace.playbook import Playbook, PlaybookBullet


def test_add_update_remove_bullet():
    playbook = Playbook()
    bullet_id = playbook.add_bullet("strategies_and_hard_rules", "Use retry logic.")

    assert bullet_id in playbook.bullets
    assert bullet_id in playbook.sections["strategies_and_hard_rules"]

    playbook.update_bullet(bullet_id, content="Use bounded retries.")
    assert playbook.bullets[bullet_id].content == "Use bounded retries."

    playbook.remove_bullet(bullet_id)
    assert bullet_id not in playbook.bullets
    assert bullet_id not in playbook.sections["strategies_and_hard_rules"]


def test_playbook_roundtrip_to_dict():
    playbook = Playbook()
    bullet_id = playbook.add_bullet("apis_and_schemas", "Return 201 on create.")
    playbook.mark_helpful(bullet_id)
    data = playbook.to_dict()

    restored = Playbook.from_dict(data)
    assert bullet_id in restored.bullets
    assert restored.bullets[bullet_id].helpful_count == 1


def test_playbook_section_content_format():
    playbook = Playbook()
    bullet_id = playbook.add_bullet("domain_knowledge", "Meshes use meters.")
    content = playbook.get_section_content("domain_knowledge")
    assert content == [f"[{bullet_id}] Meshes use meters."]


def test_playbook_bullet_score():
    bullet = PlaybookBullet(id="b1", section="test", content="Test")
    assert bullet.get_score() == 0.5

    bullet.helpful_count = 3
    bullet.harmful_count = 1
    assert bullet.get_score() == 0.75
