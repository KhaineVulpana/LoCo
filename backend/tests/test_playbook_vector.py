from app.ace.playbook import Playbook


def test_save_and_load_playbook(fake_vector_store, fake_embedding_manager):
    collection = "test_playbook_vector"
    playbook = Playbook()
    bullet_one = playbook.add_bullet("strategies_and_hard_rules", "Use caching for hot paths.")
    bullet_two = playbook.add_bullet("troubleshooting_and_pitfalls", "Check connection timeouts.")

    saved = playbook.save_to_vector_db(
        vector_store=fake_vector_store,
        embedding_manager=fake_embedding_manager,
        collection_name=collection
    )
    assert saved == 2

    loaded = Playbook.load_from_vector_db(
        vector_store=fake_vector_store,
        collection_name=collection
    )
    assert loaded.get_bullet_count() == 2
    assert bullet_one in loaded.bullets
    assert bullet_two in loaded.bullets


def test_retrieve_relevant_bullets(fake_vector_store, fake_embedding_manager):
    collection = "test_playbook_retrieve"
    playbook = Playbook()
    playbook.add_bullet("strategies_and_hard_rules", "Use caching for hot paths.")
    playbook.add_bullet("useful_code_snippets", "Serialize meshes as JSON.")

    playbook.save_to_vector_db(
        vector_store=fake_vector_store,
        embedding_manager=fake_embedding_manager,
        collection_name=collection
    )

    results = playbook.retrieve_relevant_bullets(
        query="cache hot paths",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        collection_name=collection,
        limit=1
    )
    assert len(results) == 1
    bullet, _score = results[0]
    assert "caching" in bullet.content.lower()


def test_delete_bullet_from_vector_db(fake_vector_store, fake_embedding_manager):
    collection = "test_playbook_delete"
    playbook = Playbook()
    bullet_id = playbook.add_bullet("apis_and_schemas", "Return 200 OK.")

    playbook.save_bullet_to_vector_db(
        bullet_id=bullet_id,
        vector_store=fake_vector_store,
        embedding_manager=fake_embedding_manager,
        collection_name=collection
    )

    assert fake_vector_store.get_collection_info(collection)["points_count"] == 1

    success = playbook.delete_bullet_from_vector_db(
        bullet_id=bullet_id,
        vector_store=fake_vector_store,
        collection_name=collection
    )
    assert success is True
    assert fake_vector_store.get_collection_info(collection)["points_count"] == 0
