"""
TMF931 Resource Inventory API - Resource Inventory Management
Implements TM Forum TMF931 Resource Inventory standard
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class ResourceState(Enum):
    """Resource lifecycle states"""
    PLANNED = "planned"
    RESERVED = "reserved"
    ALLOCATED = "allocated"
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ERROR = "error"


class ResourceType(Enum):
    """Resource types"""
    LOGICAL = "logical"
    PHYSICAL = "physical"
    HYBRID = "hybrid"


class RelationshipType(Enum):
    """Relationship types between resources"""
    DEPENDS_ON = "dependsOn"
    CONNECTS_TO = "connectsTo"
    CONTAINS = "contains"
    COMPOSED_OF = "composedOf"
    REALIZES = "realizes"
    HOSTED_ON = "hostedOn"


@dataclass
class ResourceRelationship:
    """Relationship between resources"""
    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class Resource:
    """Instantiated resource"""
    resource_id: str
    name: str
    resource_type: ResourceType
    specification_id: str
    state: ResourceState = ResourceState.PLANNED
    attributes: Dict[str, Any] = field(default_factory=dict)
    capacity: Optional[Dict[str, Any]] = None
    utilization: Dict[str, Any] = field(default_factory=dict)
    location: Optional[Dict[str, Any]] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    activated_at: Optional[float] = None
    terminated_at: Optional[float] = None


@dataclass
class CapacityReservation:
    """Capacity reservation for resources"""
    reservation_id: str
    resource_id: str
    reserved_by: str
    capacity: Dict[str, Any]
    expires_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class ResourceInventoryManager:
    """Tracks instantiated resources (logical/physical)"""

    def __init__(self):
        self._resources: Dict[str, Resource] = {}
        self._counter = 0

    def create_resource(self, name: str, resource_type: ResourceType,
                       specification_id: str,
                       attributes: Optional[Dict[str, Any]] = None,
                       capacity: Optional[Dict[str, Any]] = None,
                       location: Optional[Dict[str, Any]] = None,
                       parent_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> Resource:
        """Create a new resource"""
        resource_id = self._generate_id("resource")
        resource = Resource(
            resource_id=resource_id,
            name=name,
            resource_type=resource_type,
            specification_id=specification_id,
            state=ResourceState.PLANNED,
            attributes=attributes or {},
            capacity=capacity or {},
            location=location or {},
            parent_id=parent_id,
            metadata=metadata or {}
        )
        self._resources[resource_id] = resource
        return resource

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get resource by ID"""
        return self._resources.get(resource_id)

    def list_resources(self, state: Optional[ResourceState] = None,
                      resource_type: Optional[ResourceType] = None,
                      specification_id: Optional[str] = None) -> List[Resource]:
        """List resources with filters"""
        resources = list(self._resources.values())

        if state:
            resources = [r for r in resources if r.state == state]

        if resource_type:
            resources = [r for r in resources if r.resource_type == resource_type]

        if specification_id:
            resources = [r for r in resources if r.specification_id == specification_id]

        return resources

    def update_resource(self, resource_id: str, **kwargs) -> Resource:
        """Update resource attributes"""
        resource = self._get_resource_or_raise(resource_id)

        for key, value in kwargs.items():
            if hasattr(resource, key) and key not in ('resource_id', 'created_at'):
                setattr(resource, key, value)

        return resource

    def delete_resource(self, resource_id: str) -> bool:
        """Delete resource"""
        if resource_id in self._resources:
            del self._resources[resource_id]
            return True
        return False

    def get_resources_by_spec(self, specification_id: str) -> List[Resource]:
        """Get all resources for a specification"""
        return [r for r in self._resources.values() if r.specification_id == specification_id]

    def get_resources_by_location(self, location: Dict[str, Any]) -> List[Resource]:
        """Get resources at a specific location"""
        return [
            r for r in self._resources.values()
            if r.location and self._location_match(r.location, location)
        ]

    def _get_resource_or_raise(self, resource_id: str) -> Resource:
        """Get resource or raise exception"""
        resource = self.get_resource(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        return resource

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"

    def _location_match(self, resource_location: Dict[str, Any],
                       query_location: Dict[str, Any]) -> bool:
        """Check if resource location matches query"""
        for key, value in query_location.items():
            if resource_location.get(key) != value:
                return False
        return True


class ResourceRelationshipManager:
    """Manages resource relationships (dependsOn, connectsTo, contains)"""

    def __init__(self, inventory_manager: ResourceInventoryManager):
        self.inventory_manager = inventory_manager
        self._relationships: Dict[str, ResourceRelationship] = {}
        self._counter = 0

    def create_relationship(self, source_id: str, target_id: str,
                           relationship_type: RelationshipType,
                           metadata: Optional[Dict[str, Any]] = None) -> ResourceRelationship:
        """Create a relationship between resources"""
        # Validate resources exist
        self.inventory_manager._get_resource_or_raise(source_id)
        self.inventory_manager._get_resource_or_raise(target_id)

        relationship_id = self._generate_id("rel")
        relationship = ResourceRelationship(
            relationship_id=relationship_id,
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            metadata=metadata or {}
        )
        self._relationships[relationship_id] = relationship
        return relationship

    def get_relationship(self, relationship_id: str) -> Optional[ResourceRelationship]:
        """Get relationship by ID"""
        return self._relationships.get(relationship_id)

    def get_relationships(self, resource_id: str,
                         direction: str = "both") -> List[ResourceRelationship]:
        """Get relationships for a resource

        Args:
            resource_id: Resource ID
            direction: "source", "target", or "both"
        """
        relationships = []

        for rel in self._relationships.values():
            if direction in ("source", "both") and rel.source_id == resource_id:
                relationships.append(rel)
            if direction in ("target", "both") and rel.target_id == resource_id:
                relationships.append(rel)

        return relationships

    def get_related_resources(self, resource_id: str,
                              relationship_type: Optional[RelationshipType] = None,
                              direction: str = "both") -> List[Resource]:
        """Get resources related to a resource"""
        relationships = self.get_relationships(resource_id, direction)
        related_ids = set()

        for rel in relationships:
            if relationship_type is None or rel.relationship_type == relationship_type:
                if rel.source_id == resource_id:
                    related_ids.add(rel.target_id)
                if rel.target_id == resource_id:
                    related_ids.add(rel.source_id)

        return [
            self.inventory_manager._resources[rid]
            for rid in related_ids
            if rid in self.inventory_manager._resources
        ]

    def delete_relationship(self, relationship_id: str) -> bool:
        """Delete relationship"""
        if relationship_id in self._relationships:
            del self._relationships[relationship_id]
            return True
        return False

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class ResourceStateMapper:
    """Maps resource states (planned, reserved, active, terminated)"""

    VALID_TRANSITIONS = {
        ResourceState.PLANNED: [ResourceState.RESERVED, ResourceState.ALLOCATED, ResourceState.TERMINATED],
        ResourceState.RESERVED: [ResourceState.ALLOCATED, ResourceState.PLANNED, ResourceState.TERMINATED],
        ResourceState.ALLOCATED: [ResourceState.ACTIVE, ResourceState.ERROR, ResourceState.TERMINATED],
        ResourceState.ACTIVE: [ResourceState.INACTIVE, ResourceState.TERMINATED, ResourceState.ERROR],
        ResourceState.INACTIVE: [ResourceState.ACTIVE, ResourceState.TERMINATED],
        ResourceState.ERROR: [ResourceState.PLANNED, ResourceState.ALLOCATED, ResourceState.TERMINATED],
        ResourceState.TERMINATED: [ResourceState.PLANNED]
    }

    def __init__(self, inventory_manager: ResourceInventoryManager):
        self.inventory_manager = inventory_manager

    def transition_state(self, resource_id: str, new_state: ResourceState) -> Resource:
        """Transition resource to new state"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)
        current_state = resource.state

        # Validate transition
        if new_state not in self.VALID_TRANSITIONS.get(current_state, []):
            raise ValueError(
                f"Invalid transition from {current_state.value} to {new_state.value} for resource {resource_id}"
            )

        # Update state and timestamps
        old_state = resource.state
        resource.state = new_state

        if new_state == ResourceState.ACTIVE and resource.activated_at is None:
            resource.activated_at = time.time()
        elif new_state == ResourceState.TERMINATED and resource.terminated_at is None:
            resource.terminated_at = time.time()

        return resource

    def can_transition(self, resource_id: str, new_state: ResourceState) -> bool:
        """Check if transition is valid"""
        resource = self.inventory_manager.get_resource(resource_id)
        if not resource:
            return False

        return new_state in self.VALID_TRANSITIONS.get(resource.state, [])

    def get_resources_by_state(self, state: ResourceState) -> List[Resource]:
        """Get all resources in a specific state"""
        return self.inventory_manager.list_resources(state=state)

    def get_state_summary(self) -> Dict[str, int]:
        """Get summary of resources by state"""
        summary = {state.value: 0 for state in ResourceState}

        for resource in self.inventory_manager.list_resources():
            summary[resource.state.value] += 1

        return summary


class ResourceActivationManager:
    """Handles resource activation/deactivation workflows"""

    def __init__(self, inventory_manager: ResourceInventoryManager,
                 state_mapper: ResourceStateMapper):
        self.inventory_manager = inventory_manager
        self.state_mapper = state_mapper
        self._activation_log: List[Dict[str, Any]] = []

    def activate_resource(self, resource_id: str, activated_by: str) -> Resource:
        """Activate a resource"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)

        # Can only activate allocated resources
        if resource.state not in (ResourceState.ALLOCATED, ResourceState.INACTIVE):
            raise ValueError(
                f"Cannot activate resource in state {resource.state.value}. "
                f"Must be ALLOCATED or INACTIVE"
            )

        # Transition to active
        resource = self.state_mapper.transition_state(resource_id, ResourceState.ACTIVE)
        resource.activated_at = time.time()

        # Log activation
        self._activation_log.append({
            "resource_id": resource_id,
            "action": "activate",
            "activated_by": activated_by,
            "timestamp": time.time()
        })

        return resource

    def deactivate_resource(self, resource_id: str, deactivated_by: str) -> Resource:
        """Deactivate a resource"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)

        # Can only deactivate active resources
        if resource.state != ResourceState.ACTIVE:
            raise ValueError(
                f"Cannot deactivate resource in state {resource.state.value}. "
                f"Must be ACTIVE"
            )

        # Transition to inactive
        resource = self.state_mapper.transition_state(resource_id, ResourceState.INACTIVE)

        # Log deactivation
        self._activation_log.append({
            "resource_id": resource_id,
            "action": "deactivate",
            "deactivated_by": deactivated_by,
            "timestamp": time.time()
        })

        return resource

    def terminate_resource(self, resource_id: str, terminated_by: str,
                          reason: Optional[str] = None) -> Resource:
        """Terminate a resource"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)

        # Can terminate from most states
        if not self.state_mapper.can_transition(resource_id, ResourceState.TERMINATED):
            raise ValueError(
                f"Cannot terminate resource in state {resource.state.value}"
            )

        # Transition to terminated
        resource = self.state_mapper.transition_state(resource_id, ResourceState.TERMINATED)
        resource.terminated_at = time.time()

        # Log termination
        self._activation_log.append({
            "resource_id": resource_id,
            "action": "terminate",
            "terminated_by": terminated_by,
            "reason": reason,
            "timestamp": time.time()
        })

        return resource

    def get_activation_history(self, resource_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get activation history"""
        if resource_id:
            return [log for log in self._activation_log if log["resource_id"] == resource_id]
        return self._activation_log.copy()

    def get_active_resources(self) -> List[Resource]:
        """Get all active resources"""
        return self.state_mapper.get_resources_by_state(ResourceState.ACTIVE)

    def get_terminated_resources(self, since: Optional[float] = None) -> List[Resource]:
        """Get terminated resources"""
        terminated = self.state_mapper.get_resources_by_state(ResourceState.TERMINATED)

        if since:
            terminated = [
                r for r in terminated
                if r.terminated_at and r.terminated_at >= since
            ]

        return terminated


class CapacityTracker:
    """Tracks resource capacity and utilization"""

    def __init__(self, inventory_manager: ResourceInventoryManager):
        self.inventory_manager = inventory_manager
        self._reservations: Dict[str, CapacityReservation] = {}
        self._counter = 0

    def update_capacity(self, resource_id: str, capacity: Dict[str, Any]) -> Resource:
        """Update resource capacity"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)
        resource.capacity = capacity
        return resource

    def update_utilization(self, resource_id: str, utilization: Dict[str, Any]) -> Resource:
        """Update resource utilization"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)
        resource.utilization = utilization
        return resource

    def get_utilization_rate(self, resource_id: str, metric: str = "total") -> float:
        """Get utilization rate for a resource"""
        resource = self.inventory_manager.get_resource(resource_id)
        if not resource or not resource.capacity or not resource.utilization:
            return 0.0

        total = resource.capacity.get(metric, 0)
        used = resource.utilization.get(metric, 0)

        if total == 0:
            return 0.0

        return used / total

    def reserve_capacity(self, resource_id: str, reserved_by: str,
                        capacity: Dict[str, Any],
                        expires_in_seconds: int = 3600) -> CapacityReservation:
        """Reserve capacity on a resource"""
        resource = self.inventory_manager._get_resource_or_raise(resource_id)

        # Check if capacity is available
        for metric, value in capacity.items():
            if not self._check_capacity_available(resource, metric, value):
                raise ValueError(
                    f"Insufficient capacity for metric {metric} on resource {resource_id}"
                )

        # Create reservation
        reservation_id = self._generate_id("reservation")
        reservation = CapacityReservation(
            reservation_id=reservation_id,
            resource_id=resource_id,
            reserved_by=reserved_by,
            capacity=capacity,
            expires_at=time.time() + expires_in_seconds
        )
        self._reservations[reservation_id] = reservation

        # Update utilization
        for metric, value in capacity.items():
            if metric not in resource.utilization:
                resource.utilization[metric] = 0
            resource.utilization[metric] += value

        return reservation

    def release_reservation(self, reservation_id: str) -> bool:
        """Release a capacity reservation"""
        if reservation_id not in self._reservations:
            return False

        reservation = self._reservations[reservation_id]
        resource = self.inventory_manager.get_resource(reservation.resource_id)

        if resource:
            # Return capacity
            for metric, value in reservation.capacity.items():
                if metric in resource.utilization:
                    resource.utilization[metric] -= value
                    if resource.utilization[metric] < 0:
                        resource.utilization[metric] = 0

        del self._reservations[reservation_id]
        return True

    def get_reservations(self, resource_id: Optional[str] = None) -> List[CapacityReservation]:
        """Get capacity reservations"""
        reservations = list(self._reservations.values())

        if resource_id:
            reservations = [r for r in reservations if r.resource_id == resource_id]

        return reservations

    def cleanup_expired_reservations(self) -> int:
        """Clean up expired reservations"""
        current_time = time.time()
        expired_ids = [
            rid for rid, res in self._reservations.items()
            if res.expires_at < current_time
        ]

        for rid in expired_ids:
            self.release_reservation(rid)

        return len(expired_ids)

    def get_capacity_summary(self, resource_id: str) -> Dict[str, Any]:
        """Get capacity summary for a resource"""
        resource = self.inventory_manager.get_resource(resource_id)
        if not resource:
            return {}

        summary = {
            "resource_id": resource_id,
            "name": resource.name,
            "capacity": resource.capacity or {},
            "utilization": resource.utilization or {},
            "utilization_rates": {}
        }

        # Calculate utilization rates
        if resource.capacity:
            for metric in resource.capacity:
                summary["utilization_rates"][metric] = self.get_utilization_rate(resource_id, metric)

        return summary

    def get_overutilized_resources(self, threshold: float = 0.9) -> List[Dict[str, Any]]:
        """Get resources with utilization above threshold"""
        overutilized = []

        for resource in self.inventory_manager.list_resources():
            if not resource.capacity:
                continue

            max_utilization = 0.0
            for metric in resource.capacity:
                rate = self.get_utilization_rate(resource.resource_id, metric)
                if rate > max_utilization:
                    max_utilization = rate

            if max_utilization > threshold:
                overutilized.append({
                    "resource_id": resource.resource_id,
                    "name": resource.name,
                    "max_utilization": max_utilization
                })

        return overutilized

    def _check_capacity_available(self, resource: Resource, metric: str, value: float) -> bool:
        """Check if capacity is available"""
        total = resource.capacity.get(metric, 0)
        used = resource.utilization.get(metric, 0)

        return (used + value) <= total

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"
