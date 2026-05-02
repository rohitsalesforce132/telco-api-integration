"""
TMF931 Resource Catalog API - Resource Catalog Management
Implements TM Forum TMF931 Resource Catalog standard
"""

import json
import time
import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum


class CatalogLifecycleState(Enum):
    """Catalog lifecycle states"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    RETIRED = "retired"
    ARCHIVED = "archived"


class ResourceSpecType(Enum):
    """Resource specification types"""
    LOGICAL = "logical"
    PHYSICAL = "physical"
    HYBRID = "hybrid"


@dataclass
class ResourceCategory:
    """Resource category in tree structure"""
    category_id: str
    name: str
    description: str
    parent_id: Optional[str] = None
    path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ResourceSpecification:
    """Resource specification definition"""
    spec_id: str
    name: str
    description: str
    spec_type: ResourceSpecType
    version: str = "1.0.0"
    attributes: Dict[str, Any] = field(default_factory=dict)
    category_id: Optional[str] = None
    valid_for: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class ResourceCandidate:
    """Resource candidate - what can be sold/provisioned"""
    candidate_id: str
    name: str
    description: str
    spec_id: str
    category_id: Optional[str] = None
    is_sellable: bool = True
    is_bundlable: bool = False
    pricing: Dict[str, Any] = field(default_factory=dict)
    valid_for: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class Catalog:
    """Catalog container"""
    catalog_id: str
    name: str
    description: str
    lifecycle_state: CatalogLifecycleState = CatalogLifecycleState.DRAFT
    version: int = 1
    categories: Dict[str, ResourceCategory] = field(default_factory=dict)
    specifications: Dict[str, ResourceSpecification] = field(default_factory=dict)
    candidates: Dict[str, ResourceCandidate] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    published_at: Optional[float] = None
    retired_at: Optional[float] = None


class ResourceCatalogManager:
    """Full CRUD for TMF931 resource catalogs"""

    def __init__(self):
        self._catalogs: Dict[str, Catalog] = {}
        self._counter = 0

    def create_catalog(self, name: str, description: str,
                       metadata: Optional[Dict[str, Any]] = None) -> Catalog:
        """Create a new catalog"""
        catalog_id = self._generate_id("catalog")
        catalog = Catalog(
            catalog_id=catalog_id,
            name=name,
            description=description,
            metadata=metadata or {}
        )
        self._catalogs[catalog_id] = catalog
        return catalog

    def get_catalog(self, catalog_id: str) -> Optional[Catalog]:
        """Get catalog by ID"""
        return self._catalogs.get(catalog_id)

    def list_catalogs(self, state: Optional[CatalogLifecycleState] = None) -> List[Catalog]:
        """List all catalogs, optionally filtered by state"""
        catalogs = list(self._catalogs.values())
        if state:
            catalogs = [c for c in catalogs if c.lifecycle_state == state]
        return catalogs

    def update_catalog(self, catalog_id: str, **kwargs) -> Catalog:
        """Update catalog attributes"""
        catalog = self._get_catalog_or_raise(catalog_id)

        for key, value in kwargs.items():
            if hasattr(catalog, key) and key not in ('catalog_id', 'created_at'):
                setattr(catalog, key, value)

        return catalog

    def delete_catalog(self, catalog_id: str) -> bool:
        """Delete catalog"""
        if catalog_id in self._catalogs:
            del self._catalogs[catalog_id]
            return True
        return False

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"

    def _get_catalog_or_raise(self, catalog_id: str) -> Catalog:
        """Get catalog or raise exception"""
        catalog = self.get_catalog(catalog_id)
        if not catalog:
            raise ValueError(f"Catalog not found: {catalog_id}")
        return catalog


class ResourceCategoryManager:
    """Manages resource categories in tree structure"""

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager
        self._counter = 0

    def create_category(self, catalog_id: str, name: str, description: str,
                        parent_id: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> ResourceCategory:
        """Create a resource category"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        category_id = self._generate_id("category")
        path = self._build_path(catalog, parent_id, name)

        category = ResourceCategory(
            category_id=category_id,
            name=name,
            description=description,
            parent_id=parent_id,
            path=path,
            metadata=metadata or {}
        )
        catalog.categories[category_id] = category
        return category

    def get_category(self, catalog_id: str, category_id: str) -> Optional[ResourceCategory]:
        """Get category by ID"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return None
        return catalog.categories.get(category_id)

    def list_categories(self, catalog_id: str,
                        parent_id: Optional[str] = None) -> List[ResourceCategory]:
        """List categories, optionally filtered by parent"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return []

        categories = list(catalog.categories.values())
        if parent_id is not None:
            categories = [c for c in categories if c.parent_id == parent_id]
        return categories

    def update_category(self, catalog_id: str, category_id: str,
                        **kwargs) -> ResourceCategory:
        """Update category attributes"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        if category_id not in catalog.categories:
            raise ValueError(f"Category not found: {category_id}")

        category = catalog.categories[category_id]
        for key, value in kwargs.items():
            if hasattr(category, key) and key not in ('category_id', 'created_at', 'path'):
                setattr(category, key, value)

        return category

    def delete_category(self, catalog_id: str, category_id: str) -> bool:
        """Delete category (if no children)"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        # Check for children
        children = [c for c in catalog.categories.values() if c.parent_id == category_id]
        if children:
            raise ValueError("Cannot delete category with children")

        if category_id in catalog.categories:
            del catalog.categories[category_id]
            return True
        return False

    def get_category_tree(self, catalog_id: str) -> List[Dict[str, Any]]:
        """Get category hierarchy as tree"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return []

        # Build parent->children mapping
        children_map: Dict[str, List[ResourceCategory]] = {}
        root_categories = []

        for category in catalog.categories.values():
            if category.parent_id is None:
                root_categories.append(category)
            else:
                if category.parent_id not in children_map:
                    children_map[category.parent_id] = []
                children_map[category.parent_id].append(category)

        # Recursively build tree
        def build_tree(category: ResourceCategory) -> Dict[str, Any]:
            node = {
                "category_id": category.category_id,
                "name": category.name,
                "description": category.description,
                "path": category.path,
                "children": []
            }

            if category.category_id in children_map:
                node["children"] = [build_tree(c) for c in children_map[category.category_id]]

            return node

        return [build_tree(c) for c in root_categories]

    def _build_path(self, catalog: Catalog, parent_id: Optional[str], name: str) -> str:
        """Build category path"""
        if parent_id is None:
            return f"/{name}"

        parent = catalog.categories.get(parent_id)
        if not parent:
            return f"/{name}"

        return f"{parent.path}/{name}"

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class ResourceSpecificationManager:
    """Manages resource specifications (logical, physical, hybrid)"""

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager
        self._counter = 0

    def create_specification(self, catalog_id: str, name: str, description: str,
                            spec_type: ResourceSpecType,
                            attributes: Optional[Dict[str, Any]] = None,
                            category_id: Optional[str] = None,
                            valid_for: Optional[Dict[str, Any]] = None) -> ResourceSpecification:
        """Create a resource specification"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        # Validate category exists
        if category_id and category_id not in catalog.categories:
            raise ValueError(f"Category not found: {category_id}")

        spec_id = self._generate_id("spec")
        spec = ResourceSpecification(
            spec_id=spec_id,
            name=name,
            description=description,
            spec_type=spec_type,
            attributes=attributes or {},
            category_id=category_id,
            valid_for=valid_for
        )
        catalog.specifications[spec_id] = spec
        return spec

    def get_specification(self, catalog_id: str, spec_id: str) -> Optional[ResourceSpecification]:
        """Get specification by ID"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return None
        return catalog.specifications.get(spec_id)

    def list_specifications(self, catalog_id: str,
                            spec_type: Optional[ResourceSpecType] = None,
                            category_id: Optional[str] = None) -> List[ResourceSpecification]:
        """List specifications with filters"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return []

        specs = list(catalog.specifications.values())

        if spec_type:
            specs = [s for s in specs if s.spec_type == spec_type]

        if category_id:
            specs = [s for s in specs if s.category_id == category_id]

        return specs

    def update_specification(self, catalog_id: str, spec_id: str,
                            **kwargs) -> ResourceSpecification:
        """Update specification attributes"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        if spec_id not in catalog.specifications:
            raise ValueError(f"Specification not found: {spec_id}")

        spec = catalog.specifications[spec_id]
        for key, value in kwargs.items():
            if hasattr(spec, key) and key not in ('spec_id', 'created_at'):
                setattr(spec, key, value)

        return spec

    def delete_specification(self, catalog_id: str, spec_id: str) -> bool:
        """Delete specification"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        # Check if used by any candidates
        candidates_with_spec = [c for c in catalog.candidates.values() if c.spec_id == spec_id]
        if candidates_with_spec:
            raise ValueError("Cannot delete specification used by candidates")

        if spec_id in catalog.specifications:
            del catalog.specifications[spec_id]
            return True
        return False

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class ResourceCandidateManager:
    """Manages resource candidates (what can be sold/provisioned)"""

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager
        self._counter = 0

    def create_candidate(self, catalog_id: str, name: str, description: str,
                        spec_id: str,
                        is_sellable: bool = True,
                        is_bundlable: bool = False,
                        pricing: Optional[Dict[str, Any]] = None,
                        category_id: Optional[str] = None,
                        valid_for: Optional[Dict[str, Any]] = None) -> ResourceCandidate:
        """Create a resource candidate"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        # Validate spec exists
        if spec_id not in catalog.specifications:
            raise ValueError(f"Specification not found: {spec_id}")

        # Validate category exists
        if category_id and category_id not in catalog.categories:
            raise ValueError(f"Category not found: {category_id}")

        candidate_id = self._generate_id("candidate")
        candidate = ResourceCandidate(
            candidate_id=candidate_id,
            name=name,
            description=description,
            spec_id=spec_id,
            category_id=category_id,
            is_sellable=is_sellable,
            is_bundlable=is_bundlable,
            pricing=pricing or {},
            valid_for=valid_for
        )
        catalog.candidates[candidate_id] = candidate
        return candidate

    def get_candidate(self, catalog_id: str, candidate_id: str) -> Optional[ResourceCandidate]:
        """Get candidate by ID"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return None
        return catalog.candidates.get(candidate_id)

    def list_candidates(self, catalog_id: str,
                        is_sellable: Optional[bool] = None,
                        category_id: Optional[str] = None) -> List[ResourceCandidate]:
        """List candidates with filters"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return []

        candidates = list(catalog.candidates.values())

        if is_sellable is not None:
            candidates = [c for c in candidates if c.is_sellable == is_sellable]

        if category_id:
            candidates = [c for c in candidates if c.category_id == category_id]

        return candidates

    def update_candidate(self, catalog_id: str, candidate_id: str,
                        **kwargs) -> ResourceCandidate:
        """Update candidate attributes"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        if candidate_id not in catalog.candidates:
            raise ValueError(f"Candidate not found: {candidate_id}")

        candidate = catalog.candidates[candidate_id]
        for key, value in kwargs.items():
            if hasattr(candidate, key) and key not in ('candidate_id', 'created_at'):
                setattr(candidate, key, value)

        return candidate

    def delete_candidate(self, catalog_id: str, candidate_id: str) -> bool:
        """Delete candidate"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        if candidate_id in catalog.candidates:
            del catalog.candidates[candidate_id]
            return True
        return False

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class CatalogLifecycleManager:
    """Manages catalog lifecycle states"""

    VALID_TRANSITIONS = {
        CatalogLifecycleState.DRAFT: [CatalogLifecycleState.PUBLISHED, CatalogLifecycleState.ARCHIVED],
        CatalogLifecycleState.PUBLISHED: [CatalogLifecycleState.ACTIVE, CatalogLifecycleState.DRAFT, CatalogLifecycleState.ARCHIVED],
        CatalogLifecycleState.ACTIVE: [CatalogLifecycleState.RETIRED, CatalogLifecycleState.ARCHIVED],
        CatalogLifecycleState.RETIRED: [CatalogLifecycleState.ARCHIVED],
        CatalogLifecycleState.ARCHIVED: []
    }

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager

    def transition_state(self, catalog_id: str, new_state: CatalogLifecycleState) -> Catalog:
        """Transition catalog to new state"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)
        current_state = catalog.lifecycle_state

        # Validate transition
        if new_state not in self.VALID_TRANSITIONS.get(current_state, []):
            raise ValueError(f"Invalid transition from {current_state.value} to {new_state.value}")

        # Update state and timestamps
        old_state = catalog.lifecycle_state
        catalog.lifecycle_state = new_state

        if new_state == CatalogLifecycleState.PUBLISHED:
            catalog.published_at = time.time()
        elif new_state == CatalogLifecycleState.RETIRED:
            catalog.retired_at = time.time()

        return catalog

    def can_transition(self, catalog_id: str, new_state: CatalogLifecycleState) -> bool:
        """Check if transition is valid"""
        catalog = self.catalog_manager.get_catalog(catalog_id)
        if not catalog:
            return False

        return new_state in self.VALID_TRANSITIONS.get(catalog.lifecycle_state, [])


class CatalogImportExport:
    """Import/export catalog data in TMF format"""

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager

    def export_catalog(self, catalog_id: str) -> Dict[str, Any]:
        """Export catalog to TMF format"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        export_data = {
            "catalog": {
                "id": catalog.catalog_id,
                "name": catalog.name,
                "description": catalog.description,
                "lifecycleState": catalog.lifecycle_state.value,
                "version": catalog.version,
                "metadata": catalog.metadata,
                "createdAt": catalog.created_at,
                "publishedAt": catalog.published_at,
                "retiredAt": catalog.retired_at
            },
            "categories": [
                {
                    "id": c.category_id,
                    "name": c.name,
                    "description": c.description,
                    "parentId": c.parent_id,
                    "path": c.path,
                    "metadata": c.metadata,
                    "createdAt": c.created_at
                }
                for c in catalog.categories.values()
            ],
            "specifications": [
                {
                    "id": s.spec_id,
                    "name": s.name,
                    "description": s.description,
                    "type": s.spec_type.value,
                    "version": s.version,
                    "attributes": s.attributes,
                    "categoryId": s.category_id,
                    "validFor": s.valid_for,
                    "createdAt": s.created_at
                }
                for s in catalog.specifications.values()
            ],
            "candidates": [
                {
                    "id": c.candidate_id,
                    "name": c.name,
                    "description": c.description,
                    "specId": c.spec_id,
                    "categoryId": c.category_id,
                    "isSellable": c.is_sellable,
                    "isBundlable": c.is_bundlable,
                    "pricing": c.pricing,
                    "validFor": c.valid_for,
                    "createdAt": c.created_at
                }
                for c in catalog.candidates.values()
            ]
        }

        return export_data

    def import_catalog(self, data: Dict[str, Any]) -> Catalog:
        """Import catalog from TMF format"""
        catalog_data = data.get("catalog", {})
        categories_data = data.get("categories", [])
        specs_data = data.get("specifications", [])
        candidates_data = data.get("candidates", [])

        # Create catalog
        catalog = self.catalog_manager.create_catalog(
            name=catalog_data.get("name", "Imported Catalog"),
            description=catalog_data.get("description", ""),
            metadata=catalog_data.get("metadata", {})
        )

        # Update catalog fields
        if "version" in catalog_data:
            catalog.version = catalog_data["version"]
        if "lifecycleState" in catalog_data:
            catalog.lifecycle_state = CatalogLifecycleState(catalog_data["lifecycleState"])

        # Import categories
        category_mgr = ResourceCategoryManager(self.catalog_manager)
        category_map: Dict[str, str] = {}

        for cat_data in categories_data:
            category = category_mgr.create_category(
                catalog_id=catalog.catalog_id,
                name=cat_data.get("name", ""),
                description=cat_data.get("description", ""),
                parent_id=cat_data.get("parentId"),
                metadata=cat_data.get("metadata")
            )
            category_map[cat_data["id"]] = category.category_id

        # Import specifications
        spec_mgr = ResourceSpecificationManager(self.catalog_manager)
        spec_map: Dict[str, str] = {}

        for spec_data in specs_data:
            old_cat_id = spec_data.get("categoryId")
            new_cat_id = category_map.get(old_cat_id) if old_cat_id else None

            spec = spec_mgr.create_specification(
                catalog_id=catalog.catalog_id,
                name=spec_data.get("name", ""),
                description=spec_data.get("description", ""),
                spec_type=ResourceSpecType(spec_data.get("type", "logical")),
                attributes=spec_data.get("attributes", {}),
                category_id=new_cat_id,
                valid_for=spec_data.get("validFor")
            )
            spec_map[spec_data["id"]] = spec.spec_id

        # Import candidates
        candidate_mgr = ResourceCandidateManager(self.catalog_manager)

        for cand_data in candidates_data:
            old_cat_id = cand_data.get("categoryId")
            new_cat_id = category_map.get(old_cat_id) if old_cat_id else None
            old_spec_id = cand_data.get("specId")
            new_spec_id = spec_map.get(old_spec_id) if old_spec_id else None

            if new_spec_id:
                candidate_mgr.create_candidate(
                    catalog_id=catalog.catalog_id,
                    name=cand_data.get("name", ""),
                    description=cand_data.get("description", ""),
                    spec_id=new_spec_id,
                    is_sellable=cand_data.get("isSellable", True),
                    is_bundlable=cand_data.get("isBundlable", False),
                    pricing=cand_data.get("pricing", {}),
                    category_id=new_cat_id,
                    valid_for=cand_data.get("validFor")
                )

        return catalog


class CatalogVersionManager:
    """Version management for catalog changes"""

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager
        self._versions: Dict[str, List[Dict[str, Any]]] = {}

    def create_version(self, catalog_id: str, version_label: Optional[str] = None) -> Dict[str, Any]:
        """Create a version snapshot of the catalog"""
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        version_data = {
            "version": catalog.version,
            "label": version_label or f"v{catalog.version}",
            "timestamp": time.time(),
            "lifecycleState": catalog.lifecycle_state.value,
            "snapshot": self._serialize_catalog(catalog)
        }

        if catalog_id not in self._versions:
            self._versions[catalog_id] = []

        self._versions[catalog_id].append(version_data)

        # Increment catalog version
        catalog.version += 1

        return version_data

    def get_version(self, catalog_id: str, version: int) -> Optional[Dict[str, Any]]:
        """Get specific version of catalog"""
        if catalog_id not in self._versions:
            return None

        for v in self._versions[catalog_id]:
            if v["version"] == version:
                return v

        return None

    def list_versions(self, catalog_id: str) -> List[Dict[str, Any]]:
        """List all versions of catalog"""
        return self._versions.get(catalog_id, [])

    def restore_version(self, catalog_id: str, version: int) -> Catalog:
        """Restore catalog to specific version"""
        version_data = self.get_version(catalog_id, version)
        if not version_data:
            raise ValueError(f"Version not found: {version}")

        snapshot = version_data["snapshot"]
        catalog = self.catalog_manager._get_catalog_or_raise(catalog_id)

        # Restore from snapshot
        catalog.name = snapshot["name"]
        catalog.description = snapshot["description"]
        catalog.lifecycle_state = CatalogLifecycleState(snapshot["lifecycleState"])
        catalog.version = snapshot["version"]
        catalog.metadata = snapshot["metadata"]

        return catalog

    def _serialize_catalog(self, catalog: Catalog) -> Dict[str, Any]:
        """Serialize catalog for versioning"""
        return {
            "name": catalog.name,
            "description": catalog.description,
            "version": catalog.version,
            "lifecycleState": catalog.lifecycle_state.value,
            "metadata": catalog.metadata,
            "categoriesCount": len(catalog.categories),
            "specificationsCount": len(catalog.specifications),
            "candidatesCount": len(catalog.candidates)
        }


class CatalogSearchEngine:
    """Search across catalogs with TMF filtering"""

    def __init__(self, catalog_manager: ResourceCatalogManager):
        self.catalog_manager = catalog_manager

    def search(self, catalog_id: Optional[str] = None,
               filters: Optional[Dict[str, Any]] = None,
               limit: int = 100) -> List[Dict[str, Any]]:
        """Search with TMF-style filters (field=value, field.gt=value, etc.)"""
        results = []

        catalogs = self.catalog_manager.list_catalogs()
        if catalog_id:
            catalogs = [c for c in catalogs if c.catalog_id == catalog_id]

        for catalog in catalogs:
            # Search categories
            for category in catalog.categories.values():
                if self._match_filters(category, filters):
                    results.append({
                        "type": "category",
                        "catalogId": catalog.catalog_id,
                        "catalogName": catalog.name,
                        "item": category
                    })

            # Search specifications
            for spec in catalog.specifications.values():
                if self._match_filters(spec, filters):
                    results.append({
                        "type": "specification",
                        "catalogId": catalog.catalog_id,
                        "catalogName": catalog.name,
                        "item": spec
                    })

            # Search candidates
            for candidate in catalog.candidates.values():
                if self._match_filters(candidate, filters):
                    results.append({
                        "type": "candidate",
                        "catalogId": catalog.catalog_id,
                        "catalogName": catalog.name,
                        "item": candidate
                    })

        if limit:
            results = results[:limit]

        return results

    def _match_filters(self, item: Any, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if item matches filters"""
        if not filters:
            return True

        for filter_expr, filter_value in filters.items():
            if "." not in filter_expr:
                field = filter_expr
                operator = "eq"
            else:
                parts = filter_expr.split(".", 1)
                field = parts[0]
                operator = parts[1]

            item_value = getattr(item, field, None)

            if not self._apply_operator(item_value, operator, filter_value):
                return False

        return True

    def _apply_operator(self, item_value: Any, operator: str, filter_value: Any) -> bool:
        """Apply comparison operator"""
        if operator == "eq":
            return item_value == filter_value
        elif operator == "ne":
            return item_value != filter_value
        elif operator == "gt":
            return item_value is not None and item_value > filter_value
        elif operator == "gte":
            return item_value is not None and item_value >= filter_value
        elif operator == "lt":
            return item_value is not None and item_value < filter_value
        elif operator == "lte":
            return item_value is not None and item_value <= filter_value
        elif operator == "in":
            return item_value in filter_value if isinstance(filter_value, (list, tuple, set)) else False
        elif operator == "contains":
            return filter_value in str(item_value) if item_value else False
        else:
            return True
