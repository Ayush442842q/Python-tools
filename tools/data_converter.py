#!/usr/bin/env python3
import argparse
import os
import sys
import json
import csv

class DataConverter:
    def __init__(self):
        pass
    
    def csv_to_json(self, csv_file, json_file):
        """Convert CSV file to JSON format"""
        try:
            data = []
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"Converted {csv_file} to {json_file}")
            return True
        except Exception as e:
            print(f"Error converting file: {e}")
            return False
    
    def json_to_csv(self, json_file, csv_file):
        """Convert JSON file to CSV format"""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if data and isinstance(data, list):
                with open(csv_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                
                print(f"Converted {json_file} to {csv_file}")
                return True
            else:
                print("Invalid JSON format for CSV conversion")
                return False
        except Exception as e:
            print(f"Error converting file: {e}")
            return False

def main():
    # Simple data converter
    print("Data Converter Tool")
    print("Use this tool to convert between CSV and JSON formats")

if __name__ == "__main__":
    main()