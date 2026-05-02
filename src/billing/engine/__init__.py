"""
Billing Engine - Invoice Generation and Payment Processing
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from collections import defaultdict


class BillingCycle(Enum):
    """Billing cycle types"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    CUSTOM = "custom"


class InvoiceStatus(Enum):
    """Invoice status"""
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class PaymentStatus(Enum):
    """Payment status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class Invoice:
    """Generated invoice"""
    invoice_id: str
    partner_id: str
    cycle_id: str
    period_start: float
    period_end: float
    status: InvoiceStatus = InvoiceStatus.DRAFT
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    subtotal: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    due_date: Optional[float] = None
    issued_at: Optional[float] = None
    paid_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BillingCycleInfo:
    """Billing cycle information"""
    cycle_id: str
    partner_id: str
    cycle_type: BillingCycle
    start_date: float
    end_date: float
    invoice_id: Optional[str] = None
    status: str = "active"


@dataclass
class Payment:
    """Payment record"""
    payment_id: str
    invoice_id: str
    partner_id: str
    amount: float
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    payment_method: str = ""
    transaction_id: Optional[str] = None
    processed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CreditNote:
    """Credit note for adjustments"""
    credit_note_id: str
    invoice_id: str
    partner_id: str
    amount: float
    reason: str
    currency: str = "USD"
    issued_at: float = field(default_factory=time.time)
    applied: bool = False


@dataclass
class TaxRate:
    """Tax rate for jurisdiction"""
    tax_rate_id: str
    jurisdiction: str
    rate: float
    tax_type: str = "vat"
    effective_from: float = field(default_factory=time.time)
    effective_until: Optional[float] = None


@dataclass
class BillingDispute:
    """Billing dispute record"""
    dispute_id: str
    invoice_id: str
    partner_id: str
    reason: str
    amount_in_dispute: float
    status: str = "open"
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolution: Optional[str] = None


class InvoiceEngine:
    """Generates invoices from usage data"""

    def __init__(self, usage_report_generator: 'UsageReportGenerator'):
        self.usage_report_generator = usage_report_generator
        self._invoices: Dict[str, Invoice] = {}
        self._counter = 0

    def create_invoice(self, partner_id: str, period_start: float,
                      period_end: float, due_days: int = 30) -> Invoice:
        """Create invoice from usage data"""
        # Generate usage report
        report = self.usage_report_generator.generate_report(
            partner_id, period_start, period_end
        )

        # Create line items
        line_items = []
        for api_name, breakdown in report.api_breakdown.items():
            line_items.append({
                "description": f"Usage - {api_name}",
                "api_name": api_name,
                "quantity": breakdown["total_calls"],
                "unit_price": breakdown["cost"] / breakdown["total_calls"] if breakdown["total_calls"] > 0 else 0,
                "amount": breakdown["cost"],
                "details": {
                    "total_duration_ms": breakdown.get("total_duration_ms", 0),
                    "total_size_bytes": breakdown.get("total_size_bytes", 0),
                    "success_count": breakdown.get("success_count", 0),
                    "error_count": breakdown.get("error_count", 0)
                }
            })

        # Calculate totals
        subtotal = report.total_cost
        tax_amount = 0.0  # Will be calculated by TaxCalculator
        total = subtotal + tax_amount

        # Create invoice
        invoice_id = self._generate_id("invoice")
        invoice = Invoice(
            invoice_id=invoice_id,
            partner_id=partner_id,
            cycle_id=f"cycle_{int(period_start)}_{int(period_end)}",
            period_start=period_start,
            period_end=period_end,
            status=InvoiceStatus.DRAFT,
            line_items=line_items,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=total,
            currency=report.currency,
            due_date=period_end + (due_days * 86400)
        )

        self._invoices[invoice_id] = invoice
        return invoice

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID"""
        return self._invoices.get(invoice_id)

    def list_invoices(self, partner_id: Optional[str] = None,
                     status: Optional[InvoiceStatus] = None) -> List[Invoice]:
        """List invoices with filters"""
        invoices = list(self._invoices.values())

        if partner_id:
            invoices = [inv for inv in invoices if inv.partner_id == partner_id]

        if status:
            invoices = [inv for inv in invoices if inv.status == status]

        # Sort by period start (newest first)
        invoices.sort(key=lambda inv: inv.period_start, reverse=True)

        return invoices

    def update_invoice(self, invoice_id: str, **kwargs) -> Invoice:
        """Update invoice"""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        for key, value in kwargs.items():
            if hasattr(invoice, key):
                setattr(invoice, key, value)

        return invoice

    def delete_invoice(self, invoice_id: str) -> bool:
        """Delete invoice (only draft invoices)"""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            return False

        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Cannot delete non-draft invoice")

        del self._invoices[invoice_id]
        return True

    def issue_invoice(self, invoice_id: str) -> Invoice:
        """Issue invoice"""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only issue draft invoices")

        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = time.time()

        return invoice

    def mark_paid(self, invoice_id: str) -> Invoice:
        """Mark invoice as paid"""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = time.time()

        return invoice

    def mark_overdue(self, invoice_id: str) -> Invoice:
        """Mark invoice as overdue"""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        if invoice.status == InvoiceStatus.ISSUED:
            invoice.status = InvoiceStatus.OVERDUE

        return invoice

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class BillingCycleManager:
    """Manages billing cycles (monthly, quarterly)"""

    def __init__(self, invoice_engine: InvoiceEngine):
        self.invoice_engine = invoice_engine
        self._cycles: Dict[str, BillingCycleInfo] = {}
        self._counter = 0

    def create_cycle(self, partner_id: str, cycle_type: BillingCycle,
                    start_date: Optional[float] = None) -> BillingCycleInfo:
        """Create a billing cycle"""
        start_date = start_date or time.time()
        end_date = self._calculate_end_date(start_date, cycle_type)

        cycle_id = self._generate_id("cycle")
        cycle = BillingCycleInfo(
            cycle_id=cycle_id,
            partner_id=partner_id,
            cycle_type=cycle_type,
            start_date=start_date,
            end_date=end_date
        )

        self._cycles[cycle_id] = cycle
        return cycle

    def get_cycle(self, cycle_id: str) -> Optional[BillingCycleInfo]:
        """Get cycle by ID"""
        return self._cycles.get(cycle_id)

    def get_active_cycles(self, partner_id: Optional[str] = None) -> List[BillingCycleInfo]:
        """Get active billing cycles"""
        cycles = list(self._cycles.values())

        if partner_id:
            cycles = [c for c in cycles if c.partner_id == partner_id]

        return [c for c in cycles if c.status == "active"]

    def generate_invoice_for_cycle(self, cycle_id: str) -> Invoice:
        """Generate invoice for billing cycle"""
        cycle = self.get_cycle(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle not found: {cycle_id}")

        if cycle.invoice_id:
            raise ValueError("Invoice already generated for this cycle")

        # Create invoice
        invoice = self.invoice_engine.create_invoice(
            partner_id=cycle.partner_id,
            period_start=cycle.start_date,
            period_end=cycle.end_date
        )

        # Link invoice to cycle
        cycle.invoice_id = invoice.invoice_id
        cycle.status = "invoiced"

        return invoice

    def _calculate_end_date(self, start_date: float, cycle_type: BillingCycle) -> float:
        """Calculate end date for cycle"""
        if cycle_type == BillingCycle.MONTHLY:
            # Add ~30 days
            return start_date + (30 * 86400)
        elif cycle_type == BillingCycle.QUARTERLY:
            # Add ~90 days
            return start_date + (90 * 86400)
        elif cycle_type == BillingCycle.ANNUALLY:
            # Add ~365 days
            return start_date + (365 * 86400)
        else:
            # Default to 30 days
            return start_date + (30 * 86400)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class PaymentProcessor:
    """Simulates payment processing"""

    def __init__(self, invoice_engine: InvoiceEngine):
        self.invoice_engine = invoice_engine
        self._payments: Dict[str, Payment] = {}
        self._counter = 0

    def create_payment(self, invoice_id: str, amount: float,
                      payment_method: str = "credit_card") -> Payment:
        """Create a payment"""
        invoice = self.invoice_engine.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        payment_id = self._generate_id("payment")
        payment = Payment(
            payment_id=payment_id,
            invoice_id=invoice_id,
            partner_id=invoice.partner_id,
            amount=amount,
            currency=invoice.currency,
            status=PaymentStatus.PENDING,
            payment_method=payment_method
        )

        self._payments[payment_id] = payment
        return payment

    def process_payment(self, payment_id: str) -> Payment:
        """Process a payment (simulated)"""
        payment = self._payments.get(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")

        # Simulate processing
        payment.status = PaymentStatus.PROCESSING

        # Simulate success (in production, would call actual payment gateway)
        import random
        if random.random() > 0.1:  # 90% success rate
            payment.status = PaymentStatus.COMPLETED
            payment.processed_at = time.time()
            payment.transaction_id = f"txn_{int(time.time() * 1000)}"

            # Mark invoice as paid
            invoice = self.invoice_engine.get_invoice(payment.invoice_id)
            if invoice:
                self.invoice_engine.mark_paid(payment.invoice_id)
        else:
            payment.status = PaymentStatus.FAILED

        return payment

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get payment by ID"""
        return self._payments.get(payment_id)

    def get_payments_for_invoice(self, invoice_id: str) -> List[Payment]:
        """Get all payments for an invoice"""
        return [p for p in self._payments.values() if p.invoice_id == invoice_id]

    def get_payments_for_partner(self, partner_id: str) -> List[Payment]:
        """Get all payments for a partner"""
        return [p for p in self._payments.values() if p.partner_id == partner_id]

    def refund_payment(self, payment_id: str, reason: str = "") -> Payment:
        """Refund a payment"""
        payment = self._payments.get(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")

        if payment.status != PaymentStatus.COMPLETED:
            raise ValueError("Can only refund completed payments")

        payment.status = PaymentStatus.REFUNDED

        # Mark invoice as issued again (not paid)
        invoice = self.invoice_engine.get_invoice(payment.invoice_id)
        if invoice:
            invoice.status = InvoiceStatus.ISSUED
            invoice.paid_at = None

        return payment

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class CreditNoteManager:
    """Manages credit notes and adjustments"""

    def __init__(self, invoice_engine: InvoiceEngine):
        self.invoice_engine = invoice_engine
        self._credit_notes: Dict[str, CreditNote] = {}
        self._counter = 0

    def create_credit_note(self, invoice_id: str, amount: float,
                          reason: str) -> CreditNote:
        """Create a credit note"""
        invoice = self.invoice_engine.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        credit_note_id = self._generate_id("credit")
        credit_note = CreditNote(
            credit_note_id=credit_note_id,
            invoice_id=invoice_id,
            partner_id=invoice.partner_id,
            amount=amount,
            reason=reason
        )

        self._credit_notes[credit_note_id] = credit_note
        return credit_note

    def get_credit_note(self, credit_note_id: str) -> Optional[CreditNote]:
        """Get credit note by ID"""
        return self._credit_notes.get(credit_note_id)

    def apply_credit_note(self, credit_note_id: str) -> CreditNote:
        """Apply credit note to invoice"""
        credit_note = self.get_credit_note(credit_note_id)
        if not credit_note:
            raise ValueError(f"Credit note not found: {credit_note_id}")

        if credit_note.applied:
            raise ValueError("Credit note already applied")

        # Update invoice
        invoice = self.invoice_engine.get_invoice(credit_note.invoice_id)
        if invoice:
            invoice.total -= credit_note.amount
            credit_note.applied = True

        return credit_note

    def get_credit_notes_for_invoice(self, invoice_id: str) -> List[CreditNote]:
        """Get all credit notes for an invoice"""
        return [cn for cn in self._credit_notes.values() if cn.invoice_id == invoice_id]

    def get_credit_notes_for_partner(self, partner_id: str) -> List[CreditNote]:
        """Get all credit notes for a partner"""
        return [cn for cn in self._credit_notes.values() if cn.partner_id == partner_id]

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class TaxCalculator:
    """Calculates taxes per jurisdiction"""

    def __init__(self):
        self._tax_rates: Dict[str, TaxRate] = {}
        self._counter = 0

    def create_tax_rate(self, jurisdiction: str, rate: float,
                       tax_type: str = "vat",
                       effective_from: Optional[float] = None,
                       effective_until: Optional[float] = None) -> TaxRate:
        """Create a tax rate"""
        tax_rate_id = self._generate_id("tax")
        tax_rate = TaxRate(
            tax_rate_id=tax_rate_id,
            jurisdiction=jurisdiction,
            rate=rate,
            tax_type=tax_type,
            effective_from=effective_from or time.time(),
            effective_until=effective_until
        )

        self._tax_rates[tax_rate_id] = tax_rate
        return tax_rate

    def calculate_tax(self, amount: float, jurisdiction: str,
                     tax_type: str = "vat") -> float:
        """Calculate tax for amount in jurisdiction"""
        current_time = time.time()

        # Find applicable tax rate
        tax_rate = None
        for tr in self._tax_rates.values():
            if (tr.jurisdiction == jurisdiction and
                tr.tax_type == tax_type and
                tr.effective_from <= current_time and
                (tr.effective_until is None or tr.effective_until > current_time)):
                tax_rate = tr
                break

        if not tax_rate:
            return 0.0

        return amount * (tax_rate.rate / 100)

    def get_tax_rate(self, tax_rate_id: str) -> Optional[TaxRate]:
        """Get tax rate by ID"""
        return self._tax_rates.get(tax_rate_id)

    def list_tax_rates(self, jurisdiction: Optional[str] = None) -> List[TaxRate]:
        """List tax rates"""
        tax_rates = list(self._tax_rates.values())

        if jurisdiction:
            tax_rates = [tr for tr in tax_rates if tr.jurisdiction == jurisdiction]

        return tax_rates

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"


class BillingDisputeManager:
    """Handles billing disputes"""

    def __init__(self, invoice_engine: InvoiceEngine):
        self.invoice_engine = invoice_engine
        self._disputes: Dict[str, BillingDispute] = {}
        self._counter = 0

    def create_dispute(self, invoice_id: str, partner_id: str,
                      reason: str, amount_in_dispute: float) -> BillingDispute:
        """Create a billing dispute"""
        invoice = self.invoice_engine.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        dispute_id = self._generate_id("dispute")
        dispute = BillingDispute(
            dispute_id=dispute_id,
            invoice_id=invoice_id,
            partner_id=partner_id,
            reason=reason,
            amount_in_dispute=amount_in_dispute
        )

        self._disputes[dispute_id] = dispute

        # Mark invoice as disputed
        invoice.status = InvoiceStatus.DISPUTED

        return dispute

    def resolve_dispute(self, dispute_id: str, resolution: str) -> BillingDispute:
        """Resolve a billing dispute"""
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")

        dispute.status = "resolved"
        dispute.resolved_at = time.time()
        dispute.resolution = resolution

        # Mark invoice back to issued
        invoice = self.invoice_engine.get_invoice(dispute.invoice_id)
        if invoice:
            invoice.status = InvoiceStatus.ISSUED

        return dispute

    def get_dispute(self, dispute_id: str) -> Optional[BillingDispute]:
        """Get dispute by ID"""
        return self._disputes.get(dispute_id)

    def get_disputes_for_invoice(self, invoice_id: str) -> List[BillingDispute]:
        """Get disputes for an invoice"""
        return [d for d in self._disputes.values() if d.invoice_id == invoice_id]

    def get_disputes_for_partner(self, partner_id: str) -> List[BillingDispute]:
        """Get disputes for a partner"""
        return [d for d in self._disputes.values() if d.partner_id == partner_id]

    def get_open_disputes(self) -> List[BillingDispute]:
        """Get all open disputes"""
        return [d for d in self._disputes.values() if d.status == "open"]

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        self._counter += 1
        return f"{prefix}_{int(time.time() * 1000)}_{self._counter}"
