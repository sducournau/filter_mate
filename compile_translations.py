#!/usr/bin/env python3
"""
Compile Qt translation files (.ts) to binary format (.qm)

This script compiles all .ts files in the i18n directory to .qm format
using a pure Python implementation when lrelease is not available.
"""

import os
import sys
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


class QmCompiler:
    """Simple .qm compiler for Qt translation files"""
    
    # QM file format constants
    QM_MAGIC = 0x3cb86418
    TAG_END = 1
    TAG_SOURCETEXT16 = 2
    TAG_TRANSLATION = 3
    TAG_CONTEXT16 = 4
    TAG_OBSOLETE1 = 5
    TAG_SOURCEHASH16 = 6
    TAG_CONTEXT = 7
    TAG_SOURCETEXT = 8
    TAG_COMMENT = 9
    TAG_OBSOLETE2 = 10
    
    def __init__(self):
        self.messages = []
        
    def compile_ts_to_qm(self, ts_file, qm_file):
        """Compile a .ts file to .qm format"""
        try:
            # Parse the .ts file
            tree = ET.parse(ts_file)
            root = tree.getroot()
            
            # Extract messages
            contexts = []
            
            for context in root.findall('context'):
                context_name = context.find('name')
                if context_name is None:
                    continue
                    
                context_name_text = context_name.text or ''
                messages = []
                
                for message in context.findall('message'):
                    source = message.find('source')
                    translation = message.find('translation')
                    
                    if source is None or translation is None:
                        continue
                    
                    source_text = source.text or ''
                    trans_text = translation.text or ''
                    trans_type = translation.get('type', '')
                    
                    # Skip unfinished or obsolete translations
                    if trans_type in ('unfinished', 'obsolete'):
                        continue
                    
                    # Skip empty translations
                    if not trans_text.strip():
                        continue
                    
                    messages.append({
                        'source': source_text,
                        'translation': trans_text
                    })
                
                if messages:
                    contexts.append({
                        'name': context_name_text,
                        'messages': messages
                    })
            
            # Write .qm file
            with open(qm_file, 'wb') as f:
                self._write_qm_header(f)
                self._write_qm_contexts(f, contexts)
                self._write_qm_footer(f)
            
            return True, len([m for ctx in contexts for m in ctx['messages']])
            
        except Exception as e:
            return False, str(e)
    
    def _write_qm_header(self, f):
        """Write QM file header"""
        # Magic number
        f.write(struct.pack('>I', self.QM_MAGIC))
    
    def _write_qm_contexts(self, f, contexts):
        """Write contexts and messages"""
        for context in contexts:
            # Context tag
            context_name = context['name'].encode('utf-16-be')
            f.write(struct.pack('B', self.TAG_CONTEXT))
            f.write(struct.pack('>I', len(context_name)))
            f.write(context_name)
            
            for message in context['messages']:
                # Source text
                source = message['source'].encode('utf-16-be')
                f.write(struct.pack('B', self.TAG_SOURCETEXT))
                f.write(struct.pack('>I', len(source)))
                f.write(source)
                
                # Translation
                translation = message['translation'].encode('utf-16-be')
                f.write(struct.pack('B', self.TAG_TRANSLATION))
                f.write(struct.pack('>I', len(translation)))
                f.write(translation)
    
    def _write_qm_footer(self, f):
        """Write QM file footer"""
        f.write(struct.pack('B', self.TAG_END))


def compile_all_translations(i18n_dir='i18n', force=False):
    """Compile all .ts files to .qm in the specified directory"""
    
    i18n_path = Path(i18n_dir)
    if not i18n_path.exists():
        print(f"❌ Directory '{i18n_dir}' not found")
        return False
    
    ts_files = sorted(i18n_path.glob('*.ts'))
    
    if not ts_files:
        print(f"❌ No .ts files found in '{i18n_dir}'")
        return False
    
    print(f"🔨 COMPILING QT TRANSLATIONS")
    print("=" * 70)
    print()
    
    compiler = QmCompiler()
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for ts_file in ts_files:
        qm_file = ts_file.with_suffix('.qm')
        lang_code = ts_file.stem.split('_')[-1].upper()
        
        # Check if compilation is needed
        if not force and qm_file.exists():
            if qm_file.stat().st_mtime >= ts_file.stat().st_mtime:
                print(f"⏭️  {lang_code:4} - {ts_file.name:25} → {qm_file.name:25} (up to date)")
                skipped_count += 1
                continue
        
        # Compile
        success, result = compiler.compile_ts_to_qm(str(ts_file), str(qm_file))
        
        if success:
            message_count = result
            print(f"✅ {lang_code:4} - {ts_file.name:25} → {qm_file.name:25} ({message_count} strings)")
            success_count += 1
        else:
            print(f"❌ {lang_code:4} - {ts_file.name:25} → Error: {result}")
            error_count += 1
    
    print()
    print("=" * 70)
    print(f"📊 Summary: {success_count} compiled, {skipped_count} skipped, {error_count} errors")
    print()
    
    return error_count == 0


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Compile Qt translation files (.ts) to binary format (.qm)'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force recompilation even if .qm is up to date'
    )
    parser.add_argument(
        '--dir', '-d',
        default='i18n',
        help='Directory containing .ts files (default: i18n)'
    )
    
    args = parser.parse_args()
    
    success = compile_all_translations(args.dir, args.force)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
