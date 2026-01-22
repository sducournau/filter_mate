"""
FilterMate Controller Registry.

Registry pattern for managing controller lifecycle and centralized access.
"""
from enum import IntEnum
from typing import Dict, Type, Optional, TypeVar, List

from .base_controller import BaseController

T = TypeVar('T', bound=BaseController)


class TabIndex(IntEnum):
    """
    Tab indices matching UI layout.
    
    These correspond to the tab positions in the main QTabWidget.
    Note: Exploring is in a separate frame, not a tab.
    """
    FILTERING = 0
    EXPORTING = 1
    CONFIGURATION = 2


class ControllerRegistry:
    """
    Registry for managing controller lifecycle.

    Provides centralized access to controllers and manages
    their setup/teardown in the correct order.

    Usage:
        registry = ControllerRegistry()
        
        # Register controllers
        registry.register('exploring', ExploringController(...))
        registry.register('filtering', FilteringController(...), tab_index=TabIndex.FILTERING)
        
        # Initialize all controllers
        registry.setup_all()
        
        # Access controllers
        filtering = registry.get_typed('filtering', FilteringController)
        
        # Handle tab switching
        registry.notify_tab_changed(old_index=0, new_index=1)
        
        # Cleanup
        registry.teardown_all()
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._controllers: Dict[str, BaseController] = {}
        self._tab_mapping: Dict[int, str] = {}
        self._registration_order: List[str] = []

    def register(
        self,
        name: str,
        controller: BaseController,
        tab_index: Optional[int] = None
    ) -> None:
        """
        Register a controller.

        Args:
            name: Unique name for the controller (e.g., 'exploring', 'filtering')
            controller: Controller instance (must inherit from BaseController)
            tab_index: Optional tab index for tab-based controllers

        Raises:
            ValueError: If name already registered or controller is invalid
        """
        if name in self._controllers:
            raise ValueError(f"Controller '{name}' already registered")
        
        if not isinstance(controller, BaseController):
            raise ValueError(
                f"Controller must inherit from BaseController, got {type(controller)}"
            )

        self._controllers[name] = controller
        self._registration_order.append(name)
        
        if tab_index is not None:
            self._tab_mapping[tab_index] = name

    def unregister(self, name: str) -> bool:
        """
        Unregister a controller.

        Args:
            name: Name of the controller to unregister

        Returns:
            True if successfully unregistered, False if not found
        """
        if name not in self._controllers:
            return False

        del self._controllers[name]
        
        if name in self._registration_order:
            self._registration_order.remove(name)
        
        # Remove from tab mapping
        for tab_index, ctrl_name in list(self._tab_mapping.items()):
            if ctrl_name == name:
                del self._tab_mapping[tab_index]
                break
        
        return True

    def get(self, name: str) -> Optional[BaseController]:
        """
        Get controller by name.

        Args:
            name: Registered name of the controller

        Returns:
            Controller instance or None if not found
        """
        return self._controllers.get(name)

    def get_typed(self, name: str, controller_type: Type[T]) -> Optional[T]:
        """
        Get controller with type checking.

        Args:
            name: Registered name of the controller
            controller_type: Expected controller class for type checking

        Returns:
            Controller instance with correct type, or None if not found or wrong type

        Example:
            filtering = registry.get_typed('filtering', FilteringController)
            if filtering:
                filtering.execute_filter()  # Type-safe access
        """
        controller = self._controllers.get(name)
        if controller is not None and isinstance(controller, controller_type):
            return controller
        return None

    def get_for_tab(self, tab_index: int) -> Optional[BaseController]:
        """
        Get controller for a specific tab index.

        Args:
            tab_index: Index of the tab (see TabIndex enum)

        Returns:
            Controller for that tab, or None if no controller registered
        """
        name = self._tab_mapping.get(tab_index)
        if name:
            return self._controllers.get(name)
        return None

    def get_all(self) -> Dict[str, BaseController]:
        """
        Get all registered controllers.

        Returns:
            Dictionary of name -> controller
        """
        return dict(self._controllers)

    def get_names(self) -> List[str]:
        """
        Get all registered controller names in registration order.

        Returns:
            List of controller names
        """
        return list(self._registration_order)

    def setup_all(self) -> int:
        """
        Set up all registered controllers.

        Calls setup() on each controller in registration order.

        Returns:
            Number of controllers set up
        """
        count = 0
        for name in self._registration_order:
            controller = self._controllers.get(name)
            if controller:
                try:
                    controller.setup()
                    count += 1
                except Exception as e:
                    import traceback
        return count

    def teardown_all(self) -> int:
        """
        Tear down all registered controllers in reverse order.

        Calls teardown() on each controller in reverse registration order.
        This ensures proper cleanup of dependencies.

        Returns:
            Number of controllers torn down
        """
        count = 0
        for name in reversed(self._registration_order):
            controller = self._controllers.get(name)
            if controller:
                controller.teardown()
                count += 1
        return count

    def notify_tab_changed(self, old_index: int, new_index: int) -> None:
        """
        Notify controllers of tab change.

        Calls on_tab_deactivated() on the old controller
        and on_tab_activated() on the new controller.

        Args:
            old_index: Previous tab index
            new_index: New tab index
        """
        old_controller = self.get_for_tab(old_index)
        new_controller = self.get_for_tab(new_index)

        if old_controller:
            old_controller.on_tab_deactivated()
        if new_controller:
            new_controller.on_tab_activated()

    def __len__(self) -> int:
        """Return number of registered controllers."""
        return len(self._controllers)

    def __contains__(self, name: str) -> bool:
        """Check if controller is registered."""
        return name in self._controllers

    def __repr__(self) -> str:
        """String representation for debugging."""
        names = list(self._controllers.keys())
        return f"<ControllerRegistry controllers={names}>"
