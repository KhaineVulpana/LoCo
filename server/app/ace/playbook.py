"""
ACE Playbook - Structured context storage with bullets
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import structlog

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

    def deduplicate(self, threshold: float = 0.85):
        """
        Remove duplicate bullets using semantic similarity

        Args:
            threshold: Similarity threshold for considering duplicates
        """
        # This would use embedding-based similarity in production
        # For now, simple exact match deduplication
        seen_content = {}
        to_remove = []

        for bullet_id, bullet in self.bullets.items():
            content_normalized = bullet.content.lower().strip()

            if content_normalized in seen_content:
                # Merge counts into the existing one
                existing_id = seen_content[content_normalized]
                self.bullets[existing_id].helpful_count += bullet.helpful_count
                self.bullets[existing_id].harmful_count += bullet.harmful_count
                to_remove.append(bullet_id)
            else:
                seen_content[content_normalized] = bullet_id

        for bullet_id in to_remove:
            self.remove_bullet(bullet_id)

        if to_remove:
            logger.info("deduplication_complete", removed_count=len(to_remove))

    def prune_harmful(self, threshold: int = 3):
        """Remove bullets that have been marked harmful too many times"""
        to_remove = []

        for bullet_id, bullet in self.bullets.items():
            if bullet.harmful_count >= threshold:
                to_remove.append(bullet_id)

        for bullet_id in to_remove:
            self.remove_bullet(bullet_id)

        if to_remove:
            logger.info("harmful_bullets_pruned", count=len(to_remove))
