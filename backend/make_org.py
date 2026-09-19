from app.core.database import SessionLocal
from app.models.user import Organization

db = SessionLocal()

# Create an organization if it doesn't exist
org = db.query(Organization).filter(Organization.slug == "test-owner").first()
if not org:
    org = Organization(name="Test Owner LLC", slug="test-owner")
    db.add(org)
    db.commit()
    db.refresh(org)
    print(f"Created organization: id={org.id}, name={org.name}")
else:
    print(f"Organization already exists: id={org.id}, name={org.name}")

db.close()