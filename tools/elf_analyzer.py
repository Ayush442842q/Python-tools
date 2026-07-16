#!/usr/bin/env python3
"""
ELF Header & Binary Analyzer
============================
A zero-dependency command-line reverse engineering and security auditing utility
to parse Executable and Linkable Format (ELF) binaries. Extracts ELF headers,
program headers (segments), section headers, dynamic library dependencies,
and printable string constants natively in Python.

Author: Antigravity
License: MIT
"""

import os
import sys
import struct
import json
import argparse

# ANSI Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ELF Constants mapping
ELF_CLASS = {0: "Invalid", 1: "32-bit", 2: "64-bit"}
ELF_DATA = {0: "Invalid", 1: "2's complement, little endian", 2: "2's complement, big endian"}
ELF_OSABI = {
    0: "System V", 1: "HP-UX", 2: "NetBSD", 3: "Linux", 6: "Solaris",
    7: "AIX", 8: "IRIX", 9: "FreeBSD", 10: "Tru64", 11: "Novell Modesto",
    12: "OpenBSD", 13: "OpenVMS", 14: "NonStop Kernel", 15: "AROS",
    16: "FenixOS", 17: "Nuxi CloudABI", 18: "Stratus Technologies OpenVOS"
}
ELF_TYPE = {
    0: "NONE (No file type)", 1: "REL (Relocatable file)",
    2: "EXEC (Executable file)", 3: "DYN (Shared object file)",
    4: "CORE (Core file)"
}
ELF_MACHINE = {
    0: "None", 2: "SPARC", 3: "x86", 8: "MIPS", 19: "Intel i960",
    20: "PowerPC", 22: "S390", 40: "ARM", 42: "SuperH", 50: "IA-64",
    62: "AMD64 (x86-64)", 87: "Motorola Coldfire", 183: "AArch64 (ARM64)",
    243: "RISC-V"
}

SH_TYPE = {
    0: "NULL", 1: "PROGBITS", 2: "SYMTAB", 3: "STRTAB", 4: "RELA",
    5: "HASH", 6: "DYNAMIC", 7: "NOTE", 8: "NOBITS", 9: "REL",
    10: "SHLIB", 11: "DYNSYM", 14: "INIT_ARRAY", 15: "FINI_ARRAY",
    16: "PREINIT_ARRAY", 17: "GROUP", 18: "SYMTAB_SHNDX"
}

PT_TYPE = {
    0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP", 4: "NOTE",
    5: "SHLIB", 6: "PHDR", 7: "TLS", 0x60000000: "LOOS", 0x6474e550: "GNU_EH_FRAME",
    0x6474e551: "GNU_STACK", 0x6474e552: "GNU_RELRO", 0x6fffffff: "HIOS",
    0x70000000: "LOPROC", 0x7fffffff: "HIPROC"
}

class ELFParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.file_size = os.path.getsize(filepath)
        self.stream = open(filepath, 'rb')
        self.header = {}
        self.sections = []
        self.segments = []
        self.dynamic_libraries = []
        self.parse_header()
        self.parse_sections()
        self.parse_segments()
        self.parse_dynamic_section()

    def __del__(self):
        if hasattr(self, 'stream') and self.stream:
            self.stream.close()

    def read_struct(self, format_str, offset):
        size = struct.calcsize(format_str)
        self.stream.seek(offset)
        data = self.stream.read(size)
        if len(data) < size:
            raise ValueError("Unexpected end of file while reading structure.")
        return struct.unpack(format_str, data)

    def parse_header(self):
        # Read e_ident (16 bytes)
        ident = self.read_struct("16B", 0)
        if ident[0:4] != (0x7F, ord('E'), ord('L'), ord('F')):
            raise ValueError("Not a valid ELF binary file.")

        self.header['class_raw'] = ident[4]
        self.header['class'] = ELF_CLASS.get(ident[4], "Unknown")
        self.header['data_raw'] = ident[5]
        self.header['data'] = ELF_DATA.get(ident[5], "Unknown")
        self.header['version_ident'] = ident[6]
        self.header['osabi_raw'] = ident[7]
        self.header['osabi'] = ELF_OSABI.get(ident[7], "Unknown")
        self.header['abiversion'] = ident[8]

        # Determine endianness format char
        endian = '<' if ident[5] == 1 else '>'
        is_64 = ident[4] == 2

        # Format mappings for remaining ELF header fields
        # 32-bit: e_type(H) e_machine(H) e_version(I) e_entry(I) e_phoff(I) e_shoff(I) e_flags(I) e_ehsize(H) e_phentsize(H) e_phnum(H) e_shentsize(H) e_shnum(H) e_shstrndx(H)
        # 64-bit: e_type(H) e_machine(H) e_version(I) e_entry(Q) e_phoff(Q) e_shoff(Q) e_flags(I) e_ehsize(H) e_phentsize(H) e_phnum(H) e_shentsize(H) e_shnum(H) e_shstrndx(H)
        if is_64:
            fmt = endian + "HHIQQQIHHHHHH"
            fields = self.read_struct(fmt, 16)
        else:
            fmt = endian + "HHIIIIIHHHHHH"
            fields = self.read_struct(fmt, 16)

        self.header['type_raw'] = fields[0]
        self.header['type'] = ELF_TYPE.get(fields[0], "Unknown")
        self.header['machine_raw'] = fields[1]
        self.header['machine'] = ELF_MACHINE.get(fields[1], "Unknown")
        self.header['version'] = fields[2]
        self.header['entry'] = fields[3]
        self.header['phoff'] = fields[4]
        self.header['shoff'] = fields[5]
        self.header['flags'] = fields[6]
        self.header['ehsize'] = fields[7]
        self.header['phentsize'] = fields[8]
        self.header['phnum'] = fields[9]
        self.header['shentsize'] = fields[10]
        self.header['shnum'] = fields[11]
        self.header['shstrndx'] = fields[12]

    def parse_sections(self):
        shoff = self.header['shoff']
        shnum = self.header['shnum']
        shentsize = self.header['shentsize']
        if shoff == 0 or shnum == 0:
            return

        is_64 = self.header['class_raw'] == 2
        endian = '<' if self.header['data_raw'] == 1 else '>'

        # 32-bit Section Header layout: sh_name(I) sh_type(I) sh_flags(I) sh_addr(I) sh_offset(I) sh_size(I) sh_link(I) sh_info(I) sh_addralign(I) sh_entsize(I)
        # 64-bit Section Header layout: sh_name(I) sh_type(I) sh_flags(Q) sh_addr(Q) sh_offset(Q) sh_size(Q) sh_link(I) sh_info(I) sh_addralign(Q) sh_entsize(Q)
        if is_64:
            fmt = endian + "IIQQQQIIQQ"
        else:
            fmt = endian + "IIIIIIIIII"

        raw_sections = []
        for i in range(shnum):
            offset = shoff + i * shentsize
            fields = self.read_struct(fmt, offset)
            raw_sections.append({
                'name_idx': fields[0],
                'type_raw': fields[1],
                'type': SH_TYPE.get(fields[1], f"UNKNOWN_0x{fields[1]:x}"),
                'flags': fields[2],
                'addr': fields[3],
                'offset': fields[4],
                'size': fields[5],
                'link': fields[6],
                'info': fields[7],
                'addralign': fields[8],
                'entsize': fields[9]
            })

        # Resolve section names using the string table (.shstrtab)
        shstrndx = self.header['shstrndx']
        if shstrndx < shnum:
            strtab_sec = raw_sections[shstrndx]
            strtab_offset = strtab_sec['offset']
            
            # Read whole string table
            self.stream.seek(strtab_offset)
            strtab_data = self.stream.read(strtab_sec['size'])
            
            for s in raw_sections:
                name_idx = s['name_idx']
                if name_idx < len(strtab_data):
                    end = strtab_data.find(b'\0', name_idx)
                    s['name'] = strtab_data[name_idx:end].decode('utf-8', errors='replace')
                else:
                    s['name'] = ""
        else:
            for s in raw_sections:
                s['name'] = f"sec_{s['name_idx']}"

        self.sections = raw_sections

    def parse_segments(self):
        phoff = self.header['phoff']
        phnum = self.header['phnum']
        phentsize = self.header['phentsize']
        if phoff == 0 or phnum == 0:
            return

        is_64 = self.header['class_raw'] == 2
        endian = '<' if self.header['data_raw'] == 1 else '>'

        # 32-bit Program Header: p_type(I) p_offset(I) p_vaddr(I) p_paddr(I) p_filesz(I) p_memsz(I) p_flags(I) p_align(I)
        # 64-bit Program Header: p_type(I) p_flags(I) p_offset(Q) p_vaddr(Q) p_paddr(Q) p_filesz(Q) p_memsz(Q) p_align(Q)
        for i in range(phnum):
            offset = phoff + i * phentsize
            if is_64:
                fmt = endian + "IIQQQQQQ"
                fields = self.read_struct(fmt, offset)
                self.segments.append({
                    'type_raw': fields[0],
                    'type': PT_TYPE.get(fields[0], f"UNKNOWN_0x{fields[0]:x}"),
                    'flags': fields[1],
                    'offset': fields[2],
                    'vaddr': fields[3],
                    'paddr': fields[4],
                    'filesz': fields[5],
                    'memsz': fields[6],
                    'align': fields[7]
                })
            else:
                fmt = endian + "IIIIIIII"
                fields = self.read_struct(fmt, offset)
                self.segments.append({
                    'type_raw': fields[0],
                    'type': PT_TYPE.get(fields[0], f"UNKNOWN_0x{fields[0]:x}"),
                    'offset': fields[1],
                    'vaddr': fields[2],
                    'paddr': fields[3],
                    'filesz': fields[4],
                    'memsz': fields[5],
                    'flags': fields[6],
                    'align': fields[7]
                })

    def parse_dynamic_section(self):
        # Locate dynamic section & dynstr (string table for libraries)
        dynamic_sec = None
        dynstr_sec = None
        for s in self.sections:
            if s['type'] == 'DYNAMIC':
                dynamic_sec = s
            elif s['name'] == '.dynstr':
                dynstr_sec = s

        if not dynamic_sec or not dynstr_sec:
            return

        is_64 = self.header['class_raw'] == 2
        endian = '<' if self.header['data_raw'] == 1 else '>'

        # Read dynstr data
        self.stream.seek(dynstr_sec['offset'])
        dynstr_data = self.stream.read(dynstr_sec['size'])

        # Dynamic entries consist of a tag (d_tag) and a value (d_val / d_ptr)
        # 32-bit: tag(I) val(I)
        # 64-bit: tag(Q) val(Q)
        entry_size = 16 if is_64 else 8
        fmt = (endian + "QQ") if is_64 else (endian + "II")
        
        count = dynamic_sec['size'] // entry_size
        needed_offsets = []

        for i in range(count):
            offset = dynamic_sec['offset'] + i * entry_size
            tag, val = self.read_struct(fmt, offset)
            if tag == 0:  # DT_NULL (End of dynamic section)
                break
            if tag == 1:  # DT_NEEDED (Offset in string table)
                needed_offsets.append(val)

        for off in needed_offsets:
            if off < len(dynstr_data):
                end = dynstr_data.find(b'\0', off)
                lib_name = dynstr_data[off:end].decode('utf-8', errors='replace')
                self.dynamic_libraries.append(lib_name)

    def extract_strings(self, min_len=4):
        """Extract printable strings from the file streams, similar to strings command."""
        self.stream.seek(0)
        data = self.stream.read()
        strings = []
        curr_str = bytearray()
        
        for b in data:
            if 32 <= b <= 126 or b == 10 or b == 13 or b == 9:  # Printable chars + \n \r \t
                curr_str.append(b)
            else:
                if len(curr_str) >= min_len:
                    try:
                        strings.append(curr_str.decode('utf-8'))
                    except UnicodeDecodeError:
                        strings.append(curr_str.decode('latin-1', errors='replace'))
                curr_str = bytearray()
        
        if len(curr_str) >= min_len:
            try:
                strings.append(curr_str.decode('utf-8'))
            except UnicodeDecodeError:
                strings.append(curr_str.decode('latin-1', errors='replace'))
                
        return strings

def print_elf_report(parser, show_sections=False, show_segments=False, show_dynamic=False, show_strings=False, string_len=4):
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}                   ELF BINARY HEADER ANALYZER                         {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    h = parser.header
    print(f"{BOLD}File Path:{RESET}      {parser.filepath}")
    print(f"{BOLD}File Size:{RESET}      {parser.file_size} bytes")
    print(f"{BOLD}ELF Class:{RESET}      {YELLOW}{h['class']}{RESET}")
    print(f"{BOLD}Data/Endian:{RESET}    {h['data']}")
    print(f"{BOLD}OS ABI:{RESET}         {h['osabi']}")
    print(f"{BOLD}ABI Version:{RESET}    {h['abiversion']}")
    print(f"{BOLD}Binary Type:{RESET}    {h['type']}")
    print(f"{BOLD}Architecture:{RESET}   {GREEN}{h['machine']}{RESET}")
    print(f"{BOLD}Entry Point:{RESET}    0x{h['entry']:x}")
    print(f"{BOLD}Flags:{RESET}          0x{h['flags']:x}")
    print(f"{BOLD}Header Size:{RESET}    {h['ehsize']} bytes")
    print(f"{BOLD}Section Headers Offset:{RESET} 0x{h['shoff']:x} ({h['shnum']} sections)")
    print(f"{BOLD}Program Headers Offset:{RESET} 0x{h['phoff']:x} ({h['phnum']} segments)")

    if parser.dynamic_libraries:
        print(f"\n{BOLD}{BLUE}--- Shared Dynamic Library Dependencies ---{RESET}")
        for lib in parser.dynamic_libraries:
            print(f"  {YELLOW}»{RESET} {lib}")

    if show_segments and parser.segments:
        print(f"\n{BOLD}{BLUE}--- Program Headers / Segments Table ---{RESET}")
        print(f"  {BOLD}{'Type':<15} {'Offset':<12} {'VirtAddr':<16} {'FileSize':<10} {'MemSize':<10} {'Flags':<6} {'Align':<6}{RESET}")
        for seg in parser.segments:
            flags_str = ""
            flags_str += "R" if seg['flags'] & 4 else "-"
            flags_str += "W" if seg['flags'] & 2 else "-"
            flags_str += "X" if seg['flags'] & 1 else "-"
            print(f"  {seg['type']:<15} 0x{seg['offset']:08x} 0x{seg['vaddr']:012x} {seg['filesz']:<10} {seg['memsz']:<10} {flags_str:<6} 0x{seg['align']:x}")

    if show_sections and parser.sections:
        print(f"\n{BOLD}{BLUE}--- Section Headers Table ---{RESET}")
        print(f"  {BOLD}{'Name':<24} {'Type':<12} {'Address':<16} {'Offset':<10} {'Size':<10} {'Align':<5}{RESET}")
        for sec in parser.sections:
            print(f"  {sec['name']:<24} {sec['type']:<12} 0x{sec['addr']:012x} 0x{sec['offset']:08x} {sec['size']:<10} {sec['addralign']:<5}")

    if show_strings:
        strings = parser.extract_strings(string_len)
        print(f"\n{BOLD}{BLUE}--- Extracted Printable Strings (Min length: {string_len}, Count: {len(strings)}) ---{RESET}")
        # Print first 100 strings
        for s in strings[:100]:
            print(f"  {s}")
        if len(strings) > 100:
            print(f"  ... [Truncated {len(strings) - 100} strings]")

    print(f"\n{BOLD}{BLUE}======================================================================{RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description="ELF Header & Binary Analyzer - Parse, reverse engineer, and audit ELF binaries natively."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the ELF file.")
    parser.add_argument("-s", "--sections", action="store_true", help="List section headers.")
    parser.add_argument("-p", "--segments", action="store_true", help="List program headers (segments).")
    parser.add_argument("-d", "--dynamic", action="store_true", help="Display shared dynamic libraries.")
    parser.add_argument("-t", "--strings", action="store_true", help="Extract and display printable strings.")
    parser.add_argument("-l", "--string-len", type=int, default=4, help="Minimum printable string length (default 4).")
    parser.add_argument("-j", "--json", action="store_true", help="Output information as JSON.")
    parser.add_argument("-a", "--all", action="store_true", help="Show all section headers, program headers, and dynamic details.")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"{RED}Error: File '{args.input}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        elf = ELFParser(args.input)
    except Exception as e:
        print(f"{RED}Error parsing ELF file: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # Build serializable dictionary
        json_data = {
            "header": elf.header,
            "dynamic_libraries": elf.dynamic_libraries,
            "segments": elf.segments,
            "sections": elf.sections
        }
        print(json.dumps(json_data, indent=4))
    else:
        show_sec = args.sections or args.all
        show_seg = args.segments or args.all
        show_dyn = args.dynamic or args.all
        print_elf_report(
            elf,
            show_sections=show_sec,
            show_segments=show_seg,
            show_dynamic=show_dyn,
            show_strings=args.strings,
            string_len=args.string_len
        )

if __name__ == "__main__":
    main()
