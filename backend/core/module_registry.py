"""Module / Plugin Registry for extensible dashboard widgets."""
from typing import Dict, Any, List


class BaseModule:
    """Base interface for all backend widget modules."""
    module_id: str = "base"
    name: str = "Base Module"
    description: str = ""
    version: str = "1.0.0"

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.module_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

    def on_startup(self) -> None:
        """Hook called when application starts."""
        pass

    def on_cron_tick(self, now_dt) -> None:
        """Hook called every minute by the scheduler."""
        pass


class ModuleRegistry:
    def __init__(self):
        self._modules: Dict[str, BaseModule] = {}

    def register(self, module: BaseModule):
        self._modules[module.module_id] = module
        return module

    def get(self, module_id: str) -> BaseModule:
        return self._modules.get(module_id)

    def all_modules(self) -> List[BaseModule]:
        return list(self._modules.values())

    def list_metadata(self) -> List[Dict[str, Any]]:
        return [m.get_metadata() for m in self._modules.values()]


registry = ModuleRegistry()
