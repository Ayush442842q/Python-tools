#!/usr/bin/env python3
"""
Data Serialization Benchmarker

Benchmark the performance (serialization time, deserialization time, output size)
of different data serialization formats (JSON, JSONL, XML, YAML, CSV, Pickle, MessagePack)
across different data profiles and structures.

Usage:
    python tools/serialization_benchmarker.py [options]

Requirements:
    - Python 3.6+
    - Optional: pyyaml (for YAML), msgpack (for MessagePack)
"""

import sys
import os
import time
import json
import pickle
import csv
import io
import argparse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple, Callable, Optional, Union

# Try to import optional packages
try:
    import yaml
except ImportError:
    yaml = None # type: ignore

try:
    import msgpack
except ImportError:
    msgpack = None # type: ignore

# Sample datasets
FLAT_DATA = [
    {
        "id": i,
        "name": f"User_{i}",
        "email": f"user_{i}@example.com",
        "active": i % 2 == 0,
        "score": 85.5 + i * 0.1,
        "role": "admin" if i % 10 == 0 else "user"
    }
    for i in range(1000)
]

NESTED_DATA = {
    "project": "Serialization Benchmark",
    "version": 1.0,
    "metadata": {
        "creator": "Antigravity Code Assistant",
        "timestamp": int(time.time()),
        "tags": ["benchmark", "serialization", "python", "performance"]
    },
    "runs": [
        {
            "id": i,
            "metrics": {
                "cpu_percent": 12.5 * i,
                "memory_mb": 256 + i * 16,
                "disk_io": [1024, 2048, 4096]
            },
            "snapshots": [
                {"name": f"snap_{i}_A", "hash": "abc123xyz"},
                {"name": f"snap_{i}_B", "hash": "def456uvw"}
            ]
        }
        for i in range(100)
    ]
}

# XML Helper functions
def dict_to_xml(tag: str, d: Any) -> str:
    """Helper to convert dictionaries/lists into simple XML string structures."""
    def _to_xml_element(parent: ET.Element, key: str, val: Any):
        # Normalize key names to be valid XML tags
        clean_key = str(key).replace(" ", "_").replace("[", "").replace("]", "").replace("@", "")
        if not clean_key or clean_key[0].isdigit():
            clean_key = f"item_{clean_key}"
            
        elem = ET.SubElement(parent, clean_key)
        if isinstance(val, dict):
            for k, v in val.items():
                _to_xml_element(elem, k, v)
        elif isinstance(val, list):
            for item in val:
                _to_xml_element(elem, "item", item)
        else:
            elem.text = str(val)

    root = ET.Element(tag)
    if isinstance(d, dict):
        for k, v in d.items():
            _to_xml_element(root, k, v)
    elif isinstance(d, list):
        for item in d:
            _to_xml_element(root, "item", item)
    return ET.tostring(root, encoding="utf-8").decode("utf-8")

def xml_to_dict(xml_str: str) -> dict:
    """Simple XML to dict converter (for deserialization benchmarking)."""
    def _element_to_dict(elem: ET.Element) -> Any:
        children = list(elem)
        if not children:
            text = elem.text
            if not text:
                return None
            # Try to cast values
            if text.lower() == "true":
                return True
            if text.lower() == "false":
                return False
            try:
                if "." in text:
                    return float(text)
                return int(text)
            except ValueError:
                return text
        
        # If there are children
        res = {}
        for child in children:
            val = _element_to_dict(child)
            tag = child.tag
            if tag in res:
                # If key exists, convert to list (heterogeneous elements)
                if not isinstance(res[tag], list):
                    res[tag] = [res[tag]]
                res[tag].append(val)
            else:
                res[tag] = val
        return res

    root = ET.fromstring(xml_str)
    return {root.tag: _element_to_dict(root)}

# Benchmarking runner
def run_benchmark(
    name: str, 
    data: Any, 
    serialize_fn: Callable[[Any], Union[str, bytes]], 
    deserialize_fn: Callable[[Union[str, bytes]], Any],
    iterations: int
) -> Dict[str, Any]:
    """Execute serialization and deserialization runs, returning performance stats."""
    
    # 1. Warm-up and size check
    serialized = serialize_fn(data)
    size_bytes = len(serialized) if isinstance(serialized, (bytes, bytearray)) else len(serialized.encode('utf-8'))
    
    # Verify deserialization correctness
    deserialized = deserialize_fn(serialized)
    
    # 2. Benchmark serialization
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = serialize_fn(data)
    ser_time = (time.perf_counter() - start_time) / iterations
    
    # 3. Benchmark deserialization
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = deserialize_fn(serialized)
    deser_time = (time.perf_counter() - start_time) / iterations
    
    return {
        "format": name,
        "size_kb": size_bytes / 1024.0,
        "ser_time_ms": ser_time * 1000.0,
        "deser_time_ms": deser_time * 1000.0,
        "ops_sec": 1.0 / (ser_time + deser_time)
    }

def print_bar_chart(results: List[Dict[str, Any]], metric_key: str, metric_name: str, reverse: bool = False):
    """Renders a simple Unicode horizontal bar chart in the terminal."""
    if not results:
        return
        
    # Sort results
    sorted_results = sorted(results, key=lambda x: x[metric_key], reverse=reverse)
    max_val = max(r[metric_key] for r in sorted_results)
    
    print(f"\nVisual Chart: {metric_name} (Shorter is better)")
    print("-" * 65)
    
    for r in sorted_results:
        val = r[metric_key]
        # Bar length (max 30 characters)
        bar_len = int((val / max_val) * 30) if max_val > 0 else 0
        bar = "█" * bar_len + "░" * (30 - bar_len)
        print(f"{r['format']:<15} | {bar} | {val:.4f}")

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark speed and compression of Python serialization formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--dataset", "-d",
        choices=["flat", "nested"],
        default="flat",
        help="Dataset profile to benchmark: 'flat' (flat table of rows) or 'nested' (deep hierarchy) (default: flat)"
    )
    parser.add_argument(
        "--loops", "-l",
        type=int,
        default=200,
        help="Number of iterations to run for benchmarking (default: 200)"
    )
    
    args = parser.parse_args()
    
    # Choose dataset
    data = FLAT_DATA if args.dataset == "flat" else NESTED_DATA
    is_flat = args.dataset == "flat"
    
    print(f"Data Profile Selected: {args.dataset.upper()}")
    print(f"Iterations:            {args.loops}")
    print("Preparing serialization drivers...")
    
    drivers: List[Tuple[str, Callable[[Any], Any], Callable[[Any], Any]]] = []
    
    # JSON driver
    drivers.append((
        "JSON",
        lambda d: json.dumps(d),
        lambda s: json.loads(s)
    ))
    
    # JSONL (JSON Lines) driver
    drivers.append((
        "JSONL",
        lambda d: "\n".join(json.dumps(x) for x in d) if isinstance(d, list) else json.dumps(d),
        lambda s: [json.loads(line) for line in s.split("\n") if line.strip()] if is_flat else json.loads(s)
    ))
    
    # Pickle driver (Binary)
    drivers.append((
        "Pickle (Binary)",
        lambda d: pickle.dumps(d),
        lambda b: pickle.loads(b)
    ))
    
    # XML driver
    drivers.append((
        "XML",
        lambda d: dict_to_xml("root", d),
        lambda s: xml_to_dict(s)
    ))
    
    # CSV driver (only supports flat lists of dicts)
    if is_flat:
        def serialize_csv(d_list: List[dict]) -> str:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=d_list[0].keys())
            writer.writeheader()
            writer.writerows(d_list)
            return output.getvalue()
            
        def deserialize_csv(s_data: str) -> List[dict]:
            input_io = io.StringIO(s_data)
            reader = csv.DictReader(input_io)
            # Standardize typing since CSV reads values as string
            rows = []
            for row in reader:
                typed_row = {}
                for k, v in row.items():
                    if v.lower() == "true":
                        typed_row[k] = True
                    elif v.lower() == "false":
                        typed_row[k] = False
                    else:
                        try:
                            if "." in v:
                                typed_row[k] = float(v)
                            else:
                                typed_row[k] = int(v)
                        except ValueError:
                            typed_row[k] = v
                rows.append(typed_row)
            return rows
            
        drivers.append(("CSV", serialize_csv, deserialize_csv))
        
    # Optional YAML driver
    if yaml:
        drivers.append((
            "YAML (PyYAML)",
            lambda d: yaml.dump(d),
            lambda s: yaml.safe_load(s)
        ))
    else:
        print("Note: 'pyyaml' is not installed. Skipping YAML benchmark. Install with 'pip install pyyaml'.")
        
    # Optional MessagePack driver
    if msgpack:
        drivers.append((
            "MessagePack",
            lambda d: msgpack.packb(d),
            lambda b: msgpack.unpackb(b)
        ))
    else:
        print("Note: 'msgpack' is not installed. Skipping MessagePack benchmark. Install with 'pip install msgpack'.")
        
    print("\nRunning benchmarks...")
    results = []
    
    for name, ser_fn, deser_fn in drivers:
        try:
            res = run_benchmark(name, data, ser_fn, deser_fn, args.loops)
            results.append(res)
            print(f" ✓ Completed {name}")
        except Exception as e:
            print(f" ✗ Failed {name}: {e}")
            
    if not results:
        print("Error: No benchmark runs succeeded.", file=sys.stderr)
        return 1
        
    # Render tabular report
    print("\n" + "="*80)
    print("BENCHMARK PERFORMANCE COMPARISON TABLE")
    print("="*80)
    print(f"{'Format':<20} | {'Size (KB)':<10} | {'Serialize (ms)':<15} | {'Deserialize (ms)':<18} | {'Ops/sec':<12}")
    print("-" * 80)
    
    # Sort results by throughput ops/sec desc
    sorted_results = sorted(results, key=lambda x: x["ops_sec"], reverse=True)
    for r in sorted_results:
        print(f"{r['format']:<20} | {r['size_kb']:<10.2f} | {r['ser_time_ms']:<15.4f} | {r['deser_time_ms']:<18.4f} | {r['ops_sec']:<12.1f}")
    print("="*80)
    
    # Render bar charts
    print_bar_chart(results, "ser_time_ms", "Serialization Time (ms)")
    print_bar_chart(results, "deser_time_ms", "Deserialization Time (ms)")
    print_bar_chart(results, "size_kb", "Serialized Size (KB)")
    
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
