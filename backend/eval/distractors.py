"""Deterministic synthetic candidate profiles used to grow the pool for retrieval evaluation."""

from __future__ import annotations

import random

from app.models import CandidateProfile

# (title, skills, domains). Some are deliberately close to tech roles (PHP/MySQL, QA, network, SAP) to make
# retrieval non-trivial.
ARCHETYPES: list[tuple[str, list[str], list[str]]] = [
    ("Registered Nurse", ["Patient Care", "ICU", "Phlebotomy", "Triage", "Electronic Health Records"], ["healthcare"]),
    ("Accountant", ["IFRS", "Audit", "SAP FI", "Excel", "Tax Reporting", "Payroll"], ["finance", "accounting"]),
    ("Sales Representative", ["Salesforce", "Negotiation", "CRM", "Prospecting", "B2B Sales"], ["sales"]),
    ("Primary School Teacher", ["Classroom Management", "Curriculum Design", "Pedagogy"], ["education"]),
    ("Automotive Mechanic", ["Engine Diagnostics", "Brake Systems", "Welding", "Hydraulics"], ["automotive"]),
    ("HR Officer", ["Recruitment", "Payroll", "Labour Law", "Onboarding", "HRIS"], ["human resources"]),
    ("Graphic Designer", ["Photoshop", "Illustrator", "Figma", "Typography", "Branding"], ["design"]),
    ("Chef", ["Menu Planning", "Food Safety", "Pastry", "Kitchen Management"], ["hospitality"]),
    ("PHP Developer", ["PHP", "Laravel", "MySQL", "jQuery", "WordPress"], ["web development"]),
    ("QA Tester", ["Selenium", "Jira", "Test Plans", "Postman", "Manual Testing"], ["software testing"]),
    ("Network Administrator", ["Cisco", "CCNA", "Firewalls", "VPN", "Windows Server"], ["networking"]),
    ("SAP Consultant", ["SAP MM", "SAP SD", "ABAP", "Business Process Mapping"], ["erp"]),
    ("iOS Developer", ["Swift", "SwiftUI", "Xcode", "Core Data", "Git"], ["mobile development"]),
    ("Civil Engineer", ["AutoCAD", "Structural Analysis", "Revit", "Project Management"], ["construction"]),
    ("Marketing Manager", ["SEO", "Google Analytics", "Content Strategy", "Social Media"], ["marketing"]),
]


def distractor_profiles(count: int, seed: int = 42) -> list[CandidateProfile]:
    rng = random.Random(seed)
    profiles = []
    for _ in range(count):
        title, skills, domains = rng.choice(ARCHETYPES)
        chosen = rng.sample(skills, k=rng.randint(3, len(skills)))
        start_year = rng.randint(2012, 2023)
        profiles.append(
            CandidateProfile.model_validate(
                {
                    "professional_title": title,
                    "domains": domains,
                    "skills": [{"name": s} for s in chosen],
                    "experiences": [
                        {
                            "company": f"Company {rng.randint(1, 999)}",
                            "job_title": title,
                            "dates": {"start_date": f"{start_year}-01-01"},
                            "current": True,
                            "responsibilities": [f"Worked with {', '.join(chosen[:3])}"],
                            "domains": domains,
                        }
                    ],
                }
            )
        )
    return profiles
