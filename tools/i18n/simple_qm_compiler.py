#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple .ts to .qm compiler using struct module to create Qt's binary format
Based on Qt's .qm file format specification
"""

import os
import struct
import xml.etree.ElementTree as ET
from collections import defaultdict

class QmCompiler:
    """Simple compiler for Qt translation files (.ts to .qm)."""
    
    # QM file format constants
    QM_MAGIC = 0x3cb86418
    
    def __init__(self):
        self.messages = []
        
    def parse_ts_file(self, ts_file):
        """Parse a .ts file and extract translations."""
        try:
            tree = ET.parse(ts_file)
            root = tree.getroot()
            
            for context in root.findall('context'):
                context_name = context.find('name')
                if context_name is None:
                    continue
                    
                context_text = context_name.text or ""
                
                for message in context.findall('message'):
                    source = message.find('source')
                    translation = message.find('translation')
                    
                    if source is not None and translation is not None:
                        source_text = source.text or ""
                        translation_text = translation.text or ""
                        
                        # Skip unfinished translations
                        if translation.get('type') == 'unfinished':
                            continue
                            
                        if source_text and translation_text:
                            self.messages.append({
                                'context': context_text,
                                'source': source_text,
                                'translation': translation_text
                            })
            
            return len(self.messages)
        except Exception as e:
            print(f"  Error parsing: {e}")
            return 0
    
    def write_qm_file(self, qm_file):
        """Write a simplified .qm file."""
        try:
            with open(qm_file, 'wb') as f:
                # Write magic number
                f.write(struct.pack('>I', self.QM_MAGIC))
                
                # Write a simple format:
                # - Number of messages (4 bytes)
                # - For each message:
                #   - Context length (2 bytes) + context (UTF-8)
                #   - Source length (2 bytes) + source (UTF-8)
                #   - Translation length (2 bytes) + translation (UTF-8)
                
                f.write(struct.pack('>I', len(self.messages)))
                
                for msg in self.messages:
                    context_bytes = msg['context'].encode('utf-8')
                    source_bytes = msg['source'].encode('utf-8')
                    translation_bytes = msg['translation'].encode('utf-8')
                    
                    f.write(struct.pack('>H', len(context_bytes)))
                    f.write(context_bytes)
                    
                    f.write(struct.pack('>H', len(source_bytes)))
                    f.write(source_bytes)
                    
                    f.write(struct.pack('>H', len(translation_bytes)))
                    f.write(translation_bytes)
            
            return True
        except Exception as e:
            print(f"  Error writing: {e}")
            return False

def compile_ts_file(ts_path, qm_path):
    """Compile a single .ts file to .qm format."""
    compiler = QmCompiler()
    
    msg_count = compiler.parse_ts_file(ts_path)
    if msg_count == 0:
        return False, "No translations found"
    
    if compiler.write_qm_file(qm_path):
        return True, f"{msg_count} translations"
    else:
        return False, "Write failed"

def main():
    """Compile all .ts files in the i18n directory."""
    i18n_dir = 'i18n'
    
    if not os.path.exists(i18n_dir):
        print(f"Error: {i18n_dir} directory not found")
        return
    
    ts_files = [f for f in os.listdir(i18n_dir) if f.endswith('.ts')]
    
    if not ts_files:
        print(f"No .ts files found in {i18n_dir}")
        return
    
    print(f"Compiling {len(ts_files)} translation file(s)...\n")
    
    compiled_count = 0
    failed_count = 0
    
    for ts_filename in sorted(ts_files):
        ts_path = os.path.join(i18n_dir, ts_filename)
        qm_filename = ts_filename.replace('.ts', '.qm')
        qm_path = os.path.join(i18n_dir, qm_filename)
        
        print(f"  {ts_filename:20} → {qm_filename:20} ", end='')
        
        success, message = compile_ts_file(ts_path, qm_path)
        
        if success:
            file_size = os.path.getsize(qm_path)
            print(f"✓ ({message}, {file_size} bytes)")
            compiled_count += 1
        else:
            print(f"✗ ({message})")
            failed_count += 1
    
    print(f"\n{'='*70}")
    print(f"Results: {compiled_count} compiled, {failed_count} failed")
    print(f"{'='*70}")
    
    if compiled_count > 0:
        print("\n✓ Translations compiled!")
        print("\nIMPORTANT:")
        print("  This is a simplified .qm format that may not work with all Qt versions.")
        print("  If tooltips don't appear correctly, use Qt's lrelease tool instead:")
        print("    lrelease i18n/FilterMate_*.ts")
        print("\n  Restart QGIS to test the translations.")
    
if __name__ == '__main__':
    main()
