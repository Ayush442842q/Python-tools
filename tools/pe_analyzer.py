#!/usr/bin/env python3
"""
PE (Portable Executable) Header & Dependency Analyzer
=====================================================
A zero-dependency command-line utility to parse Windows Portable Executable (PE)
binaries (EXE, DLL, SYS). Decodes DOS headers, COFF file headers, Optional headers,
Data Directories, Section Headers, and Imports. Computes section Shannon entropy
to detect packing/obfuscation, and audits security flags (DEP, ASLR, etc.).

Author: Antigravity
License: MIT
"""

import os
import sys
import struct
import math
import json
import datetime
import argparse

# ANSI Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# PE Constants
PE_MACHINE = {
    0x014c: "Intel 386 (x86)",
    0x0200: "Intel Itanium (IA-64)",
    0x8664: "AMD64 (x64)",
    0x01c0: "ARM Little Endian",
    0xaa64: "ARM64"
}

PE_SUBSYSTEM = {
    0: "Unknown", 1: "Native", 2: "Windows GUI", 3: "Windows CUI (Console)",
    5: "OS/2 CUI", 7: "POSIX CUI", 9: "Windows CE GUI", 10: "EFI Application",
    11: "EFI Boot Service Driver", 12: "EFI Runtime Driver", 13: "EFI ROM",
    14: "Xbox", 16: "Windows Boot Application"
}

# DLL Characteristics
IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE = 0x0040 # ASLR
IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY = 0x0080 # Code Integrity
IMAGE_DLLCHARACTERISTICS_NX_COMPAT = 0x0100 # DEP/NX Compat
IMAGE_DLLCHARACTERISTICS_NO_ISOLATION = 0x0200 # No isolation (no manifest)
IMAGE_DLLCHARACTERISTICS_NO_SEH = 0x0400 # No Structured Exception Handling
IMAGE_DLLCHARACTERISTICS_NO_BIND = 0x0800 # Do not bind image
IMAGE_DLLCHARACTERISTICS_APPCONTAINER = 0x1000 # AppContainer
IMAGE_DLLCHARACTERISTICS_WDM_DRIVER = 0x2000 # WDM Driver
IMAGE_DLLCHARACTERISTICS_GUARD_CF = 0x4000 # Control Flow Guard (CFG)
IMAGE_DLLCHARACTERISTICS_TERMINAL_SERVER_AWARE = 0x8000

class PEParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.file_size = os.path.getsize(filepath)
        self.stream = open(filepath, 'rb')
        self.dos_header = {}
        self.coff_header = {}
        self.optional_header = {}
        self.sections = []
        self.imports = {}
        self.parse_pe()

    def __del__(self):
        if hasattr(self, 'stream') and self.stream:
            self.stream.close()

    def read_struct(self, format_str, offset):
        size = struct.calcsize(format_str)
        self.stream.seek(offset)
        data = self.stream.read(size)
        if len(data) < size:
            raise ValueError("Unexpected EOF while parsing structure.")
        return struct.unpack(format_str, data)

    def calculate_entropy(self, offset, size):
        """Calculate Shannon entropy of a file section to identify packing/encryption."""
        if size == 0:
            return 0.0
        self.stream.seek(offset)
        data = self.stream.read(size)
        if not data:
            return 0.0
        
        entropy = 0.0
        length = len(data)
        frequencies = [0] * 256
        for byte in data:
            frequencies[byte] += 1
            
        for count in frequencies:
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        return entropy

    def rva_to_offset(self, rva):
        """Map Relative Virtual Address (RVA) to raw file offset."""
        for sec in self.sections:
            v_start = sec['virtual_address']
            v_end = v_start + sec['virtual_size']
            if v_start <= rva < v_end:
                # Calculate file offset
                return sec['pointer_to_raw_data'] + (rva - v_start)
        return 0

    def parse_pe(self):
        # 1. DOS Header (64 bytes)
        dos_sig, = self.read_struct("<2s", 0)
        if dos_sig != b'MZ':
            raise ValueError("Invalid DOS Signature (Not MZ).")
        
        # e_lfanew is at offset 0x3C (60)
        e_lfanew, = self.read_struct("<I", 0x3C)
        self.dos_header['e_lfanew'] = e_lfanew

        # 2. PE Signature (4 bytes)
        pe_sig, = self.read_struct("<4s", e_lfanew)
        if pe_sig != b'PE\0\0':
            raise ValueError("Invalid PE Signature (Not PE\\0\\0).")

        # 3. COFF File Header (20 bytes)
        coff_offset = e_lfanew + 4
        # Format: Machine(H), NumSections(H), TimeDateStamp(I), PointerToSymbolTable(I), NumSymbols(I), SizeOfOptionalHeader(H), Characteristics(H)
        coff_fields = self.read_struct("<HHIIIHH", coff_offset)
        self.coff_header = {
            'machine_raw': coff_fields[0],
            'machine': PE_MACHINE.get(coff_fields[0], f"UNKNOWN_0x{coff_fields[0]:x}"),
            'number_of_sections': coff_fields[1],
            'timedate_stamp': coff_fields[2],
            'pointer_to_symbol_table': coff_fields[3],
            'number_of_symbols': coff_fields[4],
            'size_of_optional_header': coff_fields[5],
            'characteristics': coff_fields[6]
        }

        # 4. Optional Header
        opt_offset = coff_offset + 20
        # Optional Header magic determines PE32 (0x10b) vs PE32+ (0x20b, 64-bit)
        magic, = self.read_struct("<H", opt_offset)
        self.optional_header['magic'] = magic
        is_pe32_plus = magic == 0x20b

        # Parse PE32 / PE32+ Optional Header fields
        if is_pe32_plus:
            # PE32+ (64-bit)
            fmt = "<B B I I I I I Q Q I I H H H H H H I I I I H H Q Q Q Q I I"
            # Fields: MajorLinker(B), MinorLinker(B), SizeOfCode(I), SizeOfInitData(I), SizeOfUninitData(I),
            # AddressOfEntryPoint(I), BaseOfCode(I), ImageBase(Q), SectionAlign(I), FileAlign(I), MajorOS(H), MinorOS(H),
            # MajorImage(H), MinorImage(H), MajorSubsystem(H), MinorSubsystem(H), Win32Version(I), SizeOfImage(I),
            # SizeOfHeaders(I), CheckSum(I), Subsystem(H), DllCharacteristics(H), SizeOfStackReserve(Q), SizeOfStackCommit(Q),
            # SizeOfHeapReserve(Q), SizeOfHeapCommit(Q), LoaderFlags(I), NumberOfRvaAndSizes(I)
            fields = self.read_struct("<BBIIIIiQIIHHHHHHIIIIHHQQQQII", opt_offset)
            
            self.optional_header.update({
                'major_linker_version': fields[0],
                'minor_linker_version': fields[1],
                'size_of_code': fields[2],
                'size_of_initialized_data': fields[3],
                'size_of_uninitialized_data': fields[4],
                'address_of_entry_point': fields[5],
                'base_of_code': fields[6],
                'image_base': fields[7],
                'section_alignment': fields[8],
                'file_alignment': fields[9],
                'major_operating_system_version': fields[10],
                'minor_operating_system_version': fields[11],
                'major_subsystem_version': fields[14],
                'minor_subsystem_version': fields[15],
                'size_of_image': fields[17],
                'size_of_headers': fields[18],
                'checksum': fields[19],
                'subsystem_raw': fields[20],
                'subsystem': PE_SUBSYSTEM.get(fields[20], "Unknown"),
                'dll_characteristics': fields[21],
                'number_of_rva_and_sizes': fields[27]
            })
            data_directories_offset = opt_offset + 112
        else:
            # PE32 (32-bit)
            # PE32 optional header has standard BaseOfData field after BaseOfCode
            fields = self.read_struct("<BBIIIIIIIIIHHHHHHIIIIHHIIIIII", opt_offset)
            self.optional_header.update({
                'major_linker_version': fields[0],
                'minor_linker_version': fields[1],
                'size_of_code': fields[2],
                'size_of_initialized_data': fields[3],
                'size_of_uninitialized_data': fields[4],
                'address_of_entry_point': fields[5],
                'base_of_code': fields[6],
                'base_of_data': fields[7],
                'image_base': fields[8],
                'section_alignment': fields[9],
                'file_alignment': fields[10],
                'major_operating_system_version': fields[11],
                'minor_operating_system_version': fields[12],
                'major_subsystem_version': fields[15],
                'minor_subsystem_version': fields[16],
                'size_of_image': fields[18],
                'size_of_headers': fields[19],
                'checksum': fields[20],
                'subsystem_raw': fields[21],
                'subsystem': PE_SUBSYSTEM.get(fields[21], "Unknown"),
                'dll_characteristics': fields[22],
                'number_of_rva_and_sizes': fields[28]
            })
            data_directories_offset = opt_offset + 96

        # 5. Data Directories (each is VirtualAddress(I), Size(I))
        # Total directories is NumberOfRvaAndSizes (usually 16)
        num_dirs = self.optional_header['number_of_rva_and_sizes']
        data_dirs = []
        for i in range(num_dirs):
            offset = data_directories_offset + i * 8
            rva, size = self.read_struct("<II", offset)
            data_dirs.append({'rva': rva, 'size': size})
        self.optional_header['data_directories'] = data_dirs

        # 6. Section Headers (each is 40 bytes)
        sec_offset = data_directories_offset + num_dirs * 8
        num_sections = self.coff_header['number_of_sections']
        
        for i in range(num_sections):
            offset = sec_offset + i * 40
            # Name(8s), Misc.VirtualSize(I), VirtualAddress(I), SizeOfRawData(I), PointerToRawData(I),
            # PointerToRelocations(I), PointerToLinenumbers(I), NumberOfRelocations(H), NumberOfLinenumbers(H), Characteristics(I)
            fields = self.read_struct("<8sIIIIIIHHI", offset)
            
            name = fields[0].split(b'\0')[0].decode('utf-8', errors='replace')
            raw_data_offset = fields[4]
            raw_data_size = fields[3]
            
            # Compute entropy for this section
            entropy = self.calculate_entropy(raw_data_offset, raw_data_size)
            
            self.sections.append({
                'name': name,
                'virtual_size': fields[1],
                'virtual_address': fields[2],
                'size_of_raw_data': raw_data_size,
                'pointer_to_raw_data': raw_data_offset,
                'characteristics': fields[9],
                'entropy': entropy
            })

        # 7. Parse Imports
        self.parse_imports()

    def parse_imports(self):
        # Data directory 1 is Import Directory (index 1)
        data_dirs = self.optional_header.get('data_directories', [])
        if len(data_dirs) < 2:
            return

        import_dir = data_dirs[1]
        if import_dir['rva'] == 0 or import_dir['size'] == 0:
            return

        offset = self.rva_to_offset(import_dir['rva'])
        if offset == 0:
            return

        is_64 = self.optional_header['magic'] == 0x20b

        # Format of Import Directory Entry (20 bytes):
        # ImportLookupTableRVA(I), TimeDateStamp(I), ForwarderChain(I), NameRVA(I), ImportAddressTableRVA(I)
        while True:
            fields = self.read_struct("<IIIII", offset)
            if fields == (0, 0, 0, 0, 0):  # End of directory table
                break
            
            lookup_table_rva = fields[0]
            name_rva = fields[3]
            iat_rva = fields[4]
            
            # Read DLL name string
            name_offset = self.rva_to_offset(name_rva)
            if name_offset != 0:
                self.stream.seek(name_offset)
                dll_name_bytes = bytearray()
                while True:
                    char = self.stream.read(1)
                    if char == b'\0' or not char:
                        break
                    dll_name_bytes.extend(char)
                dll_name = dll_name_bytes.decode('utf-8', errors='replace')
            else:
                dll_name = f"unknown_dll_{name_rva:x}"

            # If Import Lookup Table RVA is zero, default to Import Address Table (IAT) RVA
            table_rva = lookup_table_rva if lookup_table_rva != 0 else iat_rva
            table_offset = self.rva_to_offset(table_rva)
            
            functions = []
            if table_offset != 0:
                entry_idx = 0
                while True:
                    # 64-bit uses 8-byte entries, 32-bit uses 4-byte entries
                    if is_64:
                        entry_val, = self.read_struct("<Q", table_offset + entry_idx * 8)
                        if entry_val == 0:
                            break
                        # High bit denotes import by ordinal
                        import_by_ordinal = bool(entry_val & 0x8000000000000000)
                        ordinal = entry_val & 0xFFFF
                        hint_name_rva = entry_val & 0x7FFFFFFF
                    else:
                        entry_val, = self.read_struct("<I", table_offset + entry_idx * 4)
                        if entry_val == 0:
                            break
                        import_by_ordinal = bool(entry_val & 0x80000000)
                        ordinal = entry_val & 0xFFFF
                        hint_name_rva = entry_val & 0x7FFFFFFF

                    if import_by_ordinal:
                        functions.append(f"Ordinal_{ordinal}")
                    else:
                        # Function name is at HintNameTable RVA (Hint is 2 bytes, then name string)
                        hint_offset = self.rva_to_offset(hint_name_rva)
                        if hint_offset != 0:
                            self.stream.seek(hint_offset + 2) # skip Hint (2 bytes)
                            func_name_bytes = bytearray()
                            while True:
                                char = self.stream.read(1)
                                if char == b'\0' or not char:
                                    break
                                func_name_bytes.extend(char)
                            func_name = func_name_bytes.decode('utf-8', errors='replace')
                            functions.append(func_name)
                        else:
                            functions.append(f"unknown_func_{hint_name_rva:x}")
                    entry_idx += 1

            self.imports[dll_name] = functions
            offset += 20  # Next import descriptor

    def audit_security_features(self):
        """Audits PE security features based on DLL characteristics."""
        char = self.optional_header.get('dll_characteristics', 0)
        return {
            'aslr': bool(char & IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE),
            'dep_nx': bool(char & IMAGE_DLLCHARACTERISTICS_NX_COMPAT),
            'force_integrity': bool(char & IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY),
            'no_seh': bool(char & IMAGE_DLLCHARACTERISTICS_NO_SEH),
            'cfg': bool(char & IMAGE_DLLCHARACTERISTICS_GUARD_CF),
            'appcontainer': bool(char & IMAGE_DLLCHARACTERISTICS_APPCONTAINER)
        }

def print_pe_report(parser, show_sections=False, show_imports=False):
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}                   PE BINARY HEADER ANALYZER                         {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    h = parser.coff_header
    opt = parser.optional_header
    sec = parser.audit_security_features()

    print(f"{BOLD}File Path:{RESET}      {parser.filepath}")
    print(f"{BOLD}File Size:{RESET}      {parser.file_size} bytes")
    print(f"{BOLD}Architecture:{RESET}   {YELLOW}{h['machine']}{RESET}")
    print(f"{BOLD}Subsystem:{RESET}      {opt.get('subsystem', 'Unknown')}")
    print(f"{BOLD}Linker Version:{RESET} {opt.get('major_linker_version')}.{opt.get('minor_linker_version')}")
    print(f"{BOLD}Entry Point RVA:{RESET}0x{opt.get('address_of_entry_point', 0):x}")
    print(f"{BOLD}Image Base:{RESET}     0x{opt.get('image_base', 0):x}")
    print(f"{BOLD}Image Size:{RESET}     {opt.get('size_of_image', 0)} bytes")
    print(f"{BOLD}Section Count:{RESET}  {h['number_of_sections']}")

    # Security checks
    print(f"\n{BOLD}{BLUE}--- Security Mitigations & Exploit Mitigations Audit ---{RESET}")
    print(f"  {BOLD}ASLR (Dynamic Base):{RESET}      {GREEN if sec['aslr'] else RED}{'ENABLED' if sec['aslr'] else 'DISABLED'}{RESET}")
    print(f"  {BOLD}DEP/NX (Data Execution Prevention):{RESET} {GREEN if sec['dep_nx'] else RED}{'ENABLED' if sec['dep_nx'] else 'DISABLED'}{RESET}")
    print(f"  {BOLD}Control Flow Guard (CFG):{RESET} {GREEN if sec['cfg'] else YELLOW}{'ENABLED' if sec['cfg'] else 'DISABLED/NOT_SUPPORTED'}{RESET}")
    print(f"  {BOLD}Code Integrity Validation:{RESET} {GREEN if sec['force_integrity'] else YELLOW}{'ENABLED' if sec['force_integrity'] else 'DISABLED'}{RESET}")
    print(f"  {BOLD}AppContainer Sandbox Compliant:{RESET} {GREEN if sec['appcontainer'] else RESET}{'YES' if sec['appcontainer'] else 'NO'}")

    if show_sections and parser.sections:
        print(f"\n{BOLD}{BLUE}--- Section Directory & Entropy Heatmap ---{RESET}")
        print(f"  {BOLD}{'Name':<10} {'VirtualAddress':<16} {'SizeOfRawData':<15} {'Entropy':<8} {'Status/Indication'}{RESET}")
        for s in parser.sections:
            ent = s['entropy']
            # Packing indicators: Entropy > 7.2 indicates packed/compressed data
            if ent > 7.2:
                status = f"{RED}HIGHLY ENTROPIC (PACKED / ENCRYPTED?){RESET}"
            elif ent > 6.0:
                status = f"{YELLOW}MODERATE ENTROPY (COMPRESSED / RESOURCES){RESET}"
            else:
                status = "Normal Code/Data"
            print(f"  {s['name']:<10} 0x{s['virtual_address']:08x} {s['size_of_raw_data']:<15} {ent:<8.4f} {status}")

    if parser.imports:
        print(f"\n{BOLD}{BLUE}--- Imported Libraries & DLL Dependencies (Count: {len(parser.imports)}) ---{RESET}")
        if show_imports:
            for dll, funcs in parser.imports.items():
                print(f"\n  {YELLOW}»{RESET} {BOLD}{dll}{RESET} ({len(funcs)} functions)")
                # Print up to 10 functions for visual clarity
                for f in funcs[:10]:
                    print(f"    - {f}")
                if len(funcs) > 10:
                    print(f"    ... and {len(funcs)-10} more functions")
        else:
            for dll in parser.imports.keys():
                print(f"  {YELLOW}»{RESET} {dll} ({len(parser.imports[dll])} imports)")

    print(f"\n{BOLD}{BLUE}======================================================================{RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description="PE Header & Dependency Analyzer - Parse, reverse engineer, and audit Windows PE binaries."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the Windows PE binary (.exe, .dll, .sys).")
    parser.add_argument("-s", "--sections", action="store_true", help="List sections and display entropy details.")
    parser.add_argument("-d", "--dependencies", action="store_true", help="List detailed library imports and functions.")
    parser.add_argument("-j", "--json", action="store_true", help="Output metadata in JSON format.")
    parser.add_argument("-a", "--all", action="store_true", help="Show sections, dependency functions, and security features.")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"{RED}Error: File '{args.input}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        pe = PEParser(args.input)
    except Exception as e:
        print(f"{RED}Error parsing PE file: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # Construct serializable dictionary
        json_data = {
            "dos_header": pe.dos_header,
            "coff_header": pe.coff_header,
            "optional_header": pe.optional_header,
            "sections": pe.sections,
            "imports": pe.imports,
            "security": pe.audit_security_features()
        }
        print(json.dumps(json_data, indent=4))
    else:
        show_sec = args.sections or args.all
        show_imp = args.dependencies or args.all
        print_pe_report(pe, show_sections=show_sec, show_imports=show_imp)

if __name__ == "__main__":
    main()
