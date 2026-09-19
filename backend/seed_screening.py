"""Seed the screening_providers catalog. Run once."""
from app.core.database import SessionLocal
from app.models.screening import ScreeningProvider

PROVIDERS = [
    {
        "slug": "smartmove",
        "name": "TransUnion SmartMove",
        "description": "Most widely used tenant screening. Credit, criminal, eviction report.",
        "pricing_info": "$25 - $49 per screening (renter pays)",
        "api_docs_url": "https://www.mysmartmove.com",
    },
    {
        "slug": "experian",
        "name": "Experian Connect",
        "description": "Full API access. Credit + rental history + VantageScore 4.0.",
        "pricing_info": "Free for landlords, renter pays ~$35",
        "api_docs_url": "https://www.experian.com/connect",
    },
    {
        "slug": "equifax",
        "name": "Equifax Smart Screen",
        "description": "Focused on criminal background checks and credit.",
        "pricing_info": "Varies",
        "api_docs_url": "https://www.equifax.com",
    },
]

db = SessionLocal()
for p in PROVIDERS:
    existing = db.query(ScreeningProvider).filter(ScreeningProvider.slug == p["slug"]).first()
    if existing:
        print(f"Already exists: {p['slug']}")
        continue
    db.add(ScreeningProvider(**p))
    print(f"Added: {p['slug']}")
db.commit()
db.close()
print("Done.")