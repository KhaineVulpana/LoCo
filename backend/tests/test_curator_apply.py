from types import SimpleNamespace

from app.ace.curator import Curator
from app.ace.playbook import Playbook


def test_apply_delta_persists_to_vector_store(fake_vector_store, fake_embedding_manager):
    playbook = Playbook()
    curator = Curator(
        llm_client=SimpleNamespace(),
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        collection_name="loco_ace_3d-gen"
    )

    operations = [
        {"type": "ADD", "section": "strategies_and_hard_rules", "content": "Keep meshes under 500 tris."}
    ]
    curator.apply_delta(playbook, operations)

    assert playbook.get_bullet_count() == 1
    assert fake_vector_store.get_collection_info("loco_ace_3d-gen")["points_count"] == 1

    bullet_id = next(iter(playbook.bullets.keys()))
    operations = [
        {"type": "UPDATE", "bullet_id": bullet_id, "content": "Keep meshes under 300 tris."}
    ]
    curator.apply_delta(playbook, operations)
    assert playbook.bullets[bullet_id].content == "Keep meshes under 300 tris."

    operations = [
        {"type": "REMOVE", "bullet_id": bullet_id}
    ]
    curator.apply_delta(playbook, operations)
    assert playbook.get_bullet_count() == 0
    assert fake_vector_store.get_collection_info("loco_ace_3d-gen")["points_count"] == 0
