# Serena MCP Server Setup for Windows

## Overview

This document explains how Serena is configured to auto-start when GitHub Copilot Chat is activated in VS Code on Windows.

## Installation

### 1. Install Serena

```powershell
# Install via uv (recommended)
uv tool install serena

# Verify installation
uvx serena --version
```

### 2. Configure MCP in VS Code

The MCP (Model Context Protocol) configuration file is located at:
```
%APPDATA%/Code/User/globalStorage/github.copilot.chat.mcp/config.json
```

Full path example:
```
C:/Users/Simon/AppData/Roaming/Code/User/globalStorage/github.copilot.chat.mcp/config.json
```

### 3. MCP Configuration Content

Edit the `config.json` file to include:

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": ["serena"],
      "env": {
        "SERENA_PROJECT": "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"
      }
    }
  }
}
```

**Important Notes:**
- Use forward slashes (`/`) in paths, not backslashes
- The `SERENA_PROJECT` environment variable automatically activates the project
- Replace the path with your actual project location

## How It Works

1. **Automatic Startup**: When you open Copilot Chat in VS Code, the MCP server automatically launches Serena
2. **Project Activation**: The `SERENA_PROJECT` environment variable tells Serena which project to activate
3. **Tool Availability**: All Serena symbolic tools become immediately available in the chat
4. **No Manual Commands**: You don't need to run `activate_project()` or start Serena manually

## Verifying Setup

### Test 1: Check Serena Installation
```powershell
# From PowerShell or CMD
uvx serena --version
```

Should display Serena version information.

### Test 2: Check MCP Server Status
1. Open VS Code
2. Open Copilot Chat
3. Check the **Output** panel → Select "GitHub Copilot Chat MCP" from dropdown
4. Look for log entries indicating Serena started

### Test 3: Use Serena Tools
In Copilot Chat, try:
```
get_current_config()
```

Should show:
- Active project: `filter_mate`
- Available Serena tools listed
- Language servers status

## Troubleshooting

### Problem: Serena tools not available

**Solution 1: Check MCP config file exists**
```powershell
# Check if file exists
Test-Path "$env:APPDATA\Code\User\globalStorage\github.copilot.chat.mcp\config.json"

# View content
Get-Content "$env:APPDATA\Code\User\globalStorage\github.copilot.chat.mcp\config.json"
```

**Solution 2: Verify path format**
- Use forward slashes: `C:/Users/Simon/...`
- Don't use backslashes: `C:\Users\Simon\...` (will cause issues in JSON)

**Solution 3: Check Serena works standalone**
```powershell
# Test Serena activation
uvx serena --project "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"
```

**Solution 4: Reload VS Code**
- Close all VS Code windows
- Reopen VS Code
- Open Copilot Chat
- Check Output panel for MCP server logs

### Problem: Wrong project activated

**Solution**: Update `SERENA_PROJECT` in MCP config
```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": ["serena"],
      "env": {
        "SERENA_PROJECT": "C:/Path/To/Your/Project"
      }
    }
  }
}
```

### Problem: MCP server crashes

**Solution 1: Check logs**
1. VS Code → Output panel
2. Select "GitHub Copilot Chat MCP"
3. Look for error messages

**Solution 2: Test command manually**
```powershell
# Set environment variable
$env:SERENA_PROJECT = "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"

# Run Serena
uvx serena
```

## MCP Configuration for Multiple Projects

If you work with multiple projects, you can configure multiple MCP servers:

```json
{
  "mcpServers": {
    "serena-filtermate": {
      "command": "uvx",
      "args": ["serena"],
      "env": {
        "SERENA_PROJECT": "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"
      }
    },
    "serena-other-project": {
      "command": "uvx",
      "args": ["serena"],
      "env": {
        "SERENA_PROJECT": "C:/Users/Simon/Projects/other-project"
      }
    }
  }
}
```

**Note**: Only the MCP server for the currently open workspace will be active.

## Advanced Configuration

### Custom Serena Settings

You can pass additional arguments to Serena:

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": [
        "serena",
        "--log-level", "debug"
      ],
      "env": {
        "SERENA_PROJECT": "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"
      }
    }
  }
}
```

### Environment Variables

Additional environment variables you can set:

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": ["serena"],
      "env": {
        "SERENA_PROJECT": "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate",
        "SERENA_CONFIG": "C:/Users/Simon/.serena/config.yml",
        "PYTHONPATH": "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"
      }
    }
  }
}
```

## Benefits of MCP Auto-Start

✅ **Seamless Experience**: No manual activation needed
✅ **Consistent State**: Project always loads with correct context
✅ **Time Saving**: Skip repetitive `activate_project()` commands
✅ **Error Prevention**: Eliminates "project not activated" errors
✅ **Better Workflow**: Focus on coding, not tool management

## Related Documentation

- Serena project configuration: `.serena/project.yml`
- Serena optimization rules: `.serena/optimization_rules.md`
- Serena tool usage: `.serena/README.md`
- FilterMate coding guidelines: `.github/copilot-instructions.md`

## References

- [Serena Documentation](https://github.com/serena-project/serena)
- [MCP Protocol](https://github.com/modelcontextprotocol/protocol)
- [GitHub Copilot Chat MCP Support](https://github.com/github/copilot-docs)
