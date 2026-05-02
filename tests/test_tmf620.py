"""
Unit tests for TMF620 Product Catalog Management.
Tests all components: ProductCatalogManager, ProductOffering, ProductSpecification,
ProductOfferingPrice, ProductCategory, BundledOfferingManager, ProductEligibilityChecker,
and CatalogExportManager.
"""

import unittest
from datetime import datetime, timedelta
import json

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tmf620.catalog import (
    ProductCatalogManager, ProductOffering, ProductSpecification,
    ProductOfferingPrice, ProductCategory, BundledOfferingManager,
    ProductEligibilityChecker, CatalogExportManager,
    ProductLifecycleState, PricingType
)


class TestProductOfferingPrice(unittest.TestCase):
    """Test ProductOfferingPrice functionality."""

    def test_create_one_time_price(self):
        """Test creating a one-time pricing model."""
        price = ProductOfferingPrice(
            id="price1",
            name="One-time purchase",
            price_type=PricingType.ONE_TIME,
            amount=99.99,
            currency="USD"
        )
        self.assertEqual(price.price_type, PricingType.ONE_TIME)
        self.assertEqual(price.amount, 99.99)
        self.assertTrue(price.is_valid())

    def test_create_recurring_price(self):
        """Test creating a recurring pricing model."""
        price = ProductOfferingPrice(
            id="price2",
            name="Monthly subscription",
            price_type=PricingType.RECURRING,
            amount=19.99,
            currency="USD"
        )
        self.assertEqual(price.price_type, PricingType.RECURRING)

    def test_create_usage_based_price(self):
        """Test creating a usage-based pricing model."""
        price = ProductOfferingPrice(
            id="price3",
            name="Data usage",
            price_type=PricingType.USAGE_BASED,
            amount=0.01,
            currency="USD",
            usage_unit="GB"
        )
        self.assertEqual(price.price_type, PricingType.USAGE_BASED)
        self.assertEqual(price.usage_unit, "GB")

    def test_price_validity_dates(self):
        """Test price validity with date ranges."""
        price = ProductOfferingPrice(
            id="price4",
            name="Promo price",
            price_type=PricingType.ONE_TIME,
            amount=49.99,
            valid_from=datetime.now() - timedelta(days=1),
            valid_to=datetime.now() + timedelta(days=7)
        )
        self.assertTrue(price.is_valid())

        # Test past validity
        future_date = datetime.now() + timedelta(days=30)
        self.assertFalse(price.is_valid(future_date))

    def test_calculate_one_time_cost(self):
        """Test cost calculation for one-time pricing."""
        price = ProductOfferingPrice(
            id="price5",
            name="One-time",
            price_type=PricingType.ONE_TIME,
            amount=10.0
        )
        self.assertEqual(price.calculate_cost(5), 50.0)

    def test_calculate_usage_based_cost(self):
        """Test cost calculation for usage-based pricing."""
        price = ProductOfferingPrice(
            id="price6",
            name="Data usage",
            price_type=PricingType.USAGE_BASED,
            amount=0.01,
            usage_unit="GB"
        )
        self.assertEqual(price.calculate_cost(usage_amount=1000), 10.0)

    def test_tiered_pricing(self):
        """Test tiered pricing calculation."""
        price = ProductOfferingPrice(
            id="price7",
            name="Tiered data",
            price_type=PricingType.USAGE_BASED,
            amount=0.01,
            tiered_pricing=[
                {"min_units": 0, "max_units": 100, "rate": 0.01},
                {"min_units": 101, "max_units": 500, "rate": 0.005},
                {"min_units": 501, "rate": 0.002}
            ]
        )
        # 150 GB: 100 * 0.01 + 50 * 0.005 = 1.0 + 0.25 = 1.25
        cost = price.calculate_cost(usage_amount=150)
        self.assertAlmostEqual(cost, 1.25, places=2)

    def test_price_to_dict(self):
        """Test price serialization to dictionary."""
        price = ProductOfferingPrice(
            id="price8",
            name="Test price",
            price_type=PricingType.ONE_TIME,
            amount=25.0
        )
        data = price.to_dict()
        self.assertEqual(data['id'], "price8")
        self.assertEqual(data['price_type'], "one_time")
        self.assertEqual(data['amount'], 25.0)


class TestProductSpecification(unittest.TestCase):
    """Test ProductSpecification functionality."""

    def test_create_specification(self):
        """Test creating a product specification."""
        spec = ProductSpecification(
            id="spec1",
            name="Mobile Plan",
            description="Standard mobile plan specification"
        )
        self.assertEqual(spec.id, "spec1")
        self.assertEqual(spec.name, "Mobile Plan")
        self.assertEqual(spec.version, "1.0")

    def test_add_characteristic(self):
        """Test adding characteristics to specification."""
        spec = ProductSpecification(id="spec2", name="Test Spec")
        spec.add_characteristic("data_limit", 10, "integer")
        self.assertIn("data_limit", spec.characteristics)
        self.assertEqual(spec.characteristics["data_limit"]["value"], 10)

    def test_add_constraint(self):
        """Test adding constraints to specification."""
        spec = ProductSpecification(id="spec3", name="Test Spec")
        spec.add_constraint("min_value", "data_limit >= 1", "Data limit must be at least 1 GB")
        self.assertEqual(len(spec.constraints), 1)

    def test_validate_success(self):
        """Test successful validation."""
        spec = ProductSpecification(id="spec4", name="Test Spec")
        spec.add_characteristic("data_limit", 10, "integer", required=True)
        is_valid, errors = spec.validate({"data_limit": 10})
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_failure_missing_required(self):
        """Test validation failure for missing required field."""
        spec = ProductSpecification(id="spec5", name="Test Spec")
        spec.add_characteristic("data_limit", 10, "integer", required=True)
        is_valid, errors = spec.validate({})
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_constraint_failure(self):
        """Test validation failure for constraint violation."""
        spec = ProductSpecification(id="spec6", name="Test Spec")
        spec.add_constraint("min_value", "data_limit >= 1", "Too small")
        is_valid, errors = spec.validate({"data_limit": 0})
        self.assertFalse(is_valid)
        self.assertIn("Too small", errors[0])

    def test_specification_to_dict(self):
        """Test specification serialization."""
        spec = ProductSpecification(id="spec7", name="Test")
        data = spec.to_dict()
        self.assertEqual(data['id'], "spec7")
        self.assertEqual(data['name'], "Test")


class TestProductCategory(unittest.TestCase):
    """Test ProductCategory functionality."""

    def test_create_category(self):
        """Test creating a product category."""
        category = ProductCategory(
            id="cat1",
            name="Mobile Services",
            description="Mobile-related products"
        )
        self.assertEqual(category.id, "cat1")
        self.assertTrue(category.is_leaf)

    def test_create_category_with_parent(self):
        """Test creating a category with parent."""
        category = ProductCategory(
            id="cat2",
            name="Data Plans",
            parent_id="cat1"
        )
        self.assertEqual(category.parent_id, "cat1")

    def test_add_child(self):
        """Test adding child categories."""
        parent = ProductCategory(id="cat3", name="Parent")
        parent.add_child("cat4")
        self.assertIn("cat4", parent.children)
        self.assertFalse(parent.is_leaf)

    def test_remove_child(self):
        """Test removing child categories."""
        parent = ProductCategory(id="cat5", name="Parent")
        parent.add_child("cat6")
        parent.remove_child("cat6")
        self.assertNotIn("cat6", parent.children)
        self.assertTrue(parent.is_leaf)

    def test_category_to_dict(self):
        """Test category serialization."""
        category = ProductCategory(id="cat7", name="Test")
        data = category.to_dict()
        self.assertEqual(data['id'], "cat7")
        self.assertEqual(data['name'], "Test")


class TestProductOffering(unittest.TestCase):
    """Test ProductOffering functionality."""

    def test_create_offering(self):
        """Test creating a product offering."""
        offering = ProductOffering(
            id="off1",
            name="Basic Mobile Plan",
            description="Entry-level mobile plan"
        )
        self.assertEqual(offering.id, "off1")
        self.assertEqual(offering.lifecycle_state, ProductLifecycleState.DRAFT)

    def test_add_price(self):
        """Test adding pricing to offering."""
        offering = ProductOffering(id="off2", name="Test")
        price = ProductOfferingPrice(
            id="price1",
            name="Monthly",
            price_type=PricingType.RECURRING,
            amount=29.99
        )
        offering.add_price(price)
        self.assertEqual(len(offering.prices), 1)

    def test_remove_price(self):
        """Test removing pricing from offering."""
        offering = ProductOffering(id="off3", name="Test")
        price = ProductOfferingPrice(
            id="price1",
            name="Monthly",
            price_type=PricingType.RECURRING,
            amount=29.99
        )
        offering.add_price(price)
        self.assertTrue(offering.remove_price("price1"))
        self.assertEqual(len(offering.prices), 0)

    def test_get_active_price(self):
        """Test getting active price by type."""
        offering = ProductOffering(id="off4", name="Test")
        price = ProductOfferingPrice(
            id="price1",
            name="Monthly",
            price_type=PricingType.RECURRING,
            amount=29.99
        )
        offering.add_price(price)
        active = offering.get_active_price(PricingType.RECURRING)
        self.assertIsNotNone(active)
        self.assertEqual(active.amount, 29.99)

    def test_lifecycle_state_transitions(self):
        """Test lifecycle state transitions."""
        offering = ProductOffering(id="off5", name="Test")
        self.assertEqual(offering.lifecycle_state, ProductLifecycleState.DRAFT)

        # Valid transition: DRAFT -> ACTIVE
        self.assertTrue(offering.change_lifecycle_state(ProductLifecycleState.ACTIVE))
        self.assertEqual(offering.lifecycle_state, ProductLifecycleState.ACTIVE)

        # Invalid transition: ACTIVE -> DRAFT
        self.assertFalse(offering.change_lifecycle_state(ProductLifecycleState.DRAFT))

        # Valid transition: ACTIVE -> RETIRED
        self.assertTrue(offering.change_lifecycle_state(ProductLifecycleState.RETIRED))

    def test_bundle_operations(self):
        """Test bundle operations."""
        offering = ProductOffering(id="off6", name="Bundle")
        offering.add_bundled_offering("off1")
        offering.add_bundled_offering("off2")
        self.assertTrue(offering.is_bundle)
        self.assertEqual(len(offering.bundled_offerings), 2)

        offering.remove_bundled_offering("off1")
        self.assertEqual(len(offering.bundled_offerings), 1)

    def test_is_available(self):
        """Test availability check."""
        offering = ProductOffering(id="off7", name="Test")
        offering.change_lifecycle_state(ProductLifecycleState.ACTIVE)
        self.assertTrue(offering.is_available())

        # Can't go back to DRAFT from ACTIVE, go to RETIRED instead
        offering.change_lifecycle_state(ProductLifecycleState.RETIRED)
        self.assertFalse(offering.is_available())


class TestBundledOfferingManager(unittest.TestCase):
    """Test BundledOfferingManager functionality."""

    def test_create_bundle(self):
        """Test creating a product bundle."""
        manager = BundledOfferingManager()
        bundle = manager.create_bundle("bundle1", "Family Plan", "Bundle for families")
        self.assertEqual(bundle.id, "bundle1")
        self.assertTrue(bundle.is_bundle)
        self.assertIn("bundle1", manager.bundles)

    def test_add_to_bundle(self):
        """Test adding offerings to bundle."""
        manager = BundledOfferingManager()
        manager.create_bundle("bundle1", "Test Bundle")
        self.assertTrue(manager.add_to_bundle("bundle1", "off1"))
        self.assertTrue(manager.add_to_bundle("bundle1", "off2"))

        bundle = manager.get_bundle("bundle1")
        self.assertEqual(len(bundle.bundled_offerings), 2)

    def test_set_bundle_discount(self):
        """Test setting bundle discount."""
        manager = BundledOfferingManager()
        manager.create_bundle("bundle1", "Test Bundle")
        manager.set_bundle_discount("bundle1", "percentage", 10, "10% off")

        self.assertIn("bundle1", manager.discount_rules)
        self.assertEqual(manager.discount_rules["bundle1"]["value"], 10)

    def test_calculate_bundle_price_no_discount(self):
        """Test bundle price calculation without discount."""
        manager = BundledOfferingManager()
        manager.create_bundle("bundle1", "Test Bundle")
        manager.add_to_bundle("bundle1", "off1")
        manager.add_to_bundle("bundle1", "off2")

        individual_prices = {"off1": 30.0, "off2": 20.0}
        total = manager.calculate_bundle_price("bundle1", individual_prices)
        self.assertEqual(total, 50.0)

    def test_calculate_bundle_price_with_percentage_discount(self):
        """Test bundle price calculation with percentage discount."""
        manager = BundledOfferingManager()
        manager.create_bundle("bundle1", "Test Bundle")
        manager.add_to_bundle("bundle1", "off1")
        manager.add_to_bundle("bundle1", "off2")
        manager.set_bundle_discount("bundle1", "percentage", 20)

        individual_prices = {"off1": 30.0, "off2": 20.0}
        total = manager.calculate_bundle_price("bundle1", individual_prices)
        self.assertEqual(total, 40.0)  # 50 * 0.8

    def test_calculate_bundle_price_with_fixed_discount(self):
        """Test bundle price calculation with fixed discount."""
        manager = BundledOfferingManager()
        manager.create_bundle("bundle1", "Test Bundle")
        manager.add_to_bundle("bundle1", "off1")
        manager.add_to_bundle("bundle1", "off2")
        manager.set_bundle_discount("bundle1", "fixed", 5.0)

        individual_prices = {"off1": 30.0, "off2": 20.0}
        total = manager.calculate_bundle_price("bundle1", individual_prices)
        self.assertEqual(total, 45.0)  # 50 - 5

    def test_list_bundles(self):
        """Test listing all bundles."""
        manager = BundledOfferingManager()
        manager.create_bundle("bundle1", "Bundle 1")
        manager.create_bundle("bundle2", "Bundle 2")

        bundles = manager.list_bundles()
        self.assertEqual(len(bundles), 2)


class TestProductEligibilityChecker(unittest.TestCase):
    """Test ProductEligibilityChecker functionality."""

    def test_add_eligibility_rule(self):
        """Test adding eligibility rules."""
        checker = ProductEligibilityChecker()
        checker.add_eligibility_rule(
            "off1",
            "age_check",
            {"field": "age", "operator": ">=", "value": 18},
            "Must be 18 or older"
        )
        self.assertIn("off1", checker.eligibility_rules)
        self.assertEqual(len(checker.eligibility_rules["off1"]), 1)

    def test_check_eligibility_pass(self):
        """Test eligibility check that passes."""
        checker = ProductEligibilityChecker()
        checker.add_eligibility_rule(
            "off1",
            "age_check",
            {"field": "age", "operator": ">=", "value": 18}
        )

        is_eligible, reasons = checker.check_eligibility("off1", {"age": 25})
        self.assertTrue(is_eligible)
        self.assertEqual(len(reasons), 0)

    def test_check_eligibility_fail(self):
        """Test eligibility check that fails."""
        checker = ProductEligibilityChecker()
        checker.add_eligibility_rule(
            "off1",
            "age_check",
            {"field": "age", "operator": ">=", "value": 18},
            "Must be 18+"
        )

        is_eligible, reasons = checker.check_eligibility("off1", {"age": 16})
        self.assertFalse(is_eligible)
        self.assertIn("Must be 18+", reasons[0])

    def test_check_eligibility_no_rules(self):
        """Test eligibility check with no rules."""
        checker = ProductEligibilityChecker()
        is_eligible, reasons = checker.check_eligibility("off1", {})
        self.assertTrue(is_eligible)
        self.assertEqual(len(reasons), 0)

    def test_multiple_rules(self):
        """Test with multiple eligibility rules."""
        checker = ProductEligibilityChecker()
        checker.add_eligibility_rule(
            "off1",
            "age_check",
            {"field": "age", "operator": ">=", "value": 18}
        )
        checker.add_eligibility_rule(
            "off1",
            "region_check",
            {"field": "region", "operator": "in", "value": ["US", "CA"]},
            "Must be in US or CA"
        )

        # Should pass both
        is_eligible, reasons = checker.check_eligibility("off1", {"age": 25, "region": "US"})
        self.assertTrue(is_eligible)

        # Should fail one
        is_eligible, reasons = checker.check_eligibility("off1", {"age": 25, "region": "UK"})
        self.assertFalse(is_eligible)
        self.assertIn("Must be in US or CA", reasons[0])

    def test_get_eligible_offerings(self):
        """Test getting eligible offerings for a customer."""
        checker = ProductEligibilityChecker()
        checker.add_eligibility_rule(
            "off1",
            "age_check",
            {"field": "age", "operator": ">=", "value": 18}
        )

        eligible = checker.get_eligible_offerings(
            ["off1", "off2"],
            {"age": 20}
        )
        self.assertIn("off1", eligible)
        self.assertIn("off2", eligible)  # No rules = always eligible

        eligible = checker.get_eligible_offerings(
            ["off1"],
            {"age": 16}
        )
        self.assertNotIn("off1", eligible)


class TestProductCatalogManager(unittest.TestCase):
    """Test ProductCatalogManager functionality."""

    def setUp(self):
        """Set up test catalog."""
        self.catalog = ProductCatalogManager(
            catalog_id="catalog1",
            name="Main Product Catalog"
        )

    def test_catalog_creation(self):
        """Test catalog creation."""
        self.assertEqual(self.catalog.id, "catalog1")
        self.assertEqual(self.catalog.name, "Main Product Catalog")
        self.assertEqual(self.catalog.lifecycle_state, ProductLifecycleState.DRAFT)

    def test_create_category(self):
        """Test creating categories."""
        cat1 = self.catalog.create_category("cat1", "Mobile", "Mobile services")
        self.assertEqual(cat1.id, "cat1")
        self.assertIn("cat1", self.catalog.categories)

        # Create child category
        cat2 = self.catalog.create_category("cat2", "Data Plans", parent_id="cat1")
        self.assertEqual(cat2.parent_id, "cat1")
        self.assertIn("cat2", self.catalog.categories["cat1"].children)

    def test_get_category(self):
        """Test getting a category."""
        self.catalog.create_category("cat1", "Test")
        cat = self.catalog.get_category("cat1")
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, "Test")

    def test_list_categories(self):
        """Test listing categories."""
        self.catalog.create_category("cat1", "Cat1", parent_id="parent")
        self.catalog.create_category("cat2", "Cat2", parent_id="parent")

        all_cats = self.catalog.list_categories()
        self.assertEqual(len(all_cats), 2)

        child_cats = self.catalog.list_categories(parent_id="parent")
        self.assertEqual(len(child_cats), 2)

    def test_delete_category(self):
        """Test deleting categories."""
        self.catalog.create_category("cat1", "Test")
        self.assertTrue(self.catalog.delete_category("cat1"))
        self.assertNotIn("cat1", self.catalog.categories)

    def test_create_specification(self):
        """Test creating specifications."""
        spec = self.catalog.create_specification("spec1", "Mobile Plan Spec")
        self.assertEqual(spec.id, "spec1")
        self.assertIn("spec1", self.catalog.specifications)

    def test_get_specification(self):
        """Test getting a specification."""
        self.catalog.create_specification("spec1", "Test")
        spec = self.catalog.get_specification("spec1")
        self.assertIsNotNone(spec)

    def test_delete_specification_in_use(self):
        """Test deleting a specification that's in use."""
        self.catalog.create_specification("spec1", "Test")
        offering = self.catalog.create_offering("off1", "Test", specification_id="spec1")

        with self.assertRaises(ValueError):
            self.catalog.delete_specification("spec1")

    def test_create_offering(self):
        """Test creating offerings."""
        offering = self.catalog.create_offering(
            "off1",
            "Basic Plan",
            description="Basic mobile plan",
            specification_id="spec1",
            category_id="cat1"
        )
        self.assertEqual(offering.id, "off1")
        self.assertIn("off1", self.catalog.offerings)

    def test_list_offerings(self):
        """Test listing offerings with filters."""
        self.catalog.create_offering("off1", "Plan A", category_id="cat1")
        self.catalog.create_offering("off2", "Plan B", category_id="cat2")
        off3 = self.catalog.create_offering("off3", "Plan C", category_id="cat1")
        off3.change_lifecycle_state(ProductLifecycleState.ACTIVE)

        # Filter by category
        cat1_offerings = self.catalog.list_offerings(category_id="cat1")
        self.assertEqual(len(cat1_offerings), 2)

        # Filter by lifecycle state
        active_offerings = self.catalog.list_offerings(lifecycle_state=ProductLifecycleState.ACTIVE)
        self.assertEqual(len(active_offerings), 1)

    def test_list_active_offerings(self):
        """Test listing only active and available offerings."""
        off1 = self.catalog.create_offering("off1", "Plan A")
        off2 = self.catalog.create_offering("off2", "Plan B")

        off1.change_lifecycle_state(ProductLifecycleState.ACTIVE)

        active = self.catalog.list_active_offerings()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, "off1")

    def test_delete_offering_draft(self):
        """Test deleting a draft offering."""
        self.catalog.create_offering("off1", "Test")
        self.assertTrue(self.catalog.delete_offering("off1"))
        self.assertNotIn("off1", self.catalog.offerings)

    def test_delete_offering_not_draft(self):
        """Test deleting a non-draft offering (should fail)."""
        offering = self.catalog.create_offering("off1", "Test")
        offering.change_lifecycle_state(ProductLifecycleState.ACTIVE)

        with self.assertRaises(ValueError):
            self.catalog.delete_offering("off1")

    def test_search_offerings(self):
        """Test searching offerings."""
        self.catalog.create_offering("off1", "Mobile Plan 5G")
        self.catalog.create_offering("off2", "Data Plan")
        self.catalog.create_offering("off3", "Mobile Plan 4G")

        results = self.catalog.search_offerings("Mobile")
        self.assertEqual(len(results), 2)

        results = self.catalog.search_offerings("5G")
        self.assertEqual(len(results), 1)

    def test_update_catalog(self):
        """Test updating catalog metadata."""
        self.catalog.update_catalog(
            name="Updated Catalog",
            description="New description"
        )
        self.assertEqual(self.catalog.name, "Updated Catalog")
        self.assertEqual(self.catalog.description, "New description")

    def test_change_catalog_lifecycle(self):
        """Test changing catalog lifecycle state."""
        self.catalog.change_catalog_lifecycle(ProductLifecycleState.ACTIVE)
        self.assertEqual(self.catalog.lifecycle_state, ProductLifecycleState.ACTIVE)

        # Invalid transition
        self.assertFalse(self.catalog.change_catalog_lifecycle(ProductLifecycleState.DRAFT))

    def test_catalog_to_dict(self):
        """Test catalog serialization."""
        self.catalog.create_category("cat1", "Test")
        self.catalog.create_specification("spec1", "Test")
        self.catalog.create_offering("off1", "Test")

        data = self.catalog.to_dict()
        self.assertEqual(data['id'], "catalog1")
        self.assertEqual(data['categories_count'], 1)
        self.assertEqual(data['specifications_count'], 1)
        self.assertEqual(data['offerings_count'], 1)

    def test_bundle_manager_integration(self):
        """Test that bundle manager is accessible."""
        self.assertIsNotNone(self.catalog.bundle_manager)
        self.assertIsInstance(self.catalog.bundle_manager, BundledOfferingManager)

    def test_eligibility_checker_integration(self):
        """Test that eligibility checker is accessible."""
        self.assertIsNotNone(self.catalog.eligibility_checker)
        self.assertIsInstance(self.catalog.eligibility_checker, ProductEligibilityChecker)


class TestCatalogExportManager(unittest.TestCase):
    """Test CatalogExportManager functionality."""

    def setUp(self):
        """Set up test catalog for export."""
        self.catalog = ProductCatalogManager(catalog_id="test_catalog", name="Test Catalog")
        self.catalog.create_category("cat1", "Test Category")
        self.catalog.create_specification("spec1", "Test Specification")
        self.catalog.create_offering("off1", "Test Offering")

    def test_export_catalog_json(self):
        """Test exporting catalog to JSON."""
        json_str = CatalogExportManager.export_catalog(self.catalog, "json")
        self.assertIsInstance(json_str, str)

        # Verify it's valid JSON
        data = json.loads(json_str)
        self.assertIn("catalog", data)
        self.assertIn("categories", data)
        self.assertIn("specifications", data)
        self.assertIn("offerings", data)

    def test_export_offering_json(self):
        """Test exporting a single offering to JSON."""
        offering = self.catalog.create_offering("off2", "Export Test")
        json_str = CatalogExportManager.export_offering(offering, "json")
        self.assertIsInstance(json_str, str)

        data = json.loads(json_str)
        self.assertEqual(data['id'], "off2")
        self.assertEqual(data['name'], "Export Test")

    def test_export_specification_json(self):
        """Test exporting a specification to JSON."""
        spec = self.catalog.get_specification("spec1")
        json_str = CatalogExportManager.export_specification(spec, "json")
        self.assertIsInstance(json_str, str)

        data = json.loads(json_str)
        self.assertEqual(data['id'], "spec1")

    def test_export_unsupported_format(self):
        """Test exporting to unsupported format."""
        with self.assertRaises(ValueError):
            CatalogExportManager.export_catalog(self.catalog, "xml")


class TestTMF620Integration(unittest.TestCase):
    """Integration tests for TMF620 components."""

    def test_full_catalog_workflow(self):
        """Test complete catalog workflow from creation to export."""
        # Create catalog
        catalog = ProductCatalogManager(name="Telco Catalog")

        # Create category hierarchy
        mobile = catalog.create_category("mobile", "Mobile Services")
        data = catalog.create_category("data", "Data Plans", parent_id="mobile")

        # Create specification
        spec = catalog.create_specification(
            "mobile_spec",
            "Mobile Plan Specification",
            description="Standard mobile plan specs"
        )
        spec.add_characteristic("data_limit", 10, "integer")
        spec.add_constraint("min_data", "data_limit >= 1", "Minimum 1 GB")

        # Create offering with pricing
        offering = catalog.create_offering(
            "basic_plan",
            "Basic Mobile Plan",
            description="Entry-level mobile plan",
            specification_id="mobile_spec",
            category_id="mobile"
        )

        # Add pricing
        monthly_price = ProductOfferingPrice(
            id="monthly_price",
            name="Monthly fee",
            price_type=PricingType.RECURRING,
            amount=29.99
        )
        offering.add_price(monthly_price)

        # Activate
        offering.change_lifecycle_state(ProductLifecycleState.ACTIVE)
        catalog.change_catalog_lifecycle(ProductLifecycleState.ACTIVE)

        # Verify
        self.assertEqual(len(catalog.list_categories()), 2)
        self.assertEqual(len(catalog.list_offerings()), 1)
        self.assertTrue(offering.is_available())

        # Export
        json_export = CatalogExportManager.export_catalog(catalog)
        self.assertIsInstance(json_export, str)
        data = json.loads(json_export)
        self.assertEqual(data['catalog']['lifecycle_state'], 'active')

    def test_bundle_workflow(self):
        """Test creating and pricing a bundle."""
        catalog = ProductCatalogManager(name="Bundle Catalog")

        # Create individual offerings
        voice = catalog.create_offering("voice", "Voice Plan")
        voice.add_price(ProductOfferingPrice(
            id="voice_price",
            name="Voice",
            price_type=PricingType.RECURRING,
            amount=20.0
        ))

        data = catalog.create_offering("data", "Data Plan")
        data.add_price(ProductOfferingPrice(
            id="data_price",
            name="Data",
            price_type=PricingType.RECURRING,
            amount=30.0
        ))

        # Create bundle
        bundle = catalog.bundle_manager.create_bundle(
            "bundle_voice_data",
            "Voice + Data Bundle"
        )
        catalog.bundle_manager.add_to_bundle("bundle_voice_data", "voice")
        catalog.bundle_manager.add_to_bundle("bundle_voice_data", "data")
        catalog.bundle_manager.set_bundle_discount("bundle_voice_data", "percentage", 15)

        # Calculate bundle price
        individual_prices = {"voice": 20.0, "data": 30.0}
        bundle_price = catalog.bundle_manager.calculate_bundle_price(
            "bundle_voice_data",
            individual_prices
        )

        self.assertEqual(bundle_price, 42.5)  # 50 * 0.85

    def test_eligibility_workflow(self):
        """Test eligibility checking workflow."""
        catalog = ProductCatalogManager(name="Eligibility Catalog")

        # Add eligibility rule
        catalog.eligibility_checker.add_eligibility_rule(
            "premium_plan",
            "age_check",
            {"field": "age", "operator": ">=", "value": 21},
            "Must be 21+ for premium plan"
        )

        # Test eligibility
        is_eligible, reasons = catalog.eligibility_checker.check_eligibility(
            "premium_plan",
            {"age": 25}
        )
        self.assertTrue(is_eligible)

        is_eligible, reasons = catalog.eligibility_checker.check_eligibility(
            "premium_plan",
            {"age": 18}
        )
        self.assertFalse(is_eligible)


if __name__ == '__main__':
    unittest.main()
