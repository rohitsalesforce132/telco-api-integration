"""
TMF620 Product Catalog Management Module
Implements product catalog, offerings, specifications, pricing, and bundling.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict
from copy import deepcopy


class ProductLifecycleState(Enum):
    """Product lifecycle states per TMF620 standard."""
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    OBSOLETE = "obsolete"


class PricingType(Enum):
    """Pricing model types."""
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    USAGE_BASED = "usage_based"


@dataclass
class ProductOfferingPrice:
    """
    Pricing model for a product offering.
    Supports one-time, recurring, and usage-based pricing.
    """
    id: str
    name: str
    price_type: PricingType
    amount: float
    currency: str = "USD"
    description: str = ""
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    tax_included: bool = False
    min_quantity: int = 1
    max_quantity: Optional[int] = None
    unit_of_measure: str = "each"
    usage_unit: Optional[str] = None  # For usage-based: GB, minutes, calls, etc.
    tiered_pricing: List[Dict[str, Any]] = field(default_factory=list)

    def is_valid(self, date: Optional[datetime] = None) -> bool:
        """Check if pricing is valid on a given date."""
        if date is None:
            date = datetime.now()
        if self.valid_from and date < self.valid_from:
            return False
        if self.valid_to and date > self.valid_to:
            return False
        return True

    def calculate_cost(self, quantity: int = 1, usage_amount: Optional[float] = None) -> float:
        """Calculate cost based on quantity or usage."""
        if quantity < self.min_quantity:
            raise ValueError(f"Quantity {quantity} below minimum {self.min_quantity}")
        if self.max_quantity and quantity > self.max_quantity:
            raise ValueError(f"Quantity {quantity} exceeds maximum {self.max_quantity}")

        if self.price_type == PricingType.ONE_TIME:
            return self.amount * quantity

        elif self.price_type == PricingType.RECURRING:
            return self.amount  # Recurring is typically flat rate

        elif self.price_type == PricingType.USAGE_BASED:
            if usage_amount is None:
                raise ValueError("Usage amount required for usage-based pricing")
            if self.tiered_pricing:
                return self._calculate_tiered_cost(usage_amount)
            return self.amount * usage_amount

        return 0.0

    def _calculate_tiered_cost(self, usage_amount: float) -> float:
        """Calculate cost using tiered pricing model."""
        total_cost = 0.0
        remaining_usage = usage_amount

        for tier in sorted(self.tiered_pricing, key=lambda x: x['min_units']):
            if remaining_usage <= 0:
                break

            tier_min = tier['min_units']
            tier_max = tier.get('max_units', float('inf'))
            tier_rate = tier['rate']

            if usage_amount <= tier_min:
                continue

            tier_units = min(remaining_usage, tier_max - tier_min + 1)
            total_cost += tier_units * tier_rate
            remaining_usage -= tier_units

        return total_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['price_type'] = self.price_type.value
        data['valid_from'] = self.valid_from.isoformat() if self.valid_from else None
        data['valid_to'] = self.valid_to.isoformat() if self.valid_to else None
        return data


@dataclass
class ProductSpecification:
    """
    Defines product specifications with characteristics, rules, and constraints.
    """
    id: str
    name: str
    description: str = ""
    version: str = "1.0"
    characteristics: Dict[str, Any] = field(default_factory=dict)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    resource_requirements: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_characteristic(self, name: str, value: Any, data_type: str = "string", required: bool = False) -> None:
        """Add a characteristic to the specification."""
        self.characteristics[name] = {
            "value": value,
            "data_type": data_type,
            "required": required
        }
        self.updated_at = datetime.now()

    def add_constraint(self, constraint_type: str, rule: str, error_message: str) -> None:
        """Add a validation constraint."""
        self.constraints.append({
            "type": constraint_type,
            "rule": rule,
            "error_message": error_message
        })
        self.updated_at = datetime.now()

    def validate(self, product_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate product data against specification constraints."""
        errors = []

        # Check required characteristics
        for name, char in self.characteristics.items():
            if char.get('required') and name not in product_data:
                errors.append(f"Required characteristic '{name}' is missing")

        # Validate constraints
        for constraint in self.constraints:
            if not self._evaluate_constraint(constraint['rule'], product_data):
                errors.append(constraint['error_message'])

        return len(errors) == 0, errors

    def _evaluate_constraint(self, rule: str, data: Dict[str, Any]) -> bool:
        """Evaluate a constraint rule (simplified implementation)."""
        # In production, this would use a proper expression evaluator
        try:
            # Simple rule evaluation: "field >= value" or "field in [a,b,c]"
            if '>=' in rule:
                field, value = rule.split('>=')
                field = field.strip()
                value = float(value.strip())
                return float(data.get(field, 0)) >= value
            elif '<=' in rule:
                field, value = rule.split('<=')
                field = field.strip()
                value = float(value.strip())
                return float(data.get(field, float('inf'))) <= value
            elif 'in' in rule:
                field, values = rule.split('in')
                field = field.strip()
                values = values.strip('[] ').split(',')
                return data.get(field) in [v.strip() for v in values]
        except Exception:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


@dataclass
class ProductCategory:
    """
    Hierarchical categorization for product offerings.
    """
    id: str
    name: str
    description: str = ""
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    is_leaf: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def add_child(self, child_id: str) -> None:
        """Add a child category."""
        if child_id not in self.children:
            self.children.append(child_id)
            self.is_leaf = False

    def remove_child(self, child_id: str) -> None:
        """Remove a child category."""
        if child_id in self.children:
            self.children.remove(child_id)
            self.is_leaf = len(self.children) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class ProductOffering:
    """
    Product offering with pricing, lifecycle, and bundling support.
    """
    id: str
    name: str
    description: str = ""
    specification_id: Optional[str] = None
    category_id: Optional[str] = None
    prices: List[ProductOfferingPrice] = field(default_factory=list)
    lifecycle_state: ProductLifecycleState = ProductLifecycleState.DRAFT
    is_bundle: bool = False
    bundled_offerings: List[str] = field(default_factory=list)
    valid_for: List[Dict[str, str]] = field(default_factory=list)
    channel: List[str] = field(default_factory=list)
    attachment: List[Dict[str, str]] = field(default_factory=list)
    place: List[Dict[str, str]] = field(default_factory=list)
    product_offering_term: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_price(self, price: ProductOfferingPrice) -> None:
        """Add a pricing model to the offering."""
        self.prices.append(price)
        self.updated_at = datetime.now()

    def remove_price(self, price_id: str) -> bool:
        """Remove a pricing model from the offering."""
        for i, price in enumerate(self.prices):
            if price.id == price_id:
                self.prices.pop(i)
                self.updated_at = datetime.now()
                return True
        return False

    def get_active_price(self, price_type: PricingType) -> Optional[ProductOfferingPrice]:
        """Get the active price for a given type."""
        now = datetime.now()
        for price in self.prices:
            if price.price_type == price_type and price.is_valid(now):
                return price
        return None

    def add_bundled_offering(self, offering_id: str) -> None:
        """Add a bundled offering to this bundle."""
        if not self.is_bundle:
            self.is_bundle = True
        if offering_id not in self.bundled_offerings:
            self.bundled_offerings.append(offering_id)
            self.updated_at = datetime.now()

    def remove_bundled_offering(self, offering_id: str) -> bool:
        """Remove a bundled offering from this bundle."""
        if offering_id in self.bundled_offerings:
            self.bundled_offerings.remove(offering_id)
            if not self.bundled_offerings:
                self.is_bundle = False
            self.updated_at = datetime.now()
            return True
        return False

    def change_lifecycle_state(self, new_state: ProductLifecycleState) -> bool:
        """Change the lifecycle state of the offering."""
        valid_transitions = {
            ProductLifecycleState.DRAFT: [ProductLifecycleState.ACTIVE, ProductLifecycleState.RETIRED],
            ProductLifecycleState.ACTIVE: [ProductLifecycleState.RETIRED],
            ProductLifecycleState.RETIRED: [ProductLifecycleState.OBSOLETE],
            ProductLifecycleState.OBSOLETE: []
        }

        if new_state in valid_transitions.get(self.lifecycle_state, []):
            self.lifecycle_state = new_state
            self.updated_at = datetime.now()
            return True
        return False

    def is_available(self) -> bool:
        """Check if the offering is currently available for sale."""
        if self.lifecycle_state != ProductLifecycleState.ACTIVE:
            return False
        now = datetime.now()
        for valid in self.valid_for:
            start = datetime.fromisoformat(valid['startDateTime'])
            end = datetime.fromisoformat(valid['endDateTime']) if 'endDateTime' in valid else None
            if start <= now and (end is None or now <= end):
                return True
        return len(self.valid_for) == 0  # No validity constraints means always available

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['lifecycle_state'] = self.lifecycle_state.value
        data['prices'] = [p.to_dict() for p in self.prices]
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


class BundledOfferingManager:
    """
    Manages product bundles and promotions.
    Handles bundle pricing, discount rules, and bundle availability.
    """

    def __init__(self):
        self.bundles: Dict[str, ProductOffering] = {}
        self.discount_rules: Dict[str, Dict[str, Any]] = {}

    def create_bundle(self, bundle_id: str, name: str, description: str = "") -> ProductOffering:
        """Create a new product bundle."""
        bundle = ProductOffering(
            id=bundle_id,
            name=name,
            description=description,
            is_bundle=True,
            lifecycle_state=ProductLifecycleState.DRAFT
        )
        self.bundles[bundle_id] = bundle
        return bundle

    def add_to_bundle(self, bundle_id: str, offering_id: str) -> bool:
        """Add a product offering to a bundle."""
        if bundle_id not in self.bundles:
            return False
        self.bundles[bundle_id].add_bundled_offering(offering_id)
        return True

    def set_bundle_discount(self, bundle_id: str, discount_type: str,
                          discount_value: float, description: str = "") -> None:
        """Set discount rule for a bundle."""
        self.discount_rules[bundle_id] = {
            "type": discount_type,  # "percentage", "fixed", "buy_x_get_y"
            "value": discount_value,
            "description": description
        }

    def calculate_bundle_price(self, bundle_id: str,
                               individual_prices: Dict[str, float]) -> float:
        """Calculate bundle price with discount applied."""
        if bundle_id not in self.bundles:
            raise ValueError(f"Bundle {bundle_id} not found")

        bundle = self.bundles[bundle_id]
        base_price = sum(individual_prices.get(oid, 0.0) for oid in bundle.bundled_offerings)

        discount = self.discount_rules.get(bundle_id, {})
        if not discount:
            return base_price

        if discount["type"] == "percentage":
            return base_price * (1 - discount["value"] / 100)
        elif discount["type"] == "fixed":
            return max(0.0, base_price - discount["value"])
        elif discount["type"] == "buy_x_get_y":
            # Simplified: buy x, get y% off
            return base_price * (1 - discount["value"] / 100)

        return base_price

    def get_bundle(self, bundle_id: str) -> Optional[ProductOffering]:
        """Get a bundle by ID."""
        return self.bundles.get(bundle_id)

    def list_bundles(self) -> List[ProductOffering]:
        """List all bundles."""
        return list(self.bundles.values())


class ProductEligibilityChecker:
    """
    Checks if a product is eligible for a given customer/context.
    Supports eligibility rules, customer segmentation, and contextual constraints.
    """

    def __init__(self):
        self.eligibility_rules: Dict[str, List[Dict[str, Any]]] = {}

    def add_eligibility_rule(self, offering_id: str, rule_type: str,
                           condition: Dict[str, Any], description: str = "") -> None:
        """Add an eligibility rule for a product offering."""
        if offering_id not in self.eligibility_rules:
            self.eligibility_rules[offering_id] = []
        self.eligibility_rules[offering_id].append({
            "type": rule_type,
            "condition": condition,
            "description": description
        })

    def check_eligibility(self, offering_id: str, customer_context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check if a product is eligible for a customer.
        Returns (is_eligible, reasons).
        """
        if offering_id not in self.eligibility_rules:
            return True, []  # No rules means always eligible

        reasons = []
        is_eligible = True

        for rule in self.eligibility_rules[offering_id]:
            if not self._evaluate_rule(rule['condition'], customer_context):
                is_eligible = False
                reasons.append(rule['description'] or f"Failed {rule['type']} check")

        return is_eligible, reasons

    def _evaluate_rule(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate an eligibility condition."""
        field = condition.get('field')
        operator = condition.get('operator', '==')
        value = condition.get('value')

        if field not in context:
            return False

        context_value = context[field]

        if operator == '==':
            return context_value == value
        elif operator == '!=':
            return context_value != value
        elif operator == '>':
            return context_value > value
        elif operator == '<':
            return context_value < value
        elif operator == '>=':
            return context_value >= value
        elif operator == '<=':
            return context_value <= value
        elif operator == 'in':
            return context_value in value
        elif operator == 'not_in':
            return context_value not in value
        elif operator == 'contains':
            return value in context_value if isinstance(context_value, (list, str)) else False

        return False

    def get_eligible_offerings(self, offering_ids: List[str],
                              customer_context: Dict[str, Any]) -> List[str]:
        """Get list of offerings eligible for a customer."""
        eligible = []
        for offering_id in offering_ids:
            is_eligible, _ = self.check_eligibility(offering_id, customer_context)
            if is_eligible:
                eligible.append(offering_id)
        return eligible


class ProductCatalogManager:
    """
    CRUD manager for product catalogs (TMF620).
    Manages product offerings, specifications, categories, and the catalog itself.
    """

    def __init__(self, catalog_id: str = "default", name: str = "Product Catalog"):
        self.id = catalog_id
        self.name = name
        self.description: str = ""
        self.lifecycle_state: ProductLifecycleState = ProductLifecycleState.DRAFT
        self.offerings: Dict[str, ProductOffering] = {}
        self.specifications: Dict[str, ProductSpecification] = {}
        self.categories: Dict[str, ProductCategory] = {}
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self.version: str = "1.0.0"

        self.bundle_manager = BundledOfferingManager()
        self.eligibility_checker = ProductEligibilityChecker()

    def create_category(self, category_id: str, name: str, description: str = "",
                       parent_id: Optional[str] = None) -> ProductCategory:
        """Create a product category."""
        category = ProductCategory(
            id=category_id,
            name=name,
            description=description,
            parent_id=parent_id
        )
        self.categories[category_id] = category

        # Add to parent if specified
        if parent_id and parent_id in self.categories:
            self.categories[parent_id].add_child(category_id)

        self.updated_at = datetime.now()
        return category

    def get_category(self, category_id: str) -> Optional[ProductCategory]:
        """Get a category by ID."""
        return self.categories.get(category_id)

    def list_categories(self, parent_id: Optional[str] = None) -> List[ProductCategory]:
        """List categories, optionally filtered by parent."""
        if parent_id is None:
            return list(self.categories.values())
        return [cat for cat in self.categories.values() if cat.parent_id == parent_id]

    def delete_category(self, category_id: str) -> bool:
        """Delete a category."""
        if category_id not in self.categories:
            return False

        # Remove from parent
        category = self.categories[category_id]
        if category.parent_id and category.parent_id in self.categories:
            self.categories[category.parent_id].remove_child(category_id)

        # Delete children recursively (simplified - in production, handle properly)
        for child_id in category.children:
            self.delete_category(child_id)

        del self.categories[category_id]
        self.updated_at = datetime.now()
        return True

    def create_specification(self, spec_id: str, name: str, description: str = "",
                            version: str = "1.0") -> ProductSpecification:
        """Create a product specification."""
        spec = ProductSpecification(
            id=spec_id,
            name=name,
            description=description,
            version=version
        )
        self.specifications[spec_id] = spec
        self.updated_at = datetime.now()
        return spec

    def get_specification(self, spec_id: str) -> Optional[ProductSpecification]:
        """Get a specification by ID."""
        return self.specifications.get(spec_id)

    def list_specifications(self) -> List[ProductSpecification]:
        """List all specifications."""
        return list(self.specifications.values())

    def delete_specification(self, spec_id: str) -> bool:
        """Delete a specification."""
        if spec_id not in self.specifications:
            return False

        # Check if used by any offering
        for offering in self.offerings.values():
            if offering.specification_id == spec_id:
                raise ValueError(f"Cannot delete spec {spec_id}: used by offering {offering.id}")

        del self.specifications[spec_id]
        self.updated_at = datetime.now()
        return True

    def create_offering(self, offering_id: str, name: str, description: str = "",
                       specification_id: Optional[str] = None,
                       category_id: Optional[str] = None) -> ProductOffering:
        """Create a product offering."""
        offering = ProductOffering(
            id=offering_id,
            name=name,
            description=description,
            specification_id=specification_id,
            category_id=category_id
        )
        self.offerings[offering_id] = offering
        self.updated_at = datetime.now()
        return offering

    def get_offering(self, offering_id: str) -> Optional[ProductOffering]:
        """Get an offering by ID."""
        return self.offerings.get(offering_id)

    def list_offerings(self, category_id: Optional[str] = None,
                      lifecycle_state: Optional[ProductLifecycleState] = None) -> List[ProductOffering]:
        """List offerings, optionally filtered by category or lifecycle state."""
        offerings = list(self.offerings.values())

        if category_id:
            offerings = [o for o in offerings if o.category_id == category_id]

        if lifecycle_state:
            offerings = [o for o in offerings if o.lifecycle_state == lifecycle_state]

        return offerings

    def list_active_offerings(self) -> List[ProductOffering]:
        """List all active and available offerings."""
        return [o for o in self.offerings.values() if o.is_available()]

    def delete_offering(self, offering_id: str) -> bool:
        """Delete an offering."""
        if offering_id not in self.offerings:
            return False

        # Can only delete draft offerings
        if self.offerings[offering_id].lifecycle_state != ProductLifecycleState.DRAFT:
            raise ValueError(f"Cannot delete offering {offering_id}: not in DRAFT state")

        del self.offerings[offering_id]
        self.updated_at = datetime.now()
        return True

    def search_offerings(self, query: str) -> List[ProductOffering]:
        """Search offerings by name or description."""
        query_lower = query.lower()
        return [
            o for o in self.offerings.values()
            if query_lower in o.name.lower() or query_lower in o.description.lower()
        ]

    def update_catalog(self, name: Optional[str] = None,
                      description: Optional[str] = None) -> None:
        """Update catalog metadata."""
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        self.updated_at = datetime.now()

    def change_catalog_lifecycle(self, new_state: ProductLifecycleState) -> bool:
        """Change the lifecycle state of the catalog."""
        # Simple state machine for catalog
        valid_transitions = {
            ProductLifecycleState.DRAFT: [ProductLifecycleState.ACTIVE, ProductLifecycleState.RETIRED],
            ProductLifecycleState.ACTIVE: [ProductLifecycleState.RETIRED],
            ProductLifecycleState.RETIRED: [ProductLifecycleState.OBSOLETE],
            ProductLifecycleState.OBSOLETE: []
        }

        if new_state in valid_transitions.get(self.lifecycle_state, []):
            self.lifecycle_state = new_state
            self.updated_at = datetime.now()
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert catalog to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "lifecycle_state": self.lifecycle_state.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "categories_count": len(self.categories),
            "specifications_count": len(self.specifications),
            "offerings_count": len(self.offerings)
        }


class CatalogExportManager:
    """
    Exports product catalog data in TMF620 format.
    Supports JSON export with TMF-compliant structure.
    """

    @staticmethod
    def export_catalog(catalog: ProductCatalogManager, format: str = "json") -> str:
        """Export catalog to TMF620 format."""
        export_data = {
            "catalog": catalog.to_dict(),
            "categories": [cat.to_dict() for cat in catalog.categories.values()],
            "specifications": [spec.to_dict() for spec in catalog.specifications.values()],
            "offerings": [off.to_dict() for off in catalog.offerings.values()]
        }

        if format == "json":
            return json.dumps(export_data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def export_offering(offering: ProductOffering, format: str = "json") -> str:
        """Export a single product offering."""
        if format == "json":
            return json.dumps(offering.to_dict(), indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def export_specification(spec: ProductSpecification, format: str = "json") -> str:
        """Export a product specification."""
        if format == "json":
            return json.dumps(spec.to_dict(), indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")
