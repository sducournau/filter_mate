#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to clean Python cache files (__pycache__ directories and .pyc files).

This helps resolve issues where old compiled Python files cause import errors
or unexpected behavior after code changes.

Usage:
    python clean_pycache.py
    
Run this script from the plugin root directory, then restart QGIS.
"""

import os
import shutil
import sys


def clean_pycache(root_dir=None):
    """
    Remove all __pycache__ directories and .pyc files.
    
    Args:
        root_dir: Root directory to clean (defaults to current directory)
    """
    if root_dir is None:
        root_dir = os.path.dirname(os.path.abspath(__file__))
    
    removed_dirs = 0
    removed_files = 0
    
    print(f"Cleaning Python cache in: {root_dir}")
    print("-" * 60)
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Remove __pycache__ directories
        if '__pycache__' in dirnames:
            cache_path = os.path.join(dirpath, '__pycache__')
            try:
                shutil.rmtree(cache_path)
                print(f"Removed directory: {cache_path}")
                removed_dirs += 1
            except Exception as e:
                print(f"Error removing {cache_path}: {e}")
        
        # Remove .pyc files (older Python versions put them alongside .py files)
        for filename in filenames:
            if filename.endswith('.pyc'):
                pyc_path = os.path.join(dirpath, filename)
                try:
                    os.remove(pyc_path)
                    print(f"Removed file: {pyc_path}")
                    removed_files += 1
                except Exception as e:
                    print(f"Error removing {pyc_path}: {e}")
    
    print("-" * 60)
    print(f"Cleanup complete!")
    print(f"  Removed {removed_dirs} __pycache__ directories")
    print(f"  Removed {removed_files} .pyc files")
    print()
    print("Please restart QGIS for changes to take effect.")


if __name__ == '__main__':
    # Allow passing a custom directory as argument
    if len(sys.argv) > 1:
        clean_pycache(sys.argv[1])
    else:
        clean_pycache()
