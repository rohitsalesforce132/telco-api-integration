"""
Tests for TMF931 Resource Inventory API
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tmf931.inventory import (
    ResourceState, ResourceType, RelationshipType,
    ResourceInventoryManager, ResourceRelationshipManager,
    ResourceStateMapper, ResourceActivationManager, CapacityTracker
)


class TestResourceInventoryManager(unittest.TestCase):
    """Test ResourceInventoryManager"""

    def setUp(self):
        self.manager = ResourceInventoryManager()

    def test_create_resource(self):
        """Test creating a resource"""
        resource = self.manager.create_resource(
            name="Test Resource",
            resource_type=ResourceType.LOGICAL,
            specification_id="spec_123"
        )

        self.assertIsNotNone(resource)
        self.assertEqual(resource.name, "Test Resource")
        self.assertEqual(resource.resource_type, ResourceType.LOGICAL)
        self.assertEqual(resource.state, ResourceState.PLANNED)

    def test_get_resource(self):
        """Test getting a resource"""
        resource = self.manager.create_resource(
            name="Test",
            resource_type=ResourceType.LOGICAL,
            specification_id="spec_123"
        )

        retrieved = self.manager.get_resource(resource.resource_id)
        self.assertEqual(retrieved.resource_id, resource.resource_id)

    def test_list_resources(self):
        """Test listing resources"""
        self.manager.create_resource(name="R1", resource_type=ResourceType.LOGICAL, specification_id="s1")
        self.manager.create_resource(name="R2", resource_type=ResourceType.PHYSICAL, specification_id="s2")

        resources = self.manager.list_resources()
        self.assertEqual(len(resources), 2)

    def test_list_resources_with_state_filter(self):
        """Test listing resources with state filter"""
        r1 = self.manager.create_resource(name="R1", resource_type=ResourceType.LOGICAL, specification_id="s1")
        r2 = self.manager.create_resource(name="R2", resource_type=ResourceType.LOGICAL, specification_id="s2")

        state_mapper = ResourceStateMapper(self.manager)
        # Go through proper state transitions: PLANNED -> ALLOCATED -> ACTIVE
        state_mapper.transition_state(r1.resource_id, ResourceState.ALLOCATED)
        state_mapper.transition_state(r1.resource_id, ResourceState.ACTIVE)

        active = self.manager.list_resources(state=ResourceState.ACTIVE)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].resource_id, r1.resource_id)

    def test_update_resource(self):
        """Test updating a resource"""
        resource = self.manager.create_resource(name="Original", resource_type=ResourceType.LOGICAL, specification_id="s1")

        updated = self.manager.update_resource(
            resource.resource_id,
            name="Updated",
            state=ResourceState.ALLOCATED
        )

        self.assertEqual(updated.name, "Updated")
        self.assertEqual(updated.state, ResourceState.ALLOCATED)

    def test_delete_resource(self):
        """Test deleting a resource"""
        resource = self.manager.create_resource(name="Test", resource_type=ResourceType.LOGICAL, specification_id="s1")

        result = self.manager.delete_resource(resource.resource_id)
        self.assertTrue(result)

        retrieved = self.manager.get_resource(resource.resource_id)
        self.assertIsNone(retrieved)


class TestResourceRelationshipManager(unittest.TestCase):
    """Test ResourceRelationshipManager"""

    def setUp(self):
        self.inventory_manager = ResourceInventoryManager()
        self.r1 = self.inventory_manager.create_resource("Resource 1", ResourceType.LOGICAL, "spec1")
        self.r2 = self.inventory_manager.create_resource("Resource 2", ResourceType.PHYSICAL, "spec2")
        self.rel_manager = ResourceRelationshipManager(self.inventory_manager)

    def test_create_relationship(self):
        """Test creating a relationship"""
        rel = self.rel_manager.create_relationship(
            source_id=self.r1.resource_id,
            target_id=self.r2.resource_id,
            relationship_type=RelationshipType.DEPENDS_ON
        )

        self.assertIsNotNone(rel)
        self.assertEqual(rel.relationship_type, RelationshipType.DEPENDS_ON)
        self.assertEqual(rel.source_id, self.r1.resource_id)
        self.assertEqual(rel.target_id, self.r2.resource_id)

    def test_get_relationship(self):
        """Test getting a relationship"""
        rel = self.rel_manager.create_relationship(
            source_id=self.r1.resource_id,
            target_id=self.r2.resource_id,
            relationship_type=RelationshipType.CONNECTS_TO
        )

        retrieved = self.rel_manager.get_relationship(rel.relationship_id)
        self.assertEqual(retrieved.relationship_id, rel.relationship_id)

    def test_get_relationships(self):
        """Test getting relationships for a resource"""
        r3 = self.inventory_manager.create_resource("Resource 3", ResourceType.LOGICAL, "spec3")

        self.rel_manager.create_relationship(self.r1.resource_id, self.r2.resource_id, RelationshipType.DEPENDS_ON)
        self.rel_manager.create_relationship(self.r1.resource_id, r3.resource_id, RelationshipType.CONNECTS_TO)

        relationships = self.rel_manager.get_relationships(self.r1.resource_id, direction="source")
        self.assertEqual(len(relationships), 2)

    def test_get_related_resources(self):
        """Test getting related resources"""
        self.rel_manager.create_relationship(self.r1.resource_id, self.r2.resource_id, RelationshipType.CONTAINS)

        related = self.rel_manager.get_related_resources(self.r1.resource_id)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0].resource_id, self.r2.resource_id)

    def test_delete_relationship(self):
        """Test deleting a relationship"""
        rel = self.rel_manager.create_relationship(
            source_id=self.r1.resource_id,
            target_id=self.r2.resource_id,
            relationship_type=RelationshipType.DEPENDS_ON
        )

        result = self.rel_manager.delete_relationship(rel.relationship_id)
        self.assertTrue(result)


class TestResourceStateMapper(unittest.TestCase):
    """Test ResourceStateMapper"""

    def setUp(self):
        self.inventory_manager = ResourceInventoryManager()
        self.resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1")
        self.state_mapper = ResourceStateMapper(self.inventory_manager)

    def test_transition_planned_to_reserved(self):
        """Test transitioning from planned to reserved"""
        updated = self.state_mapper.transition_state(self.resource.resource_id, ResourceState.RESERVED)
        self.assertEqual(updated.state, ResourceState.RESERVED)

    def test_transition_reserved_to_allocated(self):
        """Test transitioning from reserved to allocated"""
        self.state_mapper.transition_state(self.resource.resource_id, ResourceState.RESERVED)
        updated = self.state_mapper.transition_state(self.resource.resource_id, ResourceState.ALLOCATED)
        self.assertEqual(updated.state, ResourceState.ALLOCATED)

    def test_transition_allocated_to_active(self):
        """Test transitioning from allocated to active"""
        self.state_mapper.transition_state(self.resource.resource_id, ResourceState.RESERVED)
        self.state_mapper.transition_state(self.resource.resource_id, ResourceState.ALLOCATED)
        updated = self.state_mapper.transition_state(self.resource.resource_id, ResourceState.ACTIVE)

        self.assertEqual(updated.state, ResourceState.ACTIVE)
        self.assertIsNotNone(updated.activated_at)

    def test_invalid_transition(self):
        """Test that invalid transitions fail"""
        with self.assertRaises(ValueError):
            self.state_mapper.transition_state(self.resource.resource_id, ResourceState.ACTIVE)

    def test_can_transition(self):
        """Test checking if transition is valid"""
        can_reserve = self.state_mapper.can_transition(self.resource.resource_id, ResourceState.RESERVED)
        self.assertTrue(can_reserve)

        # Can transition from PLANNED to TERMINATED (it's a valid transition now)
        can_terminate = self.state_mapper.can_transition(self.resource.resource_id, ResourceState.TERMINATED)
        self.assertTrue(can_terminate)

    def test_get_resources_by_state(self):
        """Test getting resources by state"""
        r2 = self.inventory_manager.create_resource("R2", ResourceType.LOGICAL, "spec2")

        # Go through proper state transitions
        self.state_mapper.transition_state(self.resource.resource_id, ResourceState.ALLOCATED)
        self.state_mapper.transition_state(self.resource.resource_id, ResourceState.ACTIVE)

        active = self.state_mapper.get_resources_by_state(ResourceState.ACTIVE)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].resource_id, self.resource.resource_id)

    def test_get_state_summary(self):
        """Test getting state summary"""
        summary = self.state_mapper.get_state_summary()

        self.assertIn("planned", summary)
        self.assertIn("active", summary)
        self.assertIn("terminated", summary)


class TestResourceActivationManager(unittest.TestCase):
    """Test ResourceActivationManager"""

    def setUp(self):
        self.inventory_manager = ResourceInventoryManager()
        self.state_mapper = ResourceStateMapper(self.inventory_manager)
        self.activation_manager = ResourceActivationManager(self.inventory_manager, self.state_mapper)

    def test_activate_resource(self):
        """Test activating a resource"""
        resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1")
        self.state_mapper.transition_state(resource.resource_id, ResourceState.ALLOCATED)

        activated = self.activation_manager.activate_resource(resource.resource_id, "user1")
        self.assertEqual(activated.state, ResourceState.ACTIVE)
        self.assertIsNotNone(activated.activated_at)

    def test_activate_non_allocated_fails(self):
        """Test that activating non-allocated resource fails"""
        resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1")

        with self.assertRaises(ValueError):
            self.activation_manager.activate_resource(resource.resource_id, "user1")

    def test_deactivate_resource(self):
        """Test deactivating a resource"""
        resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1")
        self.state_mapper.transition_state(resource.resource_id, ResourceState.ALLOCATED)
        self.activation_manager.activate_resource(resource.resource_id, "user1")

        deactivated = self.activation_manager.deactivate_resource(resource.resource_id, "user1")
        self.assertEqual(deactivated.state, ResourceState.INACTIVE)

    def test_terminate_resource(self):
        """Test terminating a resource"""
        resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1")
        self.state_mapper.transition_state(resource.resource_id, ResourceState.ALLOCATED)
        self.activation_manager.activate_resource(resource.resource_id, "user1")

        terminated = self.activation_manager.terminate_resource(resource.resource_id, "user1")
        self.assertEqual(terminated.state, ResourceState.TERMINATED)
        self.assertIsNotNone(terminated.terminated_at)

    def test_get_activation_history(self):
        """Test getting activation history"""
        resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1")
        self.state_mapper.transition_state(resource.resource_id, ResourceState.ALLOCATED)
        self.activation_manager.activate_resource(resource.resource_id, "user1")

        history = self.activation_manager.get_activation_history(resource.resource_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "activate")

    def test_get_active_resources(self):
        """Test getting active resources"""
        r1 = self.inventory_manager.create_resource("R1", ResourceType.LOGICAL, "spec1")
        r2 = self.inventory_manager.create_resource("R2", ResourceType.LOGICAL, "spec2")

        self.state_mapper.transition_state(r1.resource_id, ResourceState.ALLOCATED)
        self.activation_manager.activate_resource(r1.resource_id, "user1")

        active = self.activation_manager.get_active_resources()
        self.assertEqual(len(active), 1)


class TestCapacityTracker(unittest.TestCase):
    """Test CapacityTracker"""

    def setUp(self):
        self.inventory_manager = ResourceInventoryManager()
        self.resource = self.inventory_manager.create_resource("Test", ResourceType.LOGICAL, "spec1",
                                                               capacity={"total": 100, "cpu": 10})
        self.tracker = CapacityTracker(self.inventory_manager)

    def test_update_capacity(self):
        """Test updating capacity"""
        updated = self.tracker.update_capacity(self.resource.resource_id, {"total": 200, "cpu": 20})
        self.assertEqual(updated.capacity["total"], 200)
        self.assertEqual(updated.capacity["cpu"], 20)

    def test_update_utilization(self):
        """Test updating utilization"""
        updated = self.tracker.update_utilization(self.resource.resource_id, {"used": 50})
        self.assertEqual(updated.utilization["used"], 50)

    def test_get_utilization_rate(self):
        """Test getting utilization rate"""
        self.tracker.update_utilization(self.resource.resource_id, {"total": 50})

        rate = self.tracker.get_utilization_rate(self.resource.resource_id, "total")
        self.assertEqual(rate, 0.5)

    def test_reserve_capacity(self):
        """Test reserving capacity"""
        reservation = self.tracker.reserve_capacity(
            self.resource.resource_id,
            "user1",
            {"total": 30}
        )

        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.capacity["total"], 30)

    def test_reserve_capacity_insufficient_fails(self):
        """Test that reserving insufficient capacity fails"""
        self.tracker.update_utilization(self.resource.resource_id, {"total": 80})

        with self.assertRaises(ValueError):
            self.tracker.reserve_capacity(
                self.resource.resource_id,
                "user1",
                {"total": 50}  # Would exceed 100
            )

    def test_release_reservation(self):
        """Test releasing reservation"""
        reservation = self.tracker.reserve_capacity(
            self.resource.resource_id,
            "user1",
            {"total": 30}
        )

        result = self.tracker.release_reservation(reservation.reservation_id)
        self.assertTrue(result)

    def test_get_reservations(self):
        """Test getting reservations"""
        self.tracker.reserve_capacity(self.resource.resource_id, "user1", {"total": 10})
        self.tracker.reserve_capacity(self.resource.resource_id, "user2", {"total": 20})

        reservations = self.tracker.get_reservations(self.resource.resource_id)
        self.assertEqual(len(reservations), 2)

    def test_get_capacity_summary(self):
        """Test getting capacity summary"""
        self.tracker.update_utilization(self.resource.resource_id, {"total": 50, "cpu": 5})

        summary = self.tracker.get_capacity_summary(self.resource.resource_id)

        self.assertEqual(summary["resource_id"], self.resource.resource_id)
        self.assertIn("capacity", summary)
        self.assertIn("utilization", summary)
        self.assertIn("utilization_rates", summary)

    def test_get_overutilized_resources(self):
        """Test getting overutilized resources"""
        self.tracker.update_utilization(self.resource.resource_id, {"total": 95})

        overutilized = self.tracker.get_overutilized_resources(threshold=0.9)
        self.assertEqual(len(overutilized), 1)


if __name__ == "__main__":
    unittest.main()
