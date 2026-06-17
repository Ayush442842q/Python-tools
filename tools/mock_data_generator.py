#!/usr/bin/env python3
"""
Mock Data Generator - Generates realistic random profile data (names, emails, addresses, companies, jobs).
Supports JSON, CSV, and XML output formats, making it ideal for database seeding and API testing.
"""

import argparse
import csv
import io
import json
import random
import sys
import uuid
import xml.etree.ElementTree as ET

# Embedded datasets for generating realistic data without third-party dependencies
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Elizabeth",
    "William", "Linda", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Andrew", "Kimberly", "Paul", "Emily", "Joshua", "Donna",
    "Kenneth", "Michelle", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker"
]

DOMAINS = ["example.com", "mockmail.net", "testmail.org", "company.io", "webmail.com", "service.co"]

STREET_NAMES = [
    "Broadway", "Main St", "Oak Ave", "Pine St", "Maple Dr", "Cedar Rd", "Elm St",
    "Park Ln", "Hill St", "Washington St", "Lake Dr", "Sunset Blvd", "River Rd", "Forest Ave"
]

CITIES = [
    ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"), ("Chicago", "IL", "60601"),
    ("Houston", "TX", "77001"), ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"), ("Dallas", "TX", "75201"),
    ("San Jose", "CA", "95101"), ("Austin", "TX", "78701"), ("Jacksonville", "FL", "32201"),
    ("Fort Worth", "TX", "76101"), ("Columbus", "OH", "43201"), ("Charlotte", "NC", "28201")
]

COMPANIES = [
    "TechCorp", "InnoSystems", "ApexSolutions", "CloudScale", "QuantumData", "NovusLabs",
    "VortexGroup", "ElementHQ", "SynergyCo", "CoreTech", "StellarDynamics", "InfiniLink"
]

JOB_TITLES = [
    "Software Engineer", "Product Manager", "Data Analyst", "UX Designer", "DevOps Engineer",
    "Marketing Lead", "HR Specialist", "Sales Director", "Systems Architect", "Financial Analyst",
    "QA Engineer", "Security Consultant", "Database Administrator", "Technical Writer"
]

def generate_record():
    """Generates a single random mock profile record."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    company = random.choice(COMPANIES)
    city_info = random.choice(CITIES)
    
    # Derivations
    username = f"{first.lower()}{random.randint(10, 99)}"
    email = f"{first.lower()}.{last.lower()}@{random.choice(DOMAINS)}"
    phone = f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"
    street_num = random.randint(100, 9999)
    address = f"{street_num} {random.choice(STREET_NAMES)}, {city_info[0]}, {city_info[1]} {city_info[2]}"
    ip_addr = f"{random.randint(1, 254)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    
    return {
        "id": str(uuid.uuid4())[:8],
        "name": f"{first} {last}",
        "username": username,
        "email": email,
        "phone": phone,
        "address": address,
        "company": company,
        "job_title": random.choice(JOB_TITLES),
        "ip_address": ip_addr
    }

def to_csv(records):
    """Formats records to CSV string."""
    output = io.StringIO()
    if not records:
        return ""
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()

def to_xml(records):
    """Formats records to XML string."""
    root = ET.Element("dataset")
    for r in records:
        record_node = ET.SubElement(root, "record")
        for key, val in r.items():
            child = ET.SubElement(record_node, key)
            child.text = str(val)
    
    # Beautifully indent
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        # indent added in Python 3.9
        pass
        
    return ET.tostring(root, encoding="utf-8").decode("utf-8")

def main():
    parser = argparse.ArgumentParser(
        description="Mock Data Generator - Create sample user data sets in JSON, CSV, or XML format."
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=10,
        help="Number of records to generate (default: 10)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["json", "csv", "xml"],
        default="json",
        help="Output format style (default: json)"
    )
    parser.add_argument(
        "-o", "--output",
        help="File path to save the generated mock data"
    )

    args = parser.parse_args()

    if args.count <= 0:
        print("Error: Count must be a positive integer.", file=sys.stderr)
        return 1

    records = [generate_record() for _ in range(args.count)]

    # Format result
    if args.format == "json":
        output_str = json.dumps(records, indent=2)
    elif args.format == "csv":
        output_str = to_csv(records)
    elif args.format == "xml":
        output_str = to_xml(records)
    else:
        output_str = ""

    # Write output
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str)
            print(f"[+] Successfully generated {args.count} records and saved to {args.output}")
        except Exception as e:
            print(f"Error saving to file: {e}", file=sys.stderr)
            return 1
    else:
        print(output_str)

    return 0

if __name__ == "__main__":
    sys.exit(main())
