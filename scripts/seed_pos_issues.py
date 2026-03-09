import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import db_manager
from app.models.models import POSIssue
from app.core.logging import logger

DATASET_FILE = Path(__file__).parent.parent / "improvement" / "pos_issue_dataset.md"

def parse_issues():
    if not DATASET_FILE.exists():
        logger.error(f"Dataset file not found at {DATASET_FILE}")
        return []

    issues = []
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    categories = content.split("## Category: ")
    for cat_block in categories[1:]:
        lines = cat_block.strip().split("\n")
        category_name = lines[0].strip()
        
        current_issue = None
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("---") or line.startswith("("):
                continue
                
            if line.startswith("Issue "):
                if current_issue:
                    issues.append(current_issue)
                # Parse "Issue 1: Cannot login to POS"
                parts = line.split(":", 1)
                issue_num = parts[0].replace("Issue", "").strip()
                problem_name = parts[1].strip() if len(parts) > 1 else ""
                current_issue = {
                    "problem_id": f"ISSUE_{issue_num.zfill(3)}",
                    "problem_name": problem_name,
                    "category": category_name,
                    "symptoms": "",
                    "root_causes": "",
                    "fix_steps": ""
                }
            elif current_issue and line.startswith("Symptoms:"):
                current_issue["symptoms"] = line.replace("Symptoms:", "").strip()
            elif current_issue and line.startswith("Root cause:"):
                current_issue["root_causes"] = line.replace("Root cause:", "").strip()
            elif current_issue and line.startswith("Fix:"):
                current_issue["fix_steps"] = line.replace("Fix:", "").strip()
                
        if current_issue:
            issues.append(current_issue)

    return issues

def seed_db():
    issues = parse_issues()
    if not issues:
        logger.warning("No issues parsed to seed.")
        return

    session = db_manager.get_session()
    try:
        added_count = 0
        for issue_data in issues:
            existing = session.query(POSIssue).filter_by(problem_id=issue_data["problem_id"]).first()
            if not existing:
                new_issue = POSIssue(
                    problem_id=issue_data["problem_id"],
                    problem_name=issue_data["problem_name"],
                    category=issue_data["category"],
                    symptoms=issue_data["symptoms"],
                    root_causes=issue_data["root_causes"],
                    fix_steps=issue_data["fix_steps"]
                )
                session.add(new_issue)
                added_count += 1
        
        session.commit()
        logger.info(f"Successfully seeded {added_count} new POS issues into the database.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed db: {e}")
    finally:
        db_manager.Session.remove()

if __name__ == "__main__":
    db_manager._init_db()  # This will create tables if they don't exist
    seed_db()
