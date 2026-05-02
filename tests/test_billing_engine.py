"""
Tests for Billing Engine
"""

import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from billing.engine import (
    BillingCycle, InvoiceStatus, PaymentStatus,
    Invoice, BillingCycleInfo, Payment,
    InvoiceEngine, BillingCycleManager, PaymentProcessor,
    CreditNoteManager, TaxCalculator, BillingDisputeManager
)


class MockUsageReportGenerator:
    """Mock usage report generator for testing"""

    class MockReport:
        def __init__(self):
            self.api_breakdown = {"TMF931": {"total_calls": 100, "cost": 1.0}}
            self.total_cost = 1.0
            self.currency = "USD"

    def generate_report(self, partner_id, period_start, period_end):
        return self.MockReport()


class TestInvoiceEngine(unittest.TestCase):
    """Test InvoiceEngine"""

    def setUp(self):
        mock_report_gen = MockUsageReportGenerator()
        self.engine = InvoiceEngine(mock_report_gen)

    def test_create_invoice(self):
        """Test creating an invoice"""
        period_start = time.time() - 86400
        period_end = time.time()

        invoice = self.engine.create_invoice("partner1", period_start, period_end)

        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.partner_id, "partner1")
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertGreater(invoice.subtotal, 0)

    def test_get_invoice(self):
        """Test getting an invoice"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())

        retrieved = self.engine.get_invoice(invoice.invoice_id)
        self.assertEqual(retrieved.invoice_id, invoice.invoice_id)

    def test_list_invoices(self):
        """Test listing invoices"""
        self.engine.create_invoice("partner1", time.time() - 86400, time.time())
        self.engine.create_invoice("partner1", time.time() - 86400, time.time())

        invoices = self.engine.list_invoices(partner_id="partner1")
        self.assertEqual(len(invoices), 2)

    def test_list_invoices_with_status_filter(self):
        """Test listing invoices with status filter"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())

        draft_invoices = self.engine.list_invoices(status=InvoiceStatus.DRAFT)
        self.assertEqual(len(draft_invoices), 1)

    def test_update_invoice(self):
        """Test updating an invoice"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())

        updated = self.engine.update_invoice(invoice.invoice_id, metadata={"key": "value"})

        self.assertEqual(updated.metadata["key"], "value")

    def test_issue_invoice(self):
        """Test issuing an invoice"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())

        issued = self.engine.issue_invoice(invoice.invoice_id)

        self.assertEqual(issued.status, InvoiceStatus.ISSUED)
        self.assertIsNotNone(issued.issued_at)

    def test_issue_non_draft_fails(self):
        """Test that issuing non-draft invoice fails"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())
        self.engine.issue_invoice(invoice.invoice_id)

        with self.assertRaises(ValueError):
            self.engine.issue_invoice(invoice.invoice_id)

    def test_mark_paid(self):
        """Test marking invoice as paid"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())
        self.engine.issue_invoice(invoice.invoice_id)

        paid = self.engine.mark_paid(invoice.invoice_id)

        self.assertEqual(paid.status, InvoiceStatus.PAID)
        self.assertIsNotNone(paid.paid_at)

    def test_delete_invoice(self):
        """Test deleting an invoice"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())

        result = self.engine.delete_invoice(invoice.invoice_id)
        self.assertTrue(result)

    def test_delete_non_draft_fails(self):
        """Test that deleting non-draft invoice fails"""
        invoice = self.engine.create_invoice("partner1", time.time() - 86400, time.time())
        self.engine.issue_invoice(invoice.invoice_id)

        with self.assertRaises(ValueError):
            self.engine.delete_invoice(invoice.invoice_id)


class TestBillingCycleManager(unittest.TestCase):
    """Test BillingCycleManager"""

    def setUp(self):
        mock_report_gen = MockUsageReportGenerator()
        invoice_engine = InvoiceEngine(mock_report_gen)
        self.cycle_manager = BillingCycleManager(invoice_engine)

    def test_create_cycle(self):
        """Test creating a billing cycle"""
        cycle = self.cycle_manager.create_cycle(
            partner_id="partner1",
            cycle_type=BillingCycle.MONTHLY
        )

        self.assertIsNotNone(cycle)
        self.assertEqual(cycle.partner_id, "partner1")
        self.assertEqual(cycle.cycle_type, BillingCycle.MONTHLY)

    def test_get_cycle(self):
        """Test getting a cycle"""
        cycle = self.cycle_manager.create_cycle("partner1", BillingCycle.MONTHLY)

        retrieved = self.cycle_manager.get_cycle(cycle.cycle_id)
        self.assertEqual(retrieved.cycle_id, cycle.cycle_id)

    def test_get_active_cycles(self):
        """Test getting active cycles"""
        self.cycle_manager.create_cycle("partner1", BillingCycle.MONTHLY)
        self.cycle_manager.create_cycle("partner2", BillingCycle.QUARTERLY)

        active = self.cycle_manager.get_active_cycles()
        self.assertEqual(len(active), 2)

    def test_generate_invoice_for_cycle(self):
        """Test generating invoice for cycle"""
        cycle = self.cycle_manager.create_cycle("partner1", BillingCycle.MONTHLY)

        invoice = self.cycle_manager.generate_invoice_for_cycle(cycle.cycle_id)

        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.partner_id, "partner1")
        self.assertEqual(cycle.invoice_id, invoice.invoice_id)

    def test_generate_invoice_twice_fails(self):
        """Test that generating invoice twice fails"""
        cycle = self.cycle_manager.create_cycle("partner1", BillingCycle.MONTHLY)
        self.cycle_manager.generate_invoice_for_cycle(cycle.cycle_id)

        with self.assertRaises(ValueError):
            self.cycle_manager.generate_invoice_for_cycle(cycle.cycle_id)


class TestPaymentProcessor(unittest.TestCase):
    """Test PaymentProcessor"""

    def setUp(self):
        mock_report_gen = MockUsageReportGenerator()
        invoice_engine = InvoiceEngine(mock_report_gen)
        self.processor = PaymentProcessor(invoice_engine)

        self.invoice = invoice_engine.create_invoice("partner1", time.time() - 86400, time.time())
        invoice_engine.issue_invoice(self.invoice.invoice_id)

    def test_create_payment(self):
        """Test creating a payment"""
        payment = self.processor.create_payment(
            invoice_id=self.invoice.invoice_id,
            amount=self.invoice.total
        )

        self.assertIsNotNone(payment)
        self.assertEqual(payment.invoice_id, self.invoice.invoice_id)
        self.assertEqual(payment.amount, self.invoice.total)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_process_payment(self):
        """Test processing a payment"""
        payment = self.processor.create_payment(self.invoice.invoice_id, self.invoice.total)

        processed = self.processor.process_payment(payment.payment_id)

        # Most likely succeeds (90% success rate)
        self.assertIn(processed.status, [PaymentStatus.COMPLETED, PaymentStatus.FAILED])

    def test_get_payment(self):
        """Test getting a payment"""
        payment = self.processor.create_payment(self.invoice.invoice_id, self.invoice.total)

        retrieved = self.processor.get_payment(payment.payment_id)
        self.assertEqual(retrieved.payment_id, payment.payment_id)

    def test_get_payments_for_invoice(self):
        """Test getting payments for invoice"""
        self.processor.create_payment(self.invoice.invoice_id, 0.5)
        self.processor.create_payment(self.invoice.invoice_id, 0.5)

        payments = self.processor.get_payments_for_invoice(self.invoice.invoice_id)
        self.assertEqual(len(payments), 2)

    def test_refund_payment(self):
        """Test refunding a payment"""
        payment = self.processor.create_payment(self.invoice.invoice_id, self.invoice.total)
        processed = self.processor.process_payment(payment.payment_id)

        if processed.status == PaymentStatus.COMPLETED:
            refunded = self.processor.refund_payment(payment.payment_id)
            self.assertEqual(refunded.status, PaymentStatus.REFUNDED)


class TestCreditNoteManager(unittest.TestCase):
    """Test CreditNoteManager"""

    def setUp(self):
        mock_report_gen = MockUsageReportGenerator()
        invoice_engine = InvoiceEngine(mock_report_gen)
        self.credit_manager = CreditNoteManager(invoice_engine)

        self.invoice = invoice_engine.create_invoice("partner1", time.time() - 86400, time.time())

    def test_create_credit_note(self):
        """Test creating a credit note"""
        credit_note = self.credit_manager.create_credit_note(
            invoice_id=self.invoice.invoice_id,
            amount=0.5,
            reason="Billing error"
        )

        self.assertIsNotNone(credit_note)
        self.assertEqual(credit_note.invoice_id, self.invoice.invoice_id)
        self.assertEqual(credit_note.amount, 0.5)

    def test_get_credit_note(self):
        """Test getting a credit note"""
        credit_note = self.credit_manager.create_credit_note(
            self.invoice.invoice_id, 0.5, "Reason"
        )

        retrieved = self.credit_manager.get_credit_note(credit_note.credit_note_id)
        self.assertEqual(retrieved.credit_note_id, credit_note.credit_note_id)

    def test_apply_credit_note(self):
        """Test applying a credit note"""
        credit_note = self.credit_manager.create_credit_note(
            self.invoice.invoice_id, 0.5, "Reason"
        )

        applied = self.credit_manager.apply_credit_note(credit_note.credit_note_id)

        self.assertTrue(applied.applied)
        self.assertEqual(self.invoice.total, 0.5)  # Was 1.0, reduced by 0.5

    def test_get_credit_notes_for_invoice(self):
        """Test getting credit notes for invoice"""
        self.credit_manager.create_credit_note(self.invoice.invoice_id, 0.5, "Reason 1")
        self.credit_manager.create_credit_note(self.invoice.invoice_id, 0.3, "Reason 2")

        credit_notes = self.credit_manager.get_credit_notes_for_invoice(self.invoice.invoice_id)
        self.assertEqual(len(credit_notes), 2)


class TestTaxCalculator(unittest.TestCase):
    """Test TaxCalculator"""

    def setUp(self):
        self.calculator = TaxCalculator()

    def test_create_tax_rate(self):
        """Test creating a tax rate"""
        tax_rate = self.calculator.create_tax_rate(
            jurisdiction="US",
            rate=10.0,
            tax_type="vat"
        )

        self.assertIsNotNone(tax_rate)
        self.assertEqual(tax_rate.jurisdiction, "US")
        self.assertEqual(tax_rate.rate, 10.0)

    def test_calculate_tax(self):
        """Test calculating tax"""
        self.calculator.create_tax_rate("US", 10.0, "vat")

        tax = self.calculator.calculate_tax(100.0, "US", "vat")

        self.assertEqual(tax, 10.0)

    def test_calculate_tax_no_rate(self):
        """Test calculating tax with no rate"""
        tax = self.calculator.calculate_tax(100.0, "XX", "vat")
        self.assertEqual(tax, 0.0)

    def test_list_tax_rates(self):
        """Test listing tax rates"""
        self.calculator.create_tax_rate("US", 10.0, "vat")
        self.calculator.create_tax_rate("UK", 20.0, "vat")

        tax_rates = self.calculator.list_tax_rates()
        self.assertEqual(len(tax_rates), 2)

        us_rates = self.calculator.list_tax_rates(jurisdiction="US")
        self.assertEqual(len(us_rates), 1)


class TestBillingDisputeManager(unittest.TestCase):
    """Test BillingDisputeManager"""

    def setUp(self):
        mock_report_gen = MockUsageReportGenerator()
        invoice_engine = InvoiceEngine(mock_report_gen)
        self.dispute_manager = BillingDisputeManager(invoice_engine)

        self.invoice = invoice_engine.create_invoice("partner1", time.time() - 86400, time.time())
        invoice_engine.issue_invoice(self.invoice.invoice_id)

    def test_create_dispute(self):
        """Test creating a dispute"""
        dispute = self.dispute_manager.create_dispute(
            invoice_id=self.invoice.invoice_id,
            partner_id="partner1",
            reason="Incorrect charges",
            amount_in_dispute=0.5
        )

        self.assertIsNotNone(dispute)
        self.assertEqual(dispute.invoice_id, self.invoice.invoice_id)
        self.assertEqual(dispute.status, "open")
        self.assertEqual(self.invoice.status, InvoiceStatus.DISPUTED)

    def test_resolve_dispute(self):
        """Test resolving a dispute"""
        dispute = self.dispute_manager.create_dispute(
            self.invoice.invoice_id, "partner1", "Reason", 0.5
        )

        resolved = self.dispute_manager.resolve_dispute(
            dispute.dispute_id,
            "Adjustment applied"
        )

        self.assertEqual(resolved.status, "resolved")
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(self.invoice.status, InvoiceStatus.ISSUED)

    def test_get_dispute(self):
        """Test getting a dispute"""
        dispute = self.dispute_manager.create_dispute(
            self.invoice.invoice_id, "partner1", "Reason", 0.5
        )

        retrieved = self.dispute_manager.get_dispute(dispute.dispute_id)
        self.assertEqual(retrieved.dispute_id, dispute.dispute_id)

    def test_get_disputes_for_invoice(self):
        """Test getting disputes for invoice"""
        self.dispute_manager.create_dispute(self.invoice.invoice_id, "partner1", "Reason 1", 0.3)
        self.dispute_manager.create_dispute(self.invoice.invoice_id, "partner1", "Reason 2", 0.2)

        disputes = self.dispute_manager.get_disputes_for_invoice(self.invoice.invoice_id)
        self.assertEqual(len(disputes), 2)

    def test_get_open_disputes(self):
        """Test getting open disputes"""
        self.dispute_manager.create_dispute(self.invoice.invoice_id, "partner1", "Reason", 0.5)

        open_disputes = self.dispute_manager.get_open_disputes()
        self.assertEqual(len(open_disputes), 1)


if __name__ == "__main__":
    unittest.main()
