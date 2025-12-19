---
sidebar_position: 3
---

# Development Setup

Complete guide to setting up your development environment for FilterMate plugin development.

## Prerequisites

### Required Software

- **QGIS 3.x** (Latest LTS recommended)
- **Python 3.7+** (comes with QGIS)
- **Git** for version control
- **Code Editor** (VS Code, PyCharm, or similar)

### Optional Dependencies

- **psycopg2** for PostgreSQL backend development
- **pytest** for running tests
- **black** for code formatting

## Initial Setup

### 1. Clone Repository

```bash
# Clone the repository
git clone https://github.com/sducournau/filter_mate.git
cd filter_mate
```

### 2. Link to QGIS Plugins Directory

**Linux:**
```bash
ln -s $(pwd) ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate
```

**Windows:**
```cmd
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\filter_mate" "%CD%"
```

**macOS:**
```bash
ln -s $(pwd) ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/filter_mate
```

### 3. Install Dependencies

#### PostgreSQL Support (Recommended)

```bash
# Using pip
pip install psycopg2-binary

# Or using QGIS Python console
import pip
pip.main(['install', 'psycopg2-binary'])
```

#### Testing Dependencies

```bash
pip install -r tests/requirements-test.txt
```

## Development Workflow

### Compiling UI Files

After modifying `.ui` files in Qt Designer:

**Linux/macOS:**
```bash
./compile_ui.sh
```

**Windows:**
```cmd
compile_ui.bat
```

**Manual compilation:**
```bash
pyuic5 filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
pyrcc5 resources.qrc -o resources.py
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_backends.py -v

# Run with coverage
pytest tests/ --cov=modules --cov-report=html

# Run performance benchmarks
python tests/benchmark_simple.py
```

### Debugging

#### Using QGIS Python Console

1. Open QGIS
2. Go to Plugins → Python Console
3. Use `print()` statements in your code
4. Reload plugin: `qgis.utils.reloadPlugin('filter_mate')`

#### Using VS Code

1. Install "Python" extension
2. Configure `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "QGIS Python",
      "type": "python",
      "request": "attach",
      "port": 5678,
      "host": "localhost"
    }
  ]
}
```

3. Add to your code:
```python
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

## Project Structure

```
filter_mate/
├── filter_mate.py              # Plugin entry point
├── filter_mate_app.py          # Main application
├── filter_mate_dockwidget.py   # UI management
├── config/
│   ├── config.json            # Configuration
│   └── config.py              # Config loader
├── modules/
│   ├── appTasks.py            # Async tasks
│   ├── appUtils.py            # Utilities
│   ├── backends/              # Backend implementations
│   └── ...                    # Other modules
├── tests/                     # Unit tests
├── docs/                      # Documentation
└── website/                   # Docusaurus site
```

## Common Tasks

### Creating a Release

```bash
# Create release ZIP
python create_release_zip.py

# Output: filter_mate_vX.Y.Z.zip
```

### Building Documentation

```bash
cd website
npm install
npm run build
```

### Code Formatting

```bash
# Format code with black
black modules/ tests/

# Check formatting
black --check modules/ tests/
```

## Troubleshooting

### Plugin Not Loading

1. Check QGIS Python console for errors
2. Verify symbolic link is correct
3. Ensure `metadata.txt` is present
4. Check plugin path in QGIS settings

### Import Errors

- Ensure all dependencies are installed in QGIS Python environment
- Use QGIS's Python interpreter, not system Python

### UI Not Updating

- Recompile UI files with `compile_ui.sh`
- Restart QGIS
- Clear QGIS cache: `~/.local/share/QGIS/QGIS3/cache/`

## Best Practices

1. **Always test locally** before committing
2. **Run unit tests** after changes
3. **Follow code style** guidelines
4. **Update documentation** for new features
5. **Use feature branches** for development

## Further Reading

- [Architecture Overview](./architecture)
- [Code Style Guide](./code-style)
- [Contributing Guide](./contributing)
- [Testing Guide](./testing)
