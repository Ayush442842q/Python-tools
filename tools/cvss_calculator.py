"""
CVSS Score Calculator & Vector Parser
Calculates Common Vulnerability Scoring System (CVSS) v3.1 base score,
impact, and exploitability sub-scores from a vector string or interactive CLI menu.
"""
import argparse
import sys

# Metric definitions for CVSS v3.1
METRICS = {
    "AV": {
        "name": "Attack Vector (AV)",
        "choices": {
            "N": ("Network", 0.85),
            "A": ("Adjacent", 0.62),
            "L": ("Local", 0.55),
            "P": ("Physical", 0.20)
        }
    },
    "AC": {
        "name": "Attack Complexity (AC)",
        "choices": {
            "L": ("Low", 0.77),
            "H": ("High", 0.44)
        }
    },
    "PR": {
        "name": "Privileges Required (PR)",
        # Value depends on Scope (S)
        "choices": {
            "N": ("None", 0.85, 0.85),
            "L": ("Low", 0.62, 0.68),  # second value is if Scope is Changed
            "H": ("High", 0.27, 0.50)  # second value is if Scope is Changed
        }
    },
    "UI": {
        "name": "User Interaction (UI)",
        "choices": {
            "N": ("None", 0.85),
            "R": ("Required", 0.62)
        }
    },
    "S": {
        "name": "Scope (S)",
        "choices": {
            "U": ("Unchanged", "U"),
            "C": ("Changed", "C")
        }
    },
    "C": {
        "name": "Confidentiality (C)",
        "choices": {
            "H": ("High", 0.56),
            "L": ("Low", 0.22),
            "N": ("None", 0.0)
        }
    },
    "I": {
        "name": "Integrity (I)",
        "choices": {
            "H": ("High", 0.56),
            "L": ("Low", 0.22),
            "N": ("None", 0.0)
        }
    },
    "A": {
        "name": "Availability (A)",
        "choices": {
            "H": ("High", 0.56),
            "L": ("Low", 0.22),
            "N": ("None", 0.0)
        }
    }
}

def cvss_roundup(input_val):
    """Smallest number specified to one decimal place, equal to or greater than its input."""
    # Official CVSS roundup implementation
    int_input = int(round(input_val * 100000))
    if int_input % 10000 == 0:
        return int_input / 100000
    else:
        return (int(int_input / 10000) + 1) / 10

def calculate_cvss(vector_dict):
    """Calculate CVSS v3.1 scores from a dictionary of metric choices."""
    try:
        av = METRICS["AV"]["choices"][vector_dict["AV"]][1]
        ac = METRICS["AC"]["choices"][vector_dict["AC"]][1]
        scope = vector_dict["S"]
        
        # PR value depends on Scope
        pr_tuple = METRICS["PR"]["choices"][vector_dict["PR"]]
        pr = pr_tuple[2] if scope == "C" else pr_tuple[1]
        
        ui = METRICS["UI"]["choices"][vector_dict["UI"]][1]
        
        c = METRICS["C"]["choices"][vector_dict["C"]][1]
        i = METRICS["I"]["choices"][vector_dict["I"]][1]
        a = METRICS["A"]["choices"][vector_dict["A"]][1]
    except KeyError as e:
        raise ValueError(f"Missing or invalid metric value: {e}")
        
    # Exploitability
    exploitability = 8.22 * av * ac * pr * ui
    
    # Impact Subscore
    iss = 1 - (1 - c) * (1 - i) * (1 - a)
    
    if scope == "U":
        impact = 6.42 * iss
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
        
    # Base Score
    if impact <= 0:
        base_score = 0
    else:
        if scope == "U":
            base_score = cvss_roundup(min(impact + exploitability, 10))
        else:
            base_score = cvss_roundup(min(1.08 * (impact + exploitability), 10))
            
    return {
        "base_score": base_score,
        "impact": round(impact, 1),
        "exploitability": round(exploitability, 1),
        "iss": round(iss, 3)
    }

def get_severity(score):
    """Get CVSS severity qualitative rating."""
    if score == 0.0:
        return "None"
    elif 0.1 <= score <= 3.9:
        return "Low"
    elif 4.0 <= score <= 6.9:
        return "Medium"
    elif 7.0 <= score <= 8.9:
        return "High"
    else:
        return "Critical"

def parse_vector_string(vector_str):
    """Parse CVSS v3.1 vector string into dictionary of metric keys."""
    # Strip prefix if present
    if vector_str.upper().startswith("CVSS:3.1/"):
        vector_str = vector_str[9:]
    elif vector_str.upper().startswith("CVSS:3.0/"):
        vector_str = vector_str[9:]
        
    parts = vector_str.split("/")
    vector_dict = {}
    for part in parts:
        if not part.strip():
            continue
        if ":" not in part:
            raise ValueError(f"Invalid metric format (missing colon): '{part}'")
        k, v = part.split(":", 1)
        k, v = k.strip().upper(), v.strip().upper()
        if k in METRICS:
            if v in METRICS[k]["choices"]:
                vector_dict[k] = v
            else:
                raise ValueError(f"Invalid choice '{v}' for metric '{k}'")
                
    # Verify all mandatory metrics are present
    missing = [m for m in METRICS if m not in vector_dict]
    if missing:
        raise ValueError(f"Missing mandatory metrics: {', '.join(missing)}")
        
    return vector_dict

def interactive_wizard():
    """Prompt the user step-by-step to construct a CVSS vector."""
    print("CVSS v3.1 Base Score Interactive Wizard")
    print("=" * 45)
    print("Please answer the following questions to compute the score:\n")
    
    choices = {}
    # Iterate in the standard order of the vector string
    order = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    
    for metric_key in order:
        metric = METRICS[metric_key]
        print(f"--- {metric['name']} ---")
        options = []
        for choice_key, choice_val in metric["choices"].items():
            print(f"  [{choice_key}] {choice_val[0]}")
            options.append(choice_key)
            
        while True:
            user_input = input(f"Select choice ({'/'.join(options)}): ").strip().upper()
            if user_input in options:
                choices[metric_key] = user_input
                print()
                break
            print("[ERROR] Invalid choice. Please try again.")
            
    # Print summary
    vector_str = f"CVSS:3.1/" + "/".join(f"{k}:{choices[k]}" for k in order)
    return vector_str, choices

def main():
    parser = argparse.ArgumentParser(
        description="Calculate CVSS v3.1 base score and severity from vector string or interactive menu."
    )
    parser.add_argument(
        "vector",
        nargs="?",
        help="CVSS v3.1 vector string (e.g. 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H')."
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run step-by-step interactive wizard."
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        try:
            vector_str, vector_dict = interactive_wizard()
        except KeyboardInterrupt:
            print("\n[INFO] Wizard cancelled.")
            sys.exit(0)
    elif args.vector:
        vector_str = args.vector
        try:
            vector_dict = parse_vector_string(vector_str)
        except ValueError as e:
            print(f"[ERROR] Invalid vector string: {e}")
            sys.exit(1)
    else:
        # If no arguments are provided and not interactive, print help and run interactive as fallback if stdin is terminal
        if sys.stdin.isatty():
            try:
                vector_str, vector_dict = interactive_wizard()
            except KeyboardInterrupt:
                print("\n[INFO] Wizard cancelled.")
                sys.exit(0)
        else:
            parser.print_help()
            sys.exit(0)
            
    # Calculate and output results
    try:
        results = calculate_cvss(vector_dict)
    except Exception as e:
        print(f"[ERROR] Calculation failed: {e}")
        sys.exit(1)
        
    score = results["base_score"]
    severity = get_severity(score)
    
    print("-" * 55)
    print(f"CVSS v3.1 Vector: {vector_str}")
    print("-" * 55)
    print(f"Base Score:      {score:.1f}")
    print(f"Severity:        {severity}")
    print(f"Impact Subscore: {results['impact']:.1f}")
    print(f"Exploitability:  {results['exploitability']:.1f}")
    print("-" * 55)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
