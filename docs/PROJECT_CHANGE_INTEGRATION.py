"""
Project Change Detection - Integration Example

This file shows how to integrate project change detection
and automatic config reset into filter_mate_app.py
"""

def on_project_loaded(self):
    """
    Called when a QGIS project is loaded.
    Detects if project has changed and resets configuration accordingly.
    """
    from config.config import ENV_VARS, load_default_config, save_config
    
    # Get current project info
    current_project_path = self.PROJECT.fileName()
    current_project_id = self.PROJECT.readEntry("FILTER_MATE", "PROJECT_ID", "")[0]
    
    if not current_project_id:
        # Generate new project ID
        import uuid
        current_project_id = str(uuid.uuid4())
        self.PROJECT.writeEntry("FILTER_MATE", "PROJECT_ID", current_project_id)
    
    # Get stored project info from config
    stored_project_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
    stored_project_id = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_ID"]
    
    # Check if project has changed
    project_changed = (
        current_project_path != stored_project_path or
        current_project_id != stored_project_id
    )
    
    if project_changed:
        print(f"FilterMate: Project changed from '{stored_project_path}' to '{current_project_path}'")
        
        # Load default config
        default_config = load_default_config()
        
        if default_config:
            # Reset CURRENT_PROJECT section to defaults
            self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"].copy()
            
            # Update with current project info
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"] = current_project_path
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_ID"] = current_project_id
            
            # Clear project-specific data
            self.CONFIG_DATA["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] = []
            self.CONFIG_DATA["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] = "EPSG:3857"
            self.CONFIG_DATA["CURRENT_PROJECT"]["layers"] = []
            
            # Save updated config
            success = save_config(self.CONFIG_DATA)
            
            if success:
                print("FilterMate: Configuration reset for new project")
                
                # Show message to user
                from qgis.utils import iface
                iface.messageBar().pushInfo(
                    "FilterMate",
                    "Project settings reset for new project",
                    3
                )
            else:
                print("FilterMate: Failed to save configuration")
        else:
            print("FilterMate: Failed to load default configuration")
    else:
        print(f"FilterMate: Same project loaded: '{current_project_path}'")


def add_project_change_detection(app_instance):
    """
    Add project change detection to FilterMate app.
    
    Call this in __init__ or run():
    
    # In __init__
    self.PROJECT.readProject.connect(self.on_project_loaded)
    
    # Or use this helper
    add_project_change_detection(self)
    """
    if hasattr(app_instance, 'PROJECT'):
        app_instance.PROJECT.readProject.connect(app_instance.on_project_loaded)
        print("FilterMate: Project change detection enabled")


# Integration code for filter_mate_app.py __init__ method:
"""
class FilterMateApp:
    def __init__(self, iface):
        # ... existing code ...
        
        # Add project change detection
        self.PROJECT.readProject.connect(self.on_project_loaded)
        
        # ... rest of __init__ ...
    
    def on_project_loaded(self):
        '''Detects project changes and resets config'''
        from config.config import load_default_config, save_config
        
        current_project_path = self.PROJECT.fileName()
        stored_project_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
        
        if current_project_path != stored_project_path:
            # Project changed - reset
            default_config = load_default_config()
            if default_config:
                self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"].copy()
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"] = current_project_path
                save_config(self.CONFIG_DATA)
                
                from qgis.utils import iface
                iface.messageBar().pushInfo("FilterMate", "Project settings reset", 3)
"""


# Alternative: Manual check in run() method
"""
def run(self):
    '''Main plugin execution'''
    
    # Check if project changed before showing dockwidget
    self._check_project_change()
    
    # ... rest of run() ...

def _check_project_change(self):
    '''Check and handle project change'''
    from config.config import load_default_config, save_config
    
    current_path = self.PROJECT.fileName()
    stored_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
    
    if current_path != stored_path:
        default_config = load_default_config()
        if default_config:
            # Reset project settings
            self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"]
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"] = current_path
            save_config(self.CONFIG_DATA)
"""
