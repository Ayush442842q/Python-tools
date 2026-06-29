#!/usr/bin/env python3
"""
JSON-LD Schema Generator & Validator
Generates or validates Schema.org structured data in JSON-LD format.
"""

import sys
import json
import argparse

# Schema templates and descriptions
SCHEMAS = {
    "1": {
        "name": "Article",
        "fields": [
            ("headline", "Headline/Title of the article", True, "My Awesome Article"),
            ("author_name", "Author Name", True, "John Doe"),
            ("author_type", "Author Type (Person/Organization)", True, "Person"),
            ("publisher_name", "Publisher Name", True, "My News Inc."),
            ("publisher_logo", "Publisher Logo URL", False, "https://example.com/logo.png"),
            ("datePublished", "Publication Date (YYYY-MM-DD)", True, "2026-06-29"),
            ("dateModified", "Modification Date (YYYY-MM-DD)", False, "2026-06-29"),
            ("description", "Brief Description", True, "An article about cool Python tools.")
        ]
    },
    "2": {
        "name": "Product",
        "fields": [
            ("name", "Product Name", True, "Ultimate Python Toolkit"),
            ("image", "Product Image URL", False, "https://example.com/product.jpg"),
            ("description", "Product Description", True, "A set of high-quality developer tools."),
            ("brand", "Brand Name", False, "Antigravity Corp"),
            ("price", "Price (decimal, e.g. 29.99)", True, "29.99"),
            ("priceCurrency", "Price Currency (e.g. USD, EUR)", True, "USD"),
            ("availability", "Availability (InStock/OutOfStock)", True, "InStock")
        ]
    },
    "3": {
        "name": "LocalBusiness",
        "fields": [
            ("name", "Business Name", True, "Downtown Coffee Shop"),
            ("image", "Business Photo URL", False, "https://example.com/shop.jpg"),
            ("telephone", "Phone Number", True, "+1-555-0199"),
            ("streetAddress", "Street Address", True, "123 Main St"),
            ("addressLocality", "City/Locality", True, "Metropolis"),
            ("addressRegion", "State/Region (e.g. NY)", True, "NY"),
            ("postalCode", "Postal Code", True, "10001"),
            ("addressCountry", "Country Code (e.g. US)", True, "US"),
            ("priceRange", "Price Range ($, $$, $$$)", False, "$$")
        ]
    },
    "4": {
        "name": "FAQPage",
        "fields": []  # FAQ requires loop for multiple Q&As
    }
}

def validate_json_ld(data):
    """Validates the structure of JSON-LD data."""
    errors = []
    warnings = []

    if "@context" not in data:
        errors.append("Missing '@context'. It should be 'https://schema.org'.")
    elif data["@context"] not in ["http://schema.org", "https://schema.org", "http://schema.org/", "https://schema.org/"]:
        warnings.append(f"Standard '@context' is 'https://schema.org', found '{data['@context']}'")

    if "@type" not in data:
        errors.append("Missing '@type' parameter defining the Schema type.")
        return errors, warnings

    schema_type = data["@type"]
    
    # Standard field validation for supported types
    if schema_type == "Article":
        required = ["headline", "author", "publisher", "datePublished"]
        for req in required:
            if req not in data:
                errors.append(f"Article is missing required field: '{req}'")
    elif schema_type == "Product":
        required = ["name", "description"]
        for req in required:
            if req not in data:
                errors.append(f"Product is missing required field: '{req}'")
        if "offers" not in data:
            warnings.append("Product should ideally have an 'offers' block for price/availability.")
    elif schema_type == "LocalBusiness":
        required = ["name", "address"]
        for req in required:
            if req not in data:
                errors.append(f"LocalBusiness is missing required field: '{req}'")
    elif schema_type == "FAQPage":
        if "mainEntity" not in data:
            errors.append("FAQPage is missing 'mainEntity' (list of Question objects).")
        else:
            questions = data["mainEntity"]
            if not isinstance(questions, list):
                errors.append("'mainEntity' must be a list of Questions.")
            else:
                for idx, q in enumerate(questions):
                    if q.get("@type") != "Question":
                        errors.append(f"Question at index {idx} has invalid type: '{q.get('@type')}'")
                    if "name" not in q:
                        errors.append(f"Question at index {idx} is missing the question text ('name').")
                    if "acceptedAnswer" not in q:
                        errors.append(f"Question at index {idx} is missing 'acceptedAnswer'.")
                    elif q["acceptedAnswer"].get("@type") != "Answer":
                        errors.append(f"Answer at index {idx} has invalid type: '{q['acceptedAnswer'].get('@type')}'")
                    elif "text" not in q["acceptedAnswer"]:
                        errors.append(f"Answer at index {idx} is missing 'text'.")

    return errors, warnings

def build_faq():
    """Interactively build an FAQ page schema."""
    print("\n--- Build FAQ Schema ---")
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": []
    }
    
    q_count = 1
    while True:
        print(f"\nQuestion #{q_count}:")
        question_text = input("Enter Question (or leave blank to finish): ").strip()
        if not question_text:
            if q_count == 1:
                print("FAQ must contain at least one question.")
                continue
            break
        
        answer_text = input("Enter Answer: ").strip()
        while not answer_text:
            print("Answer cannot be blank.")
            answer_text = input("Enter Answer: ").strip()
            
        q_obj = {
            "@type": "Question",
            "name": question_text,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": answer_text
            }
        }
        data["mainEntity"].append(q_obj)
        q_count += 1
        
    return data

def build_interactive(choice):
    """Interactively build a schema based on user selections."""
    schema_info = SCHEMAS[choice]
    print(f"\n--- Generating {schema_info['name']} Schema ---")
    
    data = {
        "@context": "https://schema.org",
        "@type": schema_info["name"]
    }
    
    # For address nesting in LocalBusiness
    address_data = {}
    
    for field_name, desc, required, default in schema_info["fields"]:
        req_str = " (Required)" if required else " (Optional)"
        def_str = f" [default: {default}]" if default else ""
        prompt = f"Enter {desc}{req_str}{def_str}: "
        
        val = input(prompt).strip()
        if not val and default:
            val = default
            
        if not val and required:
            while not val:
                print(f"Error: {desc} is required.")
                val = input(prompt).strip()
                if not val and default:
                    val = default
                    
        if val:
            # Handle nested objects
            if choice == "1" and field_name.startswith("author_"):
                if "author" not in data:
                    data["author"] = {}
                key = field_name.split("_")[1]
                if key == "name":
                    data["author"]["name"] = val
                elif key == "type":
                    data["author"]["@type"] = val
            elif choice == "1" and field_name.startswith("publisher_"):
                if "publisher" not in data:
                    data["publisher"] = {"@type": "Organization"}
                key = field_name.split("_")[1]
                if key == "name":
                    data["publisher"]["name"] = val
                elif key == "logo":
                    data["publisher"]["logo"] = {"@type": "ImageObject", "url": val}
            elif choice == "2" and field_name == "brand":
                data["brand"] = {"@type": "Brand", "name": val}
            elif choice == "2" and field_name in ["price", "priceCurrency", "availability"]:
                if "offers" not in data:
                    data["offers"] = {"@type": "Offer"}
                if field_name == "price":
                    try:
                        data["offers"]["price"] = float(val)
                    except ValueError:
                        data["offers"]["price"] = val
                elif field_name == "priceCurrency":
                    data["offers"]["priceCurrency"] = val
                elif field_name == "availability":
                    data["offers"]["availability"] = f"https://schema.org/{val}"
            elif choice == "3" and field_name in ["streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"]:
                address_data[field_name] = val
            else:
                data[field_name] = val
                
    if choice == "3" and address_data:
        address_data["@type"] = "PostalAddress"
        data["address"] = address_data
        
    return data

def main():
    parser = argparse.ArgumentParser(description="JSON-LD Schema Generator & Validator")
    parser.add_argument("-v", "--validate", help="Validate a JSON-LD file path or JSON string directly")
    parser.add_argument("-o", "--output", help="Save generated schema to file")
    args = parser.parse_args()

    # Mode: Validation
    if args.validate:
        try:
            # Check if it's a file path or raw string
            try:
                with open(args.validate, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (FileNotFoundError, OSError):
                content = args.validate
                
            data = json.loads(content)
            errors, warnings = validate_json_ld(data)
            
            print(f"Validation results for schema type: {data.get('@type', 'Unknown')}")
            print("-" * 50)
            if not errors and not warnings:
                print("✅ Schema is fully valid! No errors or warnings found.")
                sys.exit(0)
            
            if errors:
                print("❌ Errors found:")
                for err in errors:
                    print(f"  - {err}")
            if warnings:
                print("⚠️ Warnings found:")
                for warn in warnings:
                    print(f"  - {warn}")
            
            sys.exit(1 if errors else 0)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON format: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error validating: {e}")
            sys.exit(1)

    # Mode: Interactive Generation
    print("==============================================")
    print("  JSON-LD Schema Generator & Validator")
    print("==============================================")
    print("Select a schema type to generate:")
    print("1. Article (Blog, News, Scholarly)")
    print("2. Product (E-commerce listings)")
    print("3. LocalBusiness (Store, Restaurant, Office)")
    print("4. FAQPage (Questions & Answers list)")
    print("q. Exit")
    
    choice = input("\nEnter choice (1-4 or q): ").strip()
    if choice.lower() == 'q':
        print("Goodbye!")
        sys.exit(0)
        
    if choice not in SCHEMAS:
        print("Invalid choice.")
        sys.exit(1)
        
    if choice == "4":
        schema_json = build_faq()
    else:
        schema_json = build_interactive(choice)
        
    pretty_json = json.dumps(schema_json, indent=2)
    print("\nGenerated JSON-LD script:")
    print("=" * 60)
    print(pretty_json)
    print("=" * 60)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(pretty_json)
            print(f"💾 Saved schema to: {args.output}")
        except Exception as e:
            print(f"Error saving to file: {e}")
    else:
        save_choice = input("Would you like to save this to a file? (y/n): ").strip().lower()
        if save_choice == 'y':
            filename = input("Enter filename (e.g. schema.jsonld): ").strip()
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(pretty_json)
                    print(f"💾 Saved schema to: {filename}")
                except Exception as e:
                    print(f"Error saving to file: {e}")

if __name__ == "__main__":
    main()
