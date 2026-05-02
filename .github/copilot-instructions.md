# GitHub Copilot Instructions

## Project Overview

This is the **Telco API Integration Platform** - a production-grade Python platform implementing telecom APIs for telecom.

## Architecture

```
src/
├── tmf931/              # TMF931 Resource Catalog (TM Forum)
│   ├── catalog/         # Resource catalog management
│   └── inventory/       # Resource inventory management
├── tmf620/              # TMF620 Product Catalog (TM Forum)
│   └── catalog/         # Product catalog management (offerings, specs, pricing, bundles)
├── tmf622/              # TMF622 Product Ordering (TM Forum)
│   └── ordering/        # Product ordering (lifecycle, fulfillment, compensation)
├── camara/              # CAMARA APIs
│   ├── sim_swap/        # CAMARA SIM Swap Detection
│   └── number_verify/   # CAMARA Number Verification
├── billing/             # OA Billing Integration
│   ├── usage/           # Usage metering
│   └── engine/          # Billing engine
└── shared/              # Cross-cutting concerns
    ├── gateway/         # API Gateway & Security
    └── observability/   # Observability
```

## Coding Standards

### 1. Pure Python stdlib ONLY
- **NO external dependencies** - not even pytest
- Use only: `dataclasses`, `enum`, `time`, `threading`, `collections`, `json`, `random`, `string`, `uuid`, `datetime`, `copy`
- No `pip install` required

### 2. Real Classes Only
- **NO stubs** - all classes must do real work
- **NO `pass` statements** - implement all methods
- All methods must have actual functionality

### 3. Testing Standards
- **Use `unittest.TestCase` ONLY** - no pytest
- Test files: `tests/test_*.py`
- Test methods: `test_*`
- Use `self.assertX()` methods, NOT plain `assert`
- All tests must pass: `python3 -m unittest discover -s tests -p "test_*.py"`
- Target: 300+ tests ALL PASSING

### 4. Documentation
- All classes must have docstrings
- All methods must have docstrings
- Dataclasses must have field descriptions
- Follow PEP 8 style guidelines

## Subsystem Guidelines

### TMF931 Resource Catalog
- Follow TM Forum TMF931 standard
- Implement lifecycle states: draft → published → active → retired
- Support TMF search syntax: `field=value`, `field.gt=value`, `field.in=value`
- Use CatalogLifecycleState enum for states
- Use ResourceSpecType enum (LOGICAL, PHYSICAL, HYBRID)

### TMF620 Product Catalog
- Follow TM Forum TMF620 standard
- Product offerings with pricing models (one-time, recurring, usage-based, tiered)
- Product specifications with characteristics and constraints
- Product bundling with discount support (percentage, fixed, buy-x-get-y)
- Product eligibility checking with rule-based engine
- Product categorization with hierarchical tree structure
- TMF620 export format (JSON)
- Use ProductLifecycleState enum for offering states
- Use PricingType enum for pricing models

### TMF622 Product Ordering
- Follow TM Forum TMF622 standard
- Order lifecycle: acknowledged → in_progress → completed/failed/cancelled/partial
- Quote management with validity periods and state transitions
- Order validation engine for feasibility, pricing, and eligibility
- Fulfillment orchestration with pluggable handlers for TMF931 and CAMARA integration
- Compensation/rollback for failed or cancelled orders
- Notification manager with webhook support
- Use OrderState enum for order states
- Use OrderItemState enum for item states
- Use QuoteState enum for quote states

### CAMARA APIs
- Follow CAMARA Open API specifications
- SIM Swap: Implement consent management, swap history, risk assessment
- Number Verification: Implement E.164 validation, OTP flows, fraud scoring
- Use ConsentStatus enum for consent states
- Use VerificationStatus enum for verification states

### Billing
- Usage Metering: Support PER_CALL, TIERED, VOLUME_BASED pricing
- Billing Engine: Dual-entry ledger for financial accuracy
- Support multiple billing cycles: MONTHLY, QUARTERLY, ANNUALLY
- Use MeteringMode enum for pricing models
- Use InvoiceStatus and PaymentStatus enums

### API Gateway
- Implement OAuth2 token issuance, validation, refresh, revocation
- Implement API key management with scopes
- Use token bucket algorithm for rate limiting
- Map internal errors to TMF645/CAMARA error codes
- Use ErrorType enum for error types

### Observability
- Implement metrics: counters, gauges, histograms
- Health checks with overall status calculation
- Audit logging with time-based queries
- Distributed tracing with span management
- Threshold-based alerting
- Use HealthStatus and AlertSeverity enums

## Key Patterns

### Dataclass Usage
```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Resource:
    resource_id: str
    name: str
    state: ResourceState = ResourceState.PLANNED
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
```

### Enum Usage
```python
from enum import Enum

class ResourceState(Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    TERMINATED = "terminated"
```

### ID Generation
```python
def _generate_id(self, prefix: str) -> str:
    self._counter += 1
    return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"
```

### Error Handling
```python
def get_resource(self, resource_id: str) -> Optional[Resource]:
    resource = self._resources.get(resource_id)
    if not resource:
        return None
    return resource

def _get_resource_or_raise(self, resource_id: str) -> Resource:
    resource = self.get_resource(resource_id)
    if not resource:
        raise ValueError(f"Resource not found: {resource_id}")
    return resource
```

## Testing Guidelines

### Test Structure
```python
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tmf931.catalog import ResourceCatalogManager

class TestResourceCatalogManager(unittest.TestCase):
    def setUp(self):
        self.manager = ResourceCatalogManager()

    def test_create_catalog(self):
        catalog = self.manager.create_catalog("Test", "Description")
        self.assertIsNotNone(catalog)
        self.assertEqual(catalog.name, "Test")

if __name__ == "__main__":
    unittest.main()
```

### Use unittest assertions, not plain assert
```python
# ✅ CORRECT
self.assertEqual(value, expected)
self.assertTrue(condition)
self.assertIsNotNone(obj)
self.assertRaises(ValueError, func)

# ❌ WRONG
assert value == expected
assert condition
assert obj is not None
```

## Running Tests

```bash
# Run all tests
python3 -m unittest discover -s tests -p "test_*.py"

# Run specific test file
python3 -m unittest tests.test_tmf931_catalog

# Run with verbose output
python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Dependencies

**NONE** - This project uses pure Python stdlib only.

## Goals

- Build production-grade telecom API integration platform
- Implement TMF931, TMF620, TMF622, CAMARA, and OA Billing standards
- Achieve 300+ tests ALL PASSING
- Zero external dependencies
- Real, working classes with no stubs
- 5-tier architecture: Resource Layer → Product Layer → Network APIs → Billing → Cross-Cutting

## Priority

1. **Functionality first** - All methods must do real work
2. **Test coverage** - All tests must pass
3. **Standards compliance** - Follow TMF/CAMARA specifications
4. **Code quality** - Clean, documented, maintainable code
