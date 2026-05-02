# Telco API Integration Platform

A production-grade Python platform implementing 4 real telecom APIs that an Azure DevOps Engineer would work with.

## Features

### TIER 1: TMF Resource Layer (TMF931)
- **Resource Catalog Manager**: Full CRUD for TMF931 resource catalogs, categories, and catalog items
- **Resource Specification**: Manages resource specifications (logical, physical, hybrid)
- **Resource Candidate**: Manages resource candidates (what can be sold/provisioned)
- **Resource Category**: Categorizes resources in a tree structure
- **Catalog Lifecycle Manager**: Manages catalog lifecycle states (draft, active, retired)
- **Catalog Import/Export**: Import/export catalog data in TMF format
- **Catalog Version Manager**: Version management for catalog changes
- **Catalog Search Engine**: Search across catalogs with TMF filtering

### TIER 2: TMF Product Layer (TMF620 + TMF622)
- **Product Catalog (TMF620)**:
  - ProductCatalogManager: CRUD for product catalogs, offerings, and specifications
  - ProductOffering: Product offerings with pricing, lifecycle, and bundling
  - ProductSpecification: Defines product specs (characteristics, rules, constraints)
  - ProductOfferingPrice: Pricing models (one-time, recurring, usage-based, tiered)
  - ProductCategory: Hierarchical categorization for product offerings
  - BundledOfferingManager: Manages product bundles and promotions with discounts
  - ProductEligibilityChecker: Checks product eligibility for customers/contexts
  - CatalogExportManager: Exports in TMF620 format
- **Product Ordering (TMF622)**:
  - ProductOrderManager: Creates and manages product orders
  - OrderItem: Individual items within an order
  - OrderLifecycleManager: Manages order states (acknowledged, in_progress, completed, failed, cancelled, partial)
  - OrderValidationEngine: Validates order feasibility, pricing, and eligibility
  - OrderFulfillmentEngine: Orchestrates fulfillment across TMF931 resources + CAMARA services
  - OrderCompensationHandler: Rollback/compensation for failed or cancelled orders
  - OrderNotificationManager: Sends order status notifications and webhooks
  - QuoteManager: Generates quotes from product offerings before ordering

### TIER 3: CAMARA Network APIs
- **SIM Swap Detection**: Detects recent SIM swap events for fraud prevention
- **Number Verification**: Verifies phone number ownership with OTP-based authentication

### TIER 4: Billing & Revenue
- **Usage Metering**: Collects, aggregates, and meters API usage events
- **Billing Engine**: Generates invoices, processes payments, manages disputes

### TIER 5: Cross-Cutting Concerns
- **API Gateway & Security**: Request routing, authentication (OAuth2, API keys), rate limiting
- **Observability**: Metrics collection, health checks, audit logging, distributed tracing, alerting

## Architecture

```
telco-api-integration/
├── src/
│   ├── tmf931/
│   │   ├── catalog/          # Resource Catalog Management
│   │   └── inventory/        # Resource Inventory Management
│   ├── tmf620/
│   │   └── catalog/          # Product Catalog Management (offerings, specs, pricing, bundles)
│   ├── tmf622/
│   │   └── ordering/         # Product Ordering (lifecycle, fulfillment, compensation)
│   ├── camara/
│   │   ├── sim_swap/         # CAMARA SIM Swap API
│   │   └── number_verify/    # CAMARA Number Verification API
│   ├── billing/
│   │   ├── usage/            # Usage Metering
│   │   └── engine/           # Billing Engine
│   └── shared/
│       ├── gateway/          # API Gateway & Security
│       └── observability/    # Observability
├── tests/
│   ├── test_tmf931_catalog.py
│   ├── test_tmf931_inventory.py
│   ├── test_tmf620.py
│   ├── test_tmf622.py
│   ├── test_camara_sim_swap.py
│   ├── test_camara_number_verify.py
│   ├── test_billing_usage.py
│   ├── test_billing_engine.py
│   ├── test_gateway.py
│   └── test_observability.py
├── STAR.md
├── README.md
└── requirements.txt
```

## Running Tests

All tests use `unittest.TestCase` (no pytest required).

```bash
# Run all tests
python3 -m unittest discover -s tests -p "test_*.py"

# Run specific test file
python3 -m unittest tests.test_tmf931_catalog

# Run specific test class
python3 -m unittest tests.test_tmf931_catalog.TestResourceCatalogManager

# Run with verbose output
python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Design Principles

- **Pure Python stdlib**: ZERO external dependencies
- **Real functionality**: No stubs, no pass statements - all classes do real work
- **Production-grade**: Comprehensive error handling, validation, and logging
- **TMF/CAMARA Standards**: Implements TM Forum TMF931 and CAMARA API standards
- **150+ Tests**: All tests must pass before deployment

## Subsystems Overview

### 1. TMF931 Resource Catalog
Implements TM Forum TMF931 Resource Catalog standard for telecom resource management.

### 2. TMF620 Product Catalog
Implements TM Forum TMF620 Product Catalog Management API for managing product offerings, specifications, pricing, and bundles.

### 3. TMF622 Product Ordering
Implements TM Forum TMF622 Product Ordering Management API for managing product orders, quotes, fulfillment, and compensation.

### 4. CAMARA SIM Swap
Implements CAMARA SIM Swap Detection API for fraud prevention in telecom operations.

### 5. CAMARA Number Verification
Implements CAMARA Number Verification API for secure phone number verification.

### 6. Billing Usage Metering
Tracks API usage, applies pricing models (per-call, tiered, volume-based), and generates usage reports.

### 7. Billing Engine
Generates invoices, manages billing cycles, processes payments, handles disputes and credit notes.

### 8. API Gateway
Routes requests, handles authentication (OAuth2, API keys), enforces rate limits, validates requests.

### 9. Observability
Collects metrics, runs health checks, maintains audit trails, provides distributed tracing, and alerts on thresholds.

## Standards Compliance

- **TMF645**: TM Forum REST API Design Guidelines
- **TMF931**: TM Forum Resource Catalog Management API
- **TMF620**: TM Forum Product Catalog Management API
- **TMF622**: TM Forum Product Ordering Management API
- **CAMARA**: CAMARA Open API specifications (SIM Swap, Number Verification)
- **OA Billing**: internal billing integration patterns

## License

Internal project - Not for external distribution.
