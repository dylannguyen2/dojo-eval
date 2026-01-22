import re
from abc import ABC, abstractmethod
from typing import Any, Dict


class Backend(ABC):
    @abstractmethod
    def query(self, query: dict[str, Any]) -> Any:
        """Execute a MongoDB query.

        Args:
            query: A dict with 'collection' and 'filter' keys, e.g.
                   {"collection": "users", "filter": {"_id": "0"}}

        Returns:
            List of matching documents (or single document if applicable)
        """
        pass

class BackendDictAdapter(Backend):
    """Adapter to wrap backend state dict as a Backend object."""

    def __init__(self, backend_state: Dict[str, Any]):
        self.backend_state = backend_state

    def query(self, query: dict[str, Any]) -> Any:
        collection = query.get("collection")
        filter_dict = query.get("filter", {})

        if collection not in self.backend_state:
            return []

        collection_data = self.backend_state[collection]
        if not isinstance(collection_data, list):
            return []

        results = []
        for item in collection_data:
            if not isinstance(item, dict):
                continue
            match = True
            for key, value in filter_dict.items():
                if isinstance(value, dict):
                    # Handle $in operator
                    if "$in" in value:
                        if item.get(key) not in value.get("$in", []):
                            match = False
                            break
                    # Handle $regex operator
                    elif "$regex" in value:
                        pattern = value.get("$regex", "")
                        options = value.get("$options", "")
                        flags = 0
                        if "i" in options:
                            flags |= re.IGNORECASE
                        item_value = item.get(key, "")
                        if not isinstance(item_value, str):
                            item_value = str(item_value) if item_value is not None else ""
                        try:
                            if not re.search(pattern, item_value, flags):
                                match = False
                                break
                        except re.error:
                            match = False
                            break
                    else:
                        # Unknown operator, treat as exact match
                        if item.get(key) != value:
                            match = False
                            break
                else:
                    if item.get(key) != value:
                        match = False
                        break
            if match:
                results.append(item)

        return results
