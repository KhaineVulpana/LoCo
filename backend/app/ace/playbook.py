"""
ACE Playbook - Structured context storage with bullets
"""

import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import structlog
from qdrant_client.models import PointStruct

logger = structlog.get_logger()


@dataclass
class PlaybookBullet:
    """A single bullet point in the playbook"""

    id: str
    section: str
    content: str
    helpful_count: int = 0
    harmful_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "section": self.section,
            "content": self.content,
            "helpful_count": self.helpful_count,
            "harmful_count": self.harmful_count,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybookBullet":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            section=data["section"],
            content=data["content"],
            helpful_count=data.get("helpful_count", 0),
            harmful_count=data.get("harmful_count", 0),
            metadata=data.get("metadata", {})
        )

    def get_score(self) -> float:
        """
        Calculate bullet quality score as ratio (0.0-1.0)

        Returns:
            Float between 0.0 and 1.0 representing quality
            0.5 = no feedback yet
        """
        if self.helpful_count + self.harmful_count == 0:
            return 0.5  # Neutral score for bullets with no feedback
        return self.helpful_count / (self.helpful_count + self.harmful_count)


@dataclass
class PlaybookDelta:
    """
    Represents incremental changes to a playbook

    ACE uses delta updates instead of monolithic rewrites to:
    - Avoid context collapse
    - Enable localized edits
    - Support parallel processing
    - Preserve detailed knowledge
    """
    additions: List[PlaybookBullet] = field(default_factory=list)
    updates: List[PlaybookBullet] = field(default_factory=list)
    deletions: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if delta has any changes"""
        return (
            len(self.additions) == 0 and
            len(self.updates) == 0 and
            len(self.deletions) == 0
        )

    def get_total_changes(self) -> int:
        """Get total number of changes"""
        return len(self.additions) + len(self.updates) + len(self.deletions)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "additions": [b.to_dict() for b in self.additions],
            "updates": [b.to_dict() for b in self.updates],
            "deletions": self.deletions
        }


class Playbook:
    """
    ACE Playbook - Evolving context organized into structured bullets

    Implements:
    - Incremental delta updates
    - Grow-and-refine mechanism
    - Deduplication
    """

    def __init__(self):
        self.bullets: Dict[str, PlaybookBullet] = {}
        self.sections: Dict[str, List[str]] = {
            "strategies_and_hard_rules": [],
            "useful_code_snippets": [],
            "troubleshooting_and_pitfalls": [],
            "apis_and_schemas": [],
            "domain_knowledge": []
        }

    def add_bullet(self, section: str, content: str, bullet_id: Optional[str] = None) -> str:
        """
        Add a new bullet to the playbook

        Args:
            section: Section to add to
            content: Bullet content
            bullet_id: Optional specific ID (otherwise auto-generated)

        Returns:
            The bullet ID
        """
        if section not in self.sections:
            self.sections[section] = []

        if bullet_id is None:
            # Generate unique ID
            prefix = section[:3]
            bullet_id = f"{prefix}-{str(uuid.uuid4())[:8]}"

        bullet = PlaybookBullet(
            id=bullet_id,
            section=section,
            content=content
        )

        self.bullets[bullet_id] = bullet
        if bullet_id not in self.sections[section]:
            self.sections[section].append(bullet_id)

        logger.debug("bullet_added", bullet_id=bullet_id, section=section)
        return bullet_id

    def update_bullet(self, bullet_id: str, **kwargs):
        """Update an existing bullet"""
        if bullet_id not in self.bullets:
            logger.warning("bullet_not_found", bullet_id=bullet_id)
            return

        bullet = self.bullets[bullet_id]
        for key, value in kwargs.items():
            if hasattr(bullet, key):
                setattr(bullet, key, value)

    def mark_helpful(self, bullet_id: str):
        """Mark a bullet as helpful"""
        if bullet_id in self.bullets:
            self.bullets[bullet_id].helpful_count += 1

    def mark_harmful(self, bullet_id: str):
        """Mark a bullet as harmful"""
        if bullet_id in self.bullets:
            self.bullets[bullet_id].harmful_count += 1

    def remove_bullet(self, bullet_id: str):
        """Remove a bullet from the playbook"""
        if bullet_id not in self.bullets:
            return

        bullet = self.bullets[bullet_id]
        section = bullet.section

        del self.bullets[bullet_id]
        if section in self.sections and bullet_id in self.sections[section]:
            self.sections[section].remove(bullet_id)

        logger.debug("bullet_removed", bullet_id=bullet_id)

    def get_section_content(self, section: str) -> List[str]:
        """Get all bullet content for a section"""
        if section not in self.sections:
            return []

        content = []
        for bullet_id in self.sections[section]:
            if bullet_id in self.bullets:
                bullet = self.bullets[bullet_id]
                content.append(f"[{bullet.id}] {bullet.content}")

        return content

    def to_text(self) -> str:
        """Convert playbook to formatted text"""
        sections_text = []

        for section_name, bullet_ids in self.sections.items():
            if not bullet_ids:
                continue

            section_title = section_name.replace("_", " ").title()
            sections_text.append(f"\n## {section_title}\n")

            for bullet_id in bullet_ids:
                if bullet_id in self.bullets:
                    bullet = self.bullets[bullet_id]
                    sections_text.append(f"[{bullet.id}] {bullet.content}")

        return "\n".join(sections_text)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "bullets": {bid: b.to_dict() for bid, b in self.bullets.items()},
            "sections": self.sections
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playbook":
        """Create from dictionary"""
        playbook = cls()
        playbook.bullets = {
            bid: PlaybookBullet.from_dict(b)
            for bid, b in data.get("bullets", {}).items()
        }
        playbook.sections = data.get("sections", playbook.sections)
        return playbook

    def deduplicate(self, threshold: float = 0.85) -> Tuple[List[str], List[str]]:
        """
        Remove duplicate bullets using semantic similarity

        Args:
            threshold: Similarity threshold for considering duplicates
        """
        # This would use embedding-based similarity in production
        # For now, simple exact match deduplication
        seen_content = {}
        to_remove = []
        updated_ids = []

        for bullet_id, bullet in self.bullets.items():
            content_normalized = bullet.content.lower().strip()

            if content_normalized in seen_content:
                # Merge counts into the existing one
                existing_id = seen_content[content_normalized]
                self.bullets[existing_id].helpful_count += bullet.helpful_count
                self.bullets[existing_id].harmful_count += bullet.harmful_count
                if existing_id not in updated_ids:
                    updated_ids.append(existing_id)
                to_remove.append(bullet_id)
            else:
                seen_content[content_normalized] = bullet_id

        for bullet_id in to_remove:
            self.remove_bullet(bullet_id)

        if to_remove:
            logger.info("deduplication_complete", removed_count=len(to_remove))
        return to_remove, updated_ids

    def prune_harmful(self, threshold: int = 3) -> List[str]:
        """Remove bullets that have been marked harmful too many times"""
        to_remove = []

        for bullet_id, bullet in self.bullets.items():
            if bullet.harmful_count >= threshold:
                to_remove.append(bullet_id)

        for bullet_id in to_remove:
            self.remove_bullet(bullet_id)

        if to_remove:
            logger.info("harmful_bullets_pruned", count=len(to_remove))
        return to_remove

    def save_to_vector_db(
        self,
        vector_store,
        embedding_manager,
        collection_name: str
    ) -> int:
        """
        Save all bullets to vector database

        Args:
            vector_store: Vector store instance
            embedding_manager: Embedding manager instance
            collection_name: Qdrant collection name (e.g., "loco_ace_vscode")

        Returns:
            Number of bullets saved
        """
        if not self.bullets:
            logger.warning("no_bullets_to_save", collection=collection_name)
            return 0

        logger.info("saving_playbook_to_vector_db",
                   collection=collection_name,
                   bullet_count=len(self.bullets))

        bullet_ids = []
        bullet_contents = []
        bullet_payloads = []

        for bullet_id, bullet in self.bullets.items():
            bullet_ids.append(bullet_id)
            bullet_contents.append(bullet.content)
            payload = bullet.to_dict()
            payload["bullet_id"] = bullet.id
            bullet_payloads.append(payload)

        try:
            embeddings = embedding_manager.embed(bullet_contents)
        except Exception as e:
            logger.error("bullet_embedding_failed",
                        collection=collection_name,
                        error=str(e))
            raise

        points = []
        for bullet_id, embedding, payload in zip(bullet_ids, embeddings, bullet_payloads):
            points.append(PointStruct(
                id=bullet_id,
                vector=embedding.tolist(),
                payload=payload
            ))

        try:
            vector_store.upsert_vectors(collection_name, points)
            logger.info("playbook_saved_to_vector_db",
                       collection=collection_name,
                       bullets_saved=len(points))
            return len(points)
        except Exception as e:
            logger.error("playbook_save_failed",
                        collection=collection_name,
                        error=str(e))
            raise

    def save_bullet_to_vector_db(
        self,
        bullet_id: str,
        vector_store,
        embedding_manager,
        collection_name: str
    ) -> bool:
        """
        Save a single bullet to vector database

        Args:
            bullet_id: Bullet identifier
            vector_store: Vector store instance
            embedding_manager: Embedding manager instance
            collection_name: Qdrant collection name

        Returns:
            True if successful
        """
        if bullet_id not in self.bullets:
            logger.error("bullet_not_found", bullet_id=bullet_id)
            return False

        bullet = self.bullets[bullet_id]

        try:
            embedding = embedding_manager.embed_single(bullet.content)
        except Exception as e:
            logger.error("bullet_embedding_failed",
                        bullet_id=bullet_id,
                        collection=collection_name,
                        error=str(e))
            return False

        payload = bullet.to_dict()
        payload["bullet_id"] = bullet.id

        point = PointStruct(
            id=bullet_id,
            vector=embedding.tolist(),
            payload=payload
        )

        try:
            vector_store.upsert_vectors(collection_name, [point])
            logger.debug("bullet_saved_to_vector_db",
                        bullet_id=bullet_id,
                        collection=collection_name)
            return True
        except Exception as e:
            logger.error("bullet_save_failed",
                        bullet_id=bullet_id,
                        collection=collection_name,
                        error=str(e))
            return False

    @classmethod
    def load_from_vector_db(
        cls,
        vector_store,
        collection_name: str,
        max_bullets: int = 1000
    ) -> "Playbook":
        """
        Load playbook from vector database

        Args:
            vector_store: Vector store instance
            collection_name: Qdrant collection name
            max_bullets: Maximum bullets to load

        Returns:
            Loaded Playbook instance
        """
        playbook = cls()

        try:
            logger.info("loading_playbook_from_vector_db",
                       collection=collection_name,
                       max_bullets=max_bullets)

            offset = None
            loaded = 0

            while True:
                remaining = max_bullets - loaded
                if remaining <= 0:
                    break

                page = vector_store.scroll(
                    collection_name=collection_name,
                    limit=min(100, remaining),
                    offset=offset
                )

                points = page.get("points", [])
                if not points:
                    break

                for point in points:
                    payload = point.get("payload") or {}

                    if "id" in payload and "section" in payload and "content" in payload:
                        bullet = PlaybookBullet.from_dict(payload)
                    else:
                        bullet = PlaybookBullet(
                            id=payload.get("bullet_id", str(point.get("id"))),
                            section=payload.get("section", "strategies_and_hard_rules"),
                            content=payload.get("content", ""),
                            helpful_count=payload.get("helpful_count", 0),
                            harmful_count=payload.get("harmful_count", 0),
                            metadata=payload.get("metadata", {})
                        )

                    playbook.bullets[bullet.id] = bullet
                    if bullet.section not in playbook.sections:
                        playbook.sections[bullet.section] = []
                    if bullet.id not in playbook.sections[bullet.section]:
                        playbook.sections[bullet.section].append(bullet.id)

                loaded += len(points)
                offset = page.get("next_offset")
                if offset is None:
                    break

            logger.info("playbook_loaded_from_vector_db",
                       collection=collection_name,
                       bullets_loaded=len(playbook.bullets))

        except Exception as e:
            logger.error("playbook_load_failed",
                        collection=collection_name,
                        error=str(e))
            raise

        return playbook

    def retrieve_relevant_bullets(
        self,
        query: str,
        embedding_manager,
        vector_store,
        collection_name: str,
        limit: int = 5,
        score_threshold: float = 0.5
    ) -> List[Tuple[PlaybookBullet, float]]:
        """
        Retrieve bullets relevant to a query using semantic search

        Args:
            query: Search query
            embedding_manager: Embedding manager instance
            vector_store: Vector store instance
            collection_name: Qdrant collection name
            limit: Maximum number of bullets to retrieve
            score_threshold: Minimum similarity score

        Returns:
            List of (bullet, score) tuples, sorted by relevance
        """
        if not query:
            logger.warning("empty_query_for_bullet_retrieval")
            return []

        logger.debug("retrieving_relevant_bullets",
                    collection=collection_name,
                    query=query[:100],
                    limit=limit)

        try:
            query_vector = embedding_manager.embed_query(query)
        except Exception as e:
            logger.error("bullet_query_embedding_failed",
                        query=query[:100],
                        error=str(e))
            return []

        try:
            results = vector_store.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist(),
                limit=limit,
                score_threshold=score_threshold
            )
        except Exception as e:
            logger.error("bullet_search_failed",
                        collection=collection_name,
                        error=str(e))
            return []

        relevant_bullets: List[Tuple[PlaybookBullet, float]] = []
        for hit in results:
            payload = hit.get("payload") or {}
            score = hit.get("score", 0.0)

            if "id" in payload and "section" in payload and "content" in payload:
                bullet = PlaybookBullet.from_dict(payload)
            else:
                bullet = PlaybookBullet(
                    id=payload.get("bullet_id", str(hit.get("id"))),
                    section=payload.get("section", "strategies_and_hard_rules"),
                    content=payload.get("content", ""),
                    helpful_count=payload.get("helpful_count", 0),
                    harmful_count=payload.get("harmful_count", 0),
                    metadata=payload.get("metadata", {})
                )

            relevant_bullets.append((bullet, score))

        logger.info("relevant_bullets_retrieved",
                   collection=collection_name,
                   results=len(relevant_bullets),
                   top_score=relevant_bullets[0][1] if relevant_bullets else 0)

        return relevant_bullets

    def delete_bullet_from_vector_db(
        self,
        bullet_id: str,
        vector_store,
        collection_name: str
    ) -> bool:
        """
        Delete a bullet from vector database

        Args:
            bullet_id: Bullet identifier
            vector_store: Vector store instance
            collection_name: Qdrant collection name

        Returns:
            True if successful
        """
        try:
            vector_store.delete_points(
                collection_name=collection_name,
                point_ids=[bullet_id]
            )
            logger.debug("bullet_deleted_from_vector_db",
                        bullet_id=bullet_id,
                        collection=collection_name)
            return True
        except Exception as e:
            logger.error("bullet_deletion_failed",
                        bullet_id=bullet_id,
                        collection=collection_name,
                        error=str(e))
            return False

    def get_bullet_by_id(self, bullet_id: str) -> Optional[PlaybookBullet]:
        """Get a bullet by its ID"""
        return self.bullets.get(bullet_id)

    def get_bullets_by_section(self, section: str) -> List[PlaybookBullet]:
        """Get all bullets in a section"""
        bullet_ids = self.sections.get(section, [])
        return [self.bullets[bid] for bid in bullet_ids if bid in self.bullets]

    def get_all_bullets(self) -> List[PlaybookBullet]:
        """Get all bullets"""
        return list(self.bullets.values())

    def get_bullet_count(self) -> int:
        """Get total number of bullets"""
        return len(self.bullets)

    def mark_bullet_helpful(self, bullet_id: str) -> bool:
        """Mark a bullet as helpful"""
        if bullet_id not in self.bullets:
            logger.warning("bullet_not_found_for_helpful_mark", bullet_id=bullet_id)
            return False

        self.bullets[bullet_id].helpful_count += 1
        logger.debug("bullet_marked_helpful",
                    bullet_id=bullet_id,
                    helpful_count=self.bullets[bullet_id].helpful_count)
        return True

    def mark_bullet_harmful(self, bullet_id: str) -> bool:
        """Mark a bullet as harmful"""
        if bullet_id not in self.bullets:
            logger.warning("bullet_not_found_for_harmful_mark", bullet_id=bullet_id)
            return False

        self.bullets[bullet_id].harmful_count += 1
        logger.debug("bullet_marked_harmful",
                    bullet_id=bullet_id,
                    harmful_count=self.bullets[bullet_id].harmful_count)
        return True

    def apply_bullet_feedback(self, bullet_feedback: Any) -> List[str]:
        """
        Apply feedback tags to bullets based on trajectory

        Args:
            bullet_feedback: Dict {bullet_id: tag} or List[{bullet_id, tag}]
        """
        if not bullet_feedback:
            return []

        if isinstance(bullet_feedback, list):
            feedback_dict = {
                item.get("bullet_id"): item.get("tag")
                for item in bullet_feedback
                if item.get("bullet_id")
            }
        elif isinstance(bullet_feedback, dict):
            feedback_dict = bullet_feedback
        else:
            logger.warning("bullet_feedback_invalid_type", type=str(type(bullet_feedback)))
            return []

        updated_ids = []
        for bullet_id, tag in feedback_dict.items():
            if tag == "helpful":
                if self.mark_bullet_helpful(bullet_id):
                    updated_ids.append(bullet_id)
            elif tag == "harmful":
                if self.mark_bullet_harmful(bullet_id):
                    updated_ids.append(bullet_id)

        logger.info("bullet_feedback_applied",
                   total_bullets=len(updated_ids))
        return updated_ids
