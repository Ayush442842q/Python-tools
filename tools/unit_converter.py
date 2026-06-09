#!/usr/bin/env python3
"""
Advanced CLI Unit Converter - A utility to convert measurements between various units.

Features:
- Categories supported: Length, Mass/Weight, Temperature, Data Storage, Speed, and Time.
- Supports both direct command line arguments and a friendly interactive menu mode.
- Zero external dependencies.
"""

import argparse
import sys

# Define unit conversion systems
# Values are scale factors relative to the category's base unit.

UNITS = {
    'length': {
        'base': 'm',
        'desc': 'Length / Distance',
        'factors': {
            'm': 1.0,           # Meter (Base)
            'km': 1000.0,       # Kilometer
            'cm': 0.01,         # Centimeter
            'mm': 0.001,        # Millimeter
            'mi': 1609.344,     # Mile
            'yd': 0.9144,       # Yard
            'ft': 0.3048,       # Foot
            'in': 0.0254,       # Inch
        }
    },
    'mass': {
        'base': 'g',
        'desc': 'Mass / Weight',
        'factors': {
            'g': 1.0,           # Gram (Base)
            'kg': 1000.0,       # Kilogram
            'mg': 0.001,        # Milligram
            'lb': 453.59237,    # Pound
            'oz': 28.349523,    # Ounce
            'ton': 1000000.0,   # Metric Ton
        }
    },
    'data': {
        'base': 'B',
        'desc': 'Data Storage (Decimal / SI base 1000)',
        'factors': {
            'B': 1.0,           # Byte (Base)
            'KB': 1000.0,       # Kilobyte
            'MB': 1000.0 ** 2,  # Megabyte
            'GB': 1000.0 ** 3,  # Gigabyte
            'TB': 1000.0 ** 4,  # Terabyte
            'KiB': 1024.0,      # Kibibyte (Binary base 1024)
            'MiB': 1024.0 ** 2, # Mebibyte
            'GiB': 1024.0 ** 3, # Gibibyte
            'TiB': 1024.0 ** 4, # Tebibyte
        }
    },
    'speed': {
        'base': 'm/s',
        'desc': 'Speed / Velocity',
        'factors': {
            'm/s': 1.0,         # Meters per second (Base)
            'km/h': 1 / 3.6,    # Kilometers per hour
            'mph': 0.44704,     # Miles per hour
            'knots': 0.514444,  # Knots
        }
    },
    'time': {
        'base': 's',
        'desc': 'Time',
        'factors': {
            's': 1.0,           # Second (Base)
            'ms': 0.001,        # Millisecond
            'min': 60.0,        # Minute
            'h': 3600.0,        # Hour
            'd': 86400.0,       # Day
            'w': 604800.0,      # Week
            'y': 31536000.0,    # Year (365 days)
        }
    }
}

def convert_temperature(val, from_unit, to_unit):
    """Special handling for temperature conversions."""
    from_unit = from_unit.upper()
    to_unit = to_unit.upper()
    
    # Standardize to Celsius first
    if from_unit == 'C':
        c = val
    elif from_unit == 'F':
        c = (val - 32) * 5/9
    elif from_unit == 'K':
        c = val - 273.15
    else:
        raise ValueError(f"Unknown temperature unit: {from_unit}")
        
    # Convert Celsius to target
    if to_unit == 'C':
        return c
    elif to_unit == 'F':
        return (c * 9/5) + 32
    elif to_unit == 'K':
        return c + 273.15
    else:
        raise ValueError(f"Unknown temperature unit: {to_unit}")

def convert(val, from_unit, to_unit):
    """Converts a value from one unit to another."""
    # Check temperature
    temp_units = {'C', 'F', 'K', 'CELSIUS', 'FAHRENHEIT', 'KELVIN'}
    if from_unit.upper() in temp_units or to_unit.upper() in temp_units:
        # Map long names to shorthand
        mapping = {'CELSIUS': 'C', 'FAHRENHEIT': 'F', 'KELVIN': 'K'}
        u_from = mapping.get(from_unit.upper(), from_unit.upper())
        u_to = mapping.get(to_unit.upper(), to_unit.upper())
        return convert_temperature(val, u_from, u_to), 'temperature'

    # Find the category
    for cat_name, cat_data in UNITS.items():
        factors = cat_data['factors']
        # Case insensitive check
        matching_from = next((k for k in factors if k.lower() == from_unit.lower()), None)
        matching_to = next((k for k in factors if k.lower() == to_unit.lower()), None)
        
        if matching_from and matching_to:
            # Convert to base unit, then to target unit
            val_in_base = val * factors[matching_from]
            val_in_target = val_in_base / factors[matching_to]
            return val_in_target, cat_name

    raise ValueError(f"Invalid conversion path from '{from_unit}' to '{to_unit}'. Units must belong to the same category.")

def list_units():
    """Print all available categories and units."""
    print("=" * 60)
    print("Available Unit Categories and Units")
    print("=" * 60)
    for cat_name, cat_data in UNITS.items():
        units_str = ", ".join(cat_data['factors'].keys())
        print(f"{cat_data['desc']} ({cat_name}):")
        print(f"  Units: {units_str}")
        print(f"  Base:  {cat_data['base']}")
        print()
    print("Temperature (temperature):")
    print("  Units: C, F, K")
    print("=" * 60)

def run_interactive():
    """Run interactive CLI menu."""
    print("=" * 60)
    print("           CLI Unit Converter - Interactive Mode")
    print("=" * 60)
    
    categories = list(UNITS.keys()) + ['temperature']
    
    while True:
        print("\nSelect a category:")
        for idx, cat in enumerate(categories, 1):
            desc = UNITS[cat]['desc'] if cat in UNITS else 'Temperature (C, F, K)'
            print(f"  {idx}. {desc}")
        print("  0. Exit")
        
        try:
            choice = input("\nEnter choice (0-6): ").strip()
            if choice == '0' or not choice:
                print("Goodbye!")
                break
                
            idx = int(choice) - 1
            if idx < 0 or idx >= len(categories):
                print("Invalid choice, try again.")
                continue
                
            selected_cat = categories[idx]
            
            # Print available units
            if selected_cat == 'temperature':
                available_units = ['C', 'F', 'K']
                print("\nAvailable Temperature Units: C (Celsius), F (Fahrenheit), K (Kelvin)")
            else:
                available_units = list(UNITS[selected_cat]['factors'].keys())
                print(f"\nAvailable Units: {', '.join(available_units)}")
                
            from_unit = input("Convert from unit: ").strip()
            if from_unit.lower() not in [u.lower() for u in available_units]:
                print(f"Invalid unit '{from_unit}' for category '{selected_cat}'.")
                continue
                
            to_unit = input("Convert to unit: ").strip()
            if to_unit.lower() not in [u.lower() for u in available_units]:
                print(f"Invalid unit '{to_unit}' for category '{selected_cat}'.")
                continue
                
            val_str = input("Enter value: ").strip()
            val = float(val_str)
            
            res, _ = convert(val, from_unit, to_unit)
            print(f"\n---> {val} {from_unit} = {res:.6g} {to_unit}")
            print("-" * 40)
            
        except ValueError:
            print("Error: Please enter numeric values where expected.")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Advanced CLI Unit Converter - A simple yet robust conversion tool")
    parser.add_argument("value", type=float, nargs="?", help="Value to convert")
    parser.add_argument("--from", dest="from_unit", help="Unit to convert from (e.g. km, C, MB)")
    parser.add_argument("--to", dest="to_unit", help="Unit to convert to (e.g. miles, F, GB)")
    parser.add_argument("-l", "--list", action="store_true", help="List all supported categories and units")

    args = parser.parse_args()

    if args.list:
        list_units()
        return 0

    if args.value is not None:
        if not args.from_unit or not args.to_unit:
            print("Error: Direct conversion requires both --from and --to arguments.")
            print("Usage example: python unit_converter.py 100 --from km --to mi")
            return 1
            
        try:
            result, category = convert(args.value, args.from_unit, args.to_unit)
            print(f"{args.value} {args.from_unit} = {result:.6g} {args.to_unit} ({category})")
            return 0
        except ValueError as e:
            print(f"Error: {e}")
            return 1
            
    # Default to interactive mode
    run_interactive()
    return 0

if __name__ == "__main__":
    sys.exit(main())
