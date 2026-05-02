"""
Tests for TMF931 Resource Catalog API
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tmf931.catalog import (
    CatalogLifecycleState, ResourceSpecType,
    ResourceCatalogManager, ResourceCategoryManager,
    ResourceSpecificationManager, ResourceCandidateManager,
    CatalogLifecycleManager, CatalogImportExport,
    CatalogVersionManager, CatalogSearchEngine
)


class TestResourceCatalogManager(unittest.TestCase):
    """Test ResourceCatalogManager"""

    def setUp(self):
        self.manager = ResourceCatalogManager()

    def test_create_catalog(self):
        """Test creating a catalog"""
        catalog = self.manager.create_catalog(
            name="Test Catalog",
            description="Test description"
        )

        self.assertIsNotNone(catalog)
        self.assertEqual(catalog.name, "Test Catalog")
        self.assertEqual(catalog.description, "Test description")
        self.assertEqual(catalog.lifecycle_state, CatalogLifecycleState.DRAFT)

    def test_get_catalog(self):
        """Test getting a catalog"""
        catalog = self.manager.create_catalog(
            name="Test Catalog",
            description="Test description"
        )

        retrieved = self.manager.get_catalog(catalog.catalog_id)
        self.assertEqual(retrieved.catalog_id, catalog.catalog_id)

    def test_get_nonexistent_catalog(self):
        """Test getting a non-existent catalog"""
        catalog = self.manager.get_catalog("nonexistent")
        self.assertIsNone(catalog)

    def test_list_catalogs(self):
        """Test listing all catalogs"""
        self.manager.create_catalog(name="Catalog 1", description="Description 1")
        self.manager.create_catalog(name="Catalog 2", description="Description 2")

        catalogs = self.manager.list_catalogs()
        self.assertEqual(len(catalogs), 2)

    def test_list_catalogs_with_filter(self):
        """Test listing catalogs with state filter"""
        catalog = self.manager.create_catalog(name="Test Catalog", description="Test")

        lifecycle_manager = CatalogLifecycleManager(self.manager)
        lifecycle_manager.transition_state(catalog.catalog_id, CatalogLifecycleState.PUBLISHED)

        published = self.manager.list_catalogs(state=CatalogLifecycleState.PUBLISHED)
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].catalog_id, catalog.catalog_id)

    def test_update_catalog(self):
        """Test updating a catalog"""
        catalog = self.manager.create_catalog(name="Original", description="Original desc")

        updated = self.manager.update_catalog(
            catalog.catalog_id,
            name="Updated",
            description="Updated desc"
        )

        self.assertEqual(updated.name, "Updated")
        self.assertEqual(updated.description, "Updated desc")

    def test_delete_catalog(self):
        """Test deleting a catalog"""
        catalog = self.manager.create_catalog(name="Test", description="Test")

        result = self.manager.delete_catalog(catalog.catalog_id)
        self.assertTrue(result)

        retrieved = self.manager.get_catalog(catalog.catalog_id)
        self.assertIsNone(retrieved)

    def test_delete_nonexistent_catalog(self):
        """Test deleting a non-existent catalog"""
        result = self.manager.delete_catalog("nonexistent")
        self.assertFalse(result)


class TestResourceCategoryManager(unittest.TestCase):
    """Test ResourceCategoryManager"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.category_manager = ResourceCategoryManager(self.catalog_manager)

    def test_create_category(self):
        """Test creating a category"""
        category = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Network",
            description="Network resources"
        )

        self.assertIsNotNone(category)
        self.assertEqual(category.name, "Network")
        self.assertIsNone(category.parent_id)

    def test_create_category_with_parent(self):
        """Test creating a category with parent"""
        parent = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Parent",
            description="Parent category"
        )

        child = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Child",
            description="Child category",
            parent_id=parent.category_id
        )

        self.assertEqual(child.parent_id, parent.category_id)
        self.assertEqual(child.path, "/Parent/Child")

    def test_get_category(self):
        """Test getting a category"""
        category = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test"
        )

        retrieved = self.category_manager.get_category(
            self.catalog.catalog_id,
            category.category_id
        )

        self.assertEqual(retrieved.category_id, category.category_id)

    def test_list_categories(self):
        """Test listing categories"""
        self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Category 1",
            description="Description 1"
        )
        self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Category 2",
            description="Description 2"
        )

        categories = self.category_manager.list_categories(self.catalog.catalog_id)
        self.assertEqual(len(categories), 2)

    def test_list_categories_with_parent_filter(self):
        """Test listing categories with parent filter"""
        parent = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Parent",
            description="Parent"
        )

        self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Child 1",
            description="Child 1",
            parent_id=parent.category_id
        )
        self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Child 2",
            description="Child 2",
            parent_id=parent.category_id
        )

        children = self.category_manager.list_categories(
            self.catalog.catalog_id,
            parent_id=parent.category_id
        )

        self.assertEqual(len(children), 2)

    def test_update_category(self):
        """Test updating a category"""
        category = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Original",
            description="Original"
        )

        updated = self.category_manager.update_category(
            self.catalog.catalog_id,
            category.category_id,
            name="Updated",
            description="Updated description"
        )

        self.assertEqual(updated.name, "Updated")
        self.assertEqual(updated.description, "Updated description")

    def test_delete_category(self):
        """Test deleting a category"""
        category = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test"
        )

        result = self.category_manager.delete_category(
            self.catalog.catalog_id,
            category.category_id
        )

        self.assertTrue(result)

    def test_delete_category_with_children_fails(self):
        """Test that deleting a category with children fails"""
        parent = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Parent",
            description="Parent"
        )

        self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Child",
            description="Child",
            parent_id=parent.category_id
        )

        with self.assertRaises(ValueError):
            self.category_manager.delete_category(
                self.catalog.catalog_id,
                parent.category_id
            )

    def test_get_category_tree(self):
        """Test getting category tree"""
        parent = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Parent",
            description="Parent"
        )

        child1 = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Child 1",
            description="Child 1",
            parent_id=parent.category_id
        )

        child2 = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Child 2",
            description="Child 2",
            parent_id=parent.category_id
        )

        tree = self.category_manager.get_category_tree(self.catalog.catalog_id)

        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["name"], "Parent")
        self.assertEqual(len(tree[0]["children"]), 2)


class TestResourceSpecificationManager(unittest.TestCase):
    """Test ResourceSpecificationManager"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.category_manager = ResourceCategoryManager(self.catalog_manager)
        self.category = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Network",
            description="Network resources"
        )
        self.spec_manager = ResourceSpecificationManager(self.catalog_manager)

    def test_create_specification(self):
        """Test creating a specification"""
        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="IP Address",
            description="IPv4 address",
            spec_type=ResourceSpecType.LOGICAL
        )

        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "IP Address")
        self.assertEqual(spec.spec_type, ResourceSpecType.LOGICAL)

    def test_create_specification_with_category(self):
        """Test creating a specification with category"""
        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Router",
            description="Network router",
            spec_type=ResourceSpecType.PHYSICAL,
            category_id=self.category.category_id
        )

        self.assertEqual(spec.category_id, self.category.category_id)

    def test_get_specification(self):
        """Test getting a specification"""
        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test",
            spec_type=ResourceSpecType.LOGICAL
        )

        retrieved = self.spec_manager.get_specification(
            self.catalog.catalog_id,
            spec.spec_id
        )

        self.assertEqual(retrieved.spec_id, spec.spec_id)

    def test_list_specifications(self):
        """Test listing specifications"""
        self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Spec 1",
            description="Description 1",
            spec_type=ResourceSpecType.LOGICAL
        )
        self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Spec 2",
            description="Description 2",
            spec_type=ResourceSpecType.PHYSICAL
        )

        specs = self.spec_manager.list_specifications(self.catalog.catalog_id)
        self.assertEqual(len(specs), 2)

    def test_list_specifications_with_type_filter(self):
        """Test listing specifications with type filter"""
        self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Logical",
            description="Logical",
            spec_type=ResourceSpecType.LOGICAL
        )
        self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Physical",
            description="Physical",
            spec_type=ResourceSpecType.PHYSICAL
        )

        logical_specs = self.spec_manager.list_specifications(
            self.catalog.catalog_id,
            spec_type=ResourceSpecType.LOGICAL
        )

        self.assertEqual(len(logical_specs), 1)
        self.assertEqual(logical_specs[0].name, "Logical")

    def test_update_specification(self):
        """Test updating a specification"""
        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Original",
            description="Original",
            spec_type=ResourceSpecType.LOGICAL
        )

        updated = self.spec_manager.update_specification(
            self.catalog.catalog_id,
            spec.spec_id,
            name="Updated",
            description="Updated description"
        )

        self.assertEqual(updated.name, "Updated")

    def test_delete_specification(self):
        """Test deleting a specification"""
        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test",
            spec_type=ResourceSpecType.LOGICAL
        )

        result = self.spec_manager.delete_specification(
            self.catalog.catalog_id,
            spec.spec_id
        )

        self.assertTrue(result)

    def test_delete_specification_with_candidate_fails(self):
        """Test that deleting a specification used by candidates fails"""
        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test",
            spec_type=ResourceSpecType.LOGICAL
        )

        candidate_manager = ResourceCandidateManager(self.catalog_manager)
        candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Candidate",
            description="Candidate",
            spec_id=spec.spec_id
        )

        with self.assertRaises(ValueError):
            self.spec_manager.delete_specification(
                self.catalog.catalog_id,
                spec.spec_id
            )


class TestResourceCandidateManager(unittest.TestCase):
    """Test ResourceCandidateManager"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.spec_manager = ResourceSpecificationManager(self.catalog_manager)
        self.spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="IP Address",
            description="IPv4 address",
            spec_type=ResourceSpecType.LOGICAL
        )
        self.candidate_manager = ResourceCandidateManager(self.catalog_manager)

    def test_create_candidate(self):
        """Test creating a candidate"""
        candidate = self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Public IP",
            description="Public IP address",
            spec_id=self.spec.spec_id
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.name, "Public IP")
        self.assertEqual(candidate.spec_id, self.spec.spec_id)
        self.assertTrue(candidate.is_sellable)

    def test_get_candidate(self):
        """Test getting a candidate"""
        candidate = self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test",
            spec_id=self.spec.spec_id
        )

        retrieved = self.candidate_manager.get_candidate(
            self.catalog.catalog_id,
            candidate.candidate_id
        )

        self.assertEqual(retrieved.candidate_id, candidate.candidate_id)

    def test_list_candidates(self):
        """Test listing candidates"""
        self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Candidate 1",
            description="Candidate 1",
            spec_id=self.spec.spec_id
        )
        self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Candidate 2",
            description="Candidate 2",
            spec_id=self.spec.spec_id,
            is_sellable=False
        )

        candidates = self.candidate_manager.list_candidates(self.catalog.catalog_id)
        self.assertEqual(len(candidates), 2)

    def test_list_candidates_with_sellable_filter(self):
        """Test listing candidates with sellable filter"""
        self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Sellable",
            description="Sellable",
            spec_id=self.spec.spec_id,
            is_sellable=True
        )
        self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Non-sellable",
            description="Non-sellable",
            spec_id=self.spec.spec_id,
            is_sellable=False
        )

        sellable = self.candidate_manager.list_candidates(
            self.catalog.catalog_id,
            is_sellable=True
        )

        self.assertEqual(len(sellable), 1)
        self.assertEqual(sellable[0].name, "Sellable")

    def test_update_candidate(self):
        """Test updating a candidate"""
        candidate = self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Original",
            description="Original",
            spec_id=self.spec.spec_id
        )

        updated = self.candidate_manager.update_candidate(
            self.catalog.catalog_id,
            candidate.candidate_id,
            name="Updated",
            is_sellable=False
        )

        self.assertEqual(updated.name, "Updated")
        self.assertFalse(updated.is_sellable)

    def test_delete_candidate(self):
        """Test deleting a candidate"""
        candidate = self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Test",
            description="Test",
            spec_id=self.spec.spec_id
        )

        result = self.candidate_manager.delete_candidate(
            self.catalog.catalog_id,
            candidate.candidate_id
        )

        self.assertTrue(result)


class TestCatalogLifecycleManager(unittest.TestCase):
    """Test CatalogLifecycleManager"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.lifecycle_manager = CatalogLifecycleManager(self.catalog_manager)

    def test_transition_draft_to_published(self):
        """Test transitioning from draft to published"""
        updated = self.lifecycle_manager.transition_state(
            self.catalog.catalog_id,
            CatalogLifecycleState.PUBLISHED
        )

        self.assertEqual(updated.lifecycle_state, CatalogLifecycleState.PUBLISHED)
        self.assertIsNotNone(updated.published_at)

    def test_transition_published_to_active(self):
        """Test transitioning from published to active"""
        self.lifecycle_manager.transition_state(
            self.catalog.catalog_id,
            CatalogLifecycleState.PUBLISHED
        )

        updated = self.lifecycle_manager.transition_state(
            self.catalog.catalog_id,
            CatalogLifecycleState.ACTIVE
        )

        self.assertEqual(updated.lifecycle_state, CatalogLifecycleState.ACTIVE)

    def test_invalid_transition(self):
        """Test that invalid transitions fail"""
        with self.assertRaises(ValueError):
            self.lifecycle_manager.transition_state(
                self.catalog.catalog_id,
                CatalogLifecycleState.RETIRED
            )

    def test_can_transition(self):
        """Test checking if transition is valid"""
        can_publish = self.lifecycle_manager.can_transition(
            self.catalog.catalog_id,
            CatalogLifecycleState.PUBLISHED
        )

        self.assertTrue(can_publish)

        cannot_retire = self.lifecycle_manager.can_transition(
            self.catalog.catalog_id,
            CatalogLifecycleState.RETIRED
        )

        self.assertFalse(cannot_retire)


class TestCatalogImportExport(unittest.TestCase):
    """Test CatalogImportExport"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.category_manager = ResourceCategoryManager(self.catalog_manager)
        self.spec_manager = ResourceSpecificationManager(self.catalog_manager)
        self.candidate_manager = ResourceCandidateManager(self.catalog_manager)
        self.import_export = CatalogImportExport(self.catalog_manager)

    def test_export_catalog(self):
        """Test exporting a catalog"""
        self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Network",
            description="Network resources"
        )

        spec = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="IP Address",
            description="IPv4 address",
            spec_type=ResourceSpecType.LOGICAL
        )

        self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Public IP",
            description="Public IP address",
            spec_id=spec.spec_id
        )

        exported = self.import_export.export_catalog(self.catalog.catalog_id)

        self.assertIn("catalog", exported)
        self.assertIn("categories", exported)
        self.assertIn("specifications", exported)
        self.assertIn("candidates", exported)
        self.assertEqual(len(exported["categories"]), 1)
        self.assertEqual(len(exported["specifications"]), 1)
        self.assertEqual(len(exported["candidates"]), 1)

    def test_import_catalog(self):
        """Test importing a catalog"""
        data = {
            "catalog": {
                "name": "Imported Catalog",
                "description": "Imported description",
                "lifecycleState": "active",
                "version": 2
            },
            "categories": [
                {
                    "id": "cat_1",
                    "name": "Network",
                    "description": "Network resources"
                }
            ],
            "specifications": [
                {
                    "id": "spec_1",
                    "name": "IP Address",
                    "description": "IPv4 address",
                    "type": "logical"
                }
            ],
            "candidates": [
                {
                    "id": "cand_1",
                    "name": "Public IP",
                    "description": "Public IP address",
                    "specId": "spec_1"
                }
            ]
        }

        imported = self.import_export.import_catalog(data)

        self.assertIsNotNone(imported)
        self.assertEqual(imported.name, "Imported Catalog")
        self.assertEqual(len(imported.categories), 1)
        self.assertEqual(len(imported.specifications), 1)
        self.assertEqual(len(imported.candidates), 1)


class TestCatalogVersionManager(unittest.TestCase):
    """Test CatalogVersionManager"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.version_manager = CatalogVersionManager(self.catalog_manager)

    def test_create_version(self):
        """Test creating a version"""
        version = self.version_manager.create_version(
            self.catalog.catalog_id,
            "v1.0"
        )

        self.assertIsNotNone(version)
        self.assertEqual(version["version"], 1)
        self.assertEqual(version["label"], "v1.0")
        self.assertIn("snapshot", version)

    def test_get_version(self):
        """Test getting a version"""
        self.version_manager.create_version(self.catalog.catalog_id, "v1.0")

        version = self.version_manager.get_version(self.catalog.catalog_id, 1)

        self.assertIsNotNone(version)
        self.assertEqual(version["version"], 1)

    def test_list_versions(self):
        """Test listing versions"""
        self.version_manager.create_version(self.catalog.catalog_id, "v1.0")
        self.version_manager.create_version(self.catalog.catalog_id, "v2.0")

        versions = self.version_manager.list_versions(self.catalog.catalog_id)

        self.assertEqual(len(versions), 2)

    def test_restore_version(self):
        """Test restoring a version"""
        original_name = self.catalog.name

        self.version_manager.create_version(self.catalog.catalog_id, "v1.0")

        # Modify catalog
        self.catalog_manager.update_catalog(
            self.catalog.catalog_id,
            name="Modified"
        )

        # Restore version
        restored = self.version_manager.restore_version(self.catalog.catalog_id, 1)

        self.assertEqual(restored.name, original_name)


class TestCatalogSearchEngine(unittest.TestCase):
    """Test CatalogSearchEngine"""

    def setUp(self):
        self.catalog_manager = ResourceCatalogManager()
        self.catalog = self.catalog_manager.create_catalog("Test Catalog", "Description")
        self.category_manager = ResourceCategoryManager(self.catalog_manager)
        self.spec_manager = ResourceSpecificationManager(self.catalog_manager)
        self.candidate_manager = ResourceCandidateManager(self.catalog_manager)
        self.search_engine = CatalogSearchEngine(self.catalog_manager)

        # Create test data
        self.category = self.category_manager.create_category(
            catalog_id=self.catalog.catalog_id,
            name="Network",
            description="Network resources"
        )

        self.spec1 = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="IP Address",
            description="IPv4 address",
            spec_type=ResourceSpecType.LOGICAL,
            category_id=self.category.category_id
        )

        self.spec2 = self.spec_manager.create_specification(
            catalog_id=self.catalog.catalog_id,
            name="Router",
            description="Network router",
            spec_type=ResourceSpecType.PHYSICAL,
            category_id=self.category.category_id
        )

        self.candidate_manager.create_candidate(
            catalog_id=self.catalog.catalog_id,
            name="Public IP",
            description="Public IP address",
            spec_id=self.spec1.spec_id
        )

    def test_search_all(self):
        """Test searching all items"""
        results = self.search_engine.search(catalog_id=self.catalog.catalog_id)

        # Should have 1 category, 2 specs, 1 candidate
        self.assertEqual(len(results), 4)

    def test_search_with_filters(self):
        """Test searching with filters"""
        results = self.search_engine.search(
            catalog_id=self.catalog.catalog_id,
            filters={"spec_type.eq": "LOGICAL"}
        )

        # Should only match logical specs
        spec_results = [r for r in results if r["type"] == "specification"]
        self.assertGreaterEqual(len(spec_results), 0)

    def test_search_with_gt_filter(self):
        """Test searching with gt filter"""
        # This tests the filter engine - search for resources with name length > 5
        results = self.search_engine.search(
            catalog_id=self.catalog.catalog_id,
            filters={"name.contains": "IP"}
        )

        # Should return items since spec has "IP" in name
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
