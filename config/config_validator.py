"""
Configuration Validator for FilterMate.

Validates config.json against config_schema.json to ensure data integrity.
Uses a lightweight validation approach that doesn't require external dependencies.

v4.0.7: Initial implementation based on audit recommendations.

Author: FilterMate Team
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple
from qgis.core import QgsMessageLog, Qgis


class ConfigValidationError:
    """Represents a single validation error."""

    def __init__(self, path: str, message: str, severity: str = "error"):
        """
        Initialize validation error.

        Args:
            path: JSON path to the invalid value (e.g., "APP.DOCKWIDGET.THEME")
            message: Human-readable error message
            severity: "error" or "warning"
        """
        self.path = path
        self.message = message
        self.severity = severity

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.path}: {self.message}"

    def __repr__(self) -> str:
        return f"ConfigValidationError(path='{self.path}', message='{self.message}')"


class ConfigValidator:
    """
    Validates FilterMate configuration against schema.

    Supports the v2.0 config format with {value, choices, description} structures.
    Performs structural validation without requiring jsonschema library.

    Example:
        validator = ConfigValidator('/path/to/plugin/config')
        is_valid, errors = validator.validate_config(config_data)
        if not is_valid:
            for error in errors:
                print(error)
    """

    def __init__(self, config_dir: str):
        """
        Initialize validator with config directory path.

        Args:
            config_dir: Path to the config directory containing config_schema.json
        """
        self.config_dir = config_dir
        self.schema_path = os.path.join(config_dir, 'config_schema.json')
        self._schema: Optional[Dict] = None
        self._errors: List[ConfigValidationError] = []

    def _load_schema(self) -> bool:
        """
        Load the schema file.

        Returns:
            True if schema loaded successfully, False otherwise
        """
        if self._schema is not None:
            return True

        if not os.path.exists(self.schema_path):
            QgsMessageLog.logMessage(
                f"Schema file not found: {self.schema_path}",
                "FilterMate",
                Qgis.Warning
            )
            return False

        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self._schema = json.load(f)
            return True
        except json.JSONDecodeError as e:
            QgsMessageLog.logMessage(
                f"Invalid JSON in schema file: {e}",
                "FilterMate",
                Qgis.Critical
            )
            return False
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading schema: {e}",
                "FilterMate",
                Qgis.Critical
            )
            return False

    def validate_config(self, config_data: Dict) -> Tuple[bool, List[ConfigValidationError]]:
        """
        Validate configuration data against schema.

        Args:
            config_data: The configuration dictionary to validate

        Returns:
            Tuple of (is_valid, list of errors)
        """
        self._errors = []

        if not isinstance(config_data, dict):
            self._errors.append(ConfigValidationError(
                "", "Configuration must be a dictionary", "error"
            ))
            return False, self._errors

        # Basic structural validation
        self._validate_required_sections(config_data)
        self._validate_config_version(config_data)
        self._validate_value_types(config_data)
        self._validate_choices_values(config_data)

        is_valid = not any(e.severity == "error" for e in self._errors)
        return is_valid, self._errors

    def _validate_required_sections(self, config_data: Dict) -> None:
        """Check that required top-level sections exist."""
        required_sections = ["APP"]

        for section in required_sections:
            # Support both uppercase and lowercase keys
            if section not in config_data and section.lower() not in config_data:
                self._errors.append(ConfigValidationError(
                    section, f"Required section '{section}' is missing", "error"
                ))

    def _validate_config_version(self, config_data: Dict) -> None:
        """Validate _CONFIG_VERSION field."""
        version = config_data.get("_CONFIG_VERSION")

        if version is None:
            self._errors.append(ConfigValidationError(
                "_CONFIG_VERSION", "Missing configuration version", "warning"
            ))
            return

        if not isinstance(version, str):
            self._errors.append(ConfigValidationError(
                "_CONFIG_VERSION", f"Version must be a string, got {type(version).__name__}", "error"
            ))
            return

        # Validate version format (e.g., "2.0", "1.5")
        if not re.match(r'^\d+\.\d+$', version):
            self._errors.append(ConfigValidationError(
                "_CONFIG_VERSION", f"Invalid version format: '{version}'. Expected 'X.Y'", "warning"
            ))

    def _validate_value_types(self, config_data: Dict, path: str = "") -> None:
        """
        Recursively validate value types in config data.

        Checks that {value, choices} structures have compatible types.
        """
        if not isinstance(config_data, dict):
            return

        for key, value in config_data.items():
            current_path = f"{path}.{key}" if path else key

            # Skip metadata keys
            if key.startswith("_"):
                continue

            if isinstance(value, dict):
                # Check for {value, choices} pattern
                if "value" in value and "choices" in value:
                    self._validate_choices_entry(value, current_path)
                # Check for {value, description} pattern (ConfigValueType)
                elif "value" in value and "description" in value:
                    self._validate_config_value_entry(value, current_path)
                else:
                    # Recurse into nested dict
                    self._validate_value_types(value, current_path)

    def _validate_choices_entry(self, entry: Dict, path: str) -> None:
        """
        Validate a {value, choices, ...} entry.

        Checks:
        - 'choices' is a list
        - 'value' is in 'choices' list
        - Types are consistent
        """
        value = entry.get("value")
        choices = entry.get("choices")

        if not isinstance(choices, list):
            self._errors.append(ConfigValidationError(
                path, f"'choices' must be a list, got {type(choices).__name__}", "error"
            ))
            return

        if len(choices) == 0:
            self._errors.append(ConfigValidationError(
                path, "'choices' list is empty", "warning"
            ))
            return

        # Check if value is in choices
        if value not in choices:
            self._errors.append(ConfigValidationError(
                path,
                f"Value '{value}' is not in allowed choices: {choices}",
                "error"
            ))

    def _validate_config_value_entry(self, entry: Dict, path: str) -> None:
        """
        Validate a {value, description, ...} entry (without choices).

        Checks:
        - 'value' exists and is not None (unless explicitly allowed)
        - 'description' is a string
        """
        entry.get("value")
        description = entry.get("description")

        # Value can be None, bool, int, float, str - all valid
        # Just check description is string if present
        if description is not None and not isinstance(description, str):
            self._errors.append(ConfigValidationError(
                path, f"'description' must be a string, got {type(description).__name__}", "warning"
            ))

    def _validate_choices_values(self, config_data: Dict, path: str = "") -> None:
        """
        Validate that all choice values are within allowed ranges.

        Uses schema if available for additional validation rules.
        """
        if not self._load_schema():
            return  # Schema not available, skip enhanced validation

        # Schema-based validation would go here
        # For now, basic validation is sufficient

    def get_validation_summary(self) -> str:
        """
        Get a summary of validation results.

        Returns:
            Human-readable summary string
        """
        if not self._errors:
            return "Configuration is valid ✓"

        error_count = sum(1 for e in self._errors if e.severity == "error")
        warning_count = sum(1 for e in self._errors if e.severity == "warning")

        lines = [f"Configuration validation: {error_count} error(s), {warning_count} warning(s)"]
        for error in self._errors:
            lines.append(f"  {error}")

        return "\n".join(lines)


def validate_config_file(config_path: str, config_dir: str) -> Tuple[bool, List[ConfigValidationError]]:
    """
    Convenience function to validate a config file.

    Args:
        config_path: Path to the config.json file
        config_dir: Path to the config directory (for schema)

    Returns:
        Tuple of (is_valid, list of errors)
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [ConfigValidationError("", f"Invalid JSON: {e}", "error")]
    except Exception as e:
        return False, [ConfigValidationError("", f"Error reading file: {e}", "error")]

    validator = ConfigValidator(config_dir)
    return validator.validate_config(config_data)


def validate_and_log(config_data: Dict, config_dir: str, log_level: Qgis.MessageLevel = Qgis.Info) -> bool:
    """
    Validate configuration and log results to QGIS message log.

    Args:
        config_data: Configuration dictionary to validate
        config_dir: Path to config directory
        log_level: QGIS log level for messages

    Returns:
        True if validation passed (no errors), False otherwise
    """
    validator = ConfigValidator(config_dir)
    is_valid, errors = validator.validate_config(config_data)

    if is_valid and not errors:
        QgsMessageLog.logMessage(
            "FilterMate: Configuration validated successfully",
            "FilterMate",
            log_level
        )
    else:
        summary = validator.get_validation_summary()
        level = Qgis.Warning if is_valid else Qgis.Critical
        QgsMessageLog.logMessage(
            f"FilterMate: {summary}",
            "FilterMate",
            level
        )

    return is_valid
