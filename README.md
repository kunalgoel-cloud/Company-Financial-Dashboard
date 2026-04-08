# Finance Command Centre

A unified Streamlit finance dashboard combining Inventory, P&L, Working Capital, Receivables, and Supplier Performance into one app — driven by a single set of CSV uploads.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## File Structure

```
finance_dashboard/
├── app.py               # Entry point + CSS + page router
├── state.py             # Session state management & data store
├── sidebar.py           # Navigation + all CSV uploads + Item Master
├── requirements.txt
└── tabs/
    ├── __init__.py
    ├── overview.py      # Landing page with cross-tab KPI summary
    ├── inventory.py     # Inventory snapshots, ageing, shelf life
    ├── pnl.py           # P&L: Revenue → COGS → Logistics → CM1/CM2
    ├── working_capital.py  # DSO · DIO · DPO · Cash Cycle
    ├── receivables.py   # FIFO reconciled aging by customer
    └── supplier.py      # Weighted lead time · fill rate · PO status
```

## CSV Upload Guide

### Invoice CSV (drives: P&L, Receivables, Working Capital DSO)
Required columns:
- `Invoice Number`, `Invoice Date`, `Customer Name`
- `SKU`, `Item Name`, `Quantity`, `Item Price`, `Item Total`
- `Balance`, `Invoice Status`, `Place of Supply` (state code e.g. MH, DL)
- `GST Treatment` (business_gst for B2B filtering in Receivables)

### WMS / Inventory CSV (drives: Inventory, Working Capital DIO)
Required columns:
- `Title` or `SKU` — product name/code
- `Total Stock` or `Qty` — quantity on hand
- `Mfg Date` — manufacturing date (DD/MM/YYYY)
- `Shelf Life` — remaining shelf life % (e.g. "85%")
- `Channel` — B2B or B2C (optional)
- `Value` — inventory value (optional; calculated from Item Master if absent)

### Customer Balance Summary (drives: Receivables reconciliation, WC DSO)
Required columns:
- `customer_name`, `closing_balance`
- `invoiced_amount` or `invoiced` (for DSO calculation)
- `amount_received` (optional, for CEI)

### Purchase Order CSV (drives: Supplier Performance, WC DPO)
Required columns:
- `Purchase Order Number`, `Purchase Order Date`
- `Vendor Name`, `Item Name`
- `QuantityOrdered`, `Item Total`

### Bill Header CSV (drives: Supplier Performance)
Required columns:
- `Bill#` or `Bill Number`, `Date`, `Vendor Name`
- `Reference Number` (PO number this bill relates to)
- `Amount`

### Bill Lines CSV (drives: Supplier Performance)
Required columns:
- `Bill Number`, `Bill Date`, `Vendor Name`
- `Item Name`, `Quantity`, `Item Total`

## Item Master
Add SKU → COGS mappings via the sidebar to unlock:
- Inventory valuation
- P&L gross margin
- Working Capital DIO

Items auto-populate from Invoice CSV uploads; you just need to set the COGS values.
