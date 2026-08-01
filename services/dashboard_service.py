from datetime import datetime
from collections import Counter
from firebase.firebase_client import get_all_invoices

def parse_processed_at(timestamp) -> datetime | None:
    """
    Safely parses various timestamp formats into a Python datetime object.
    """
    if not timestamp:
        return None
    if isinstance(timestamp, datetime):
        return timestamp
        
    try:
        t_str = str(timestamp).strip()
        if t_str.endswith("Z"):
            t_str = t_str[:-1]
            
        # Try standard ISO formats
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(t_str, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return None


def calculate_dashboard_analytics() -> dict:
    """
    Reads all invoice documents from Firestore/local DB once
    and calculates all dashboard metrics in memory.
    """
    invoices = get_all_invoices()
    
    total_invoices = len(invoices)
    
    # Initialize variables
    processed_today = 0
    processed_this_week = 0
    processed_this_month = 0
    
    compliant_count = 0
    non_compliant_count = 0
    
    total_taxable_value = 0.0
    total_cgst = 0.0
    total_sgst = 0.0
    total_igst = 0.0
    total_invoice_value = 0.0
    
    supplier_stats = {} # supplier_name -> {"invoice_count": 0, "total_invoice_value": 0.0}
    
    # Get current local date for comparison
    now = datetime.now()
    now_year, now_week, now_weekday = now.isocalendar()
    now_month = now.month
    now_day = now.day
    
    newest_invoice = None
    
    for inv in invoices:
        # Newest invoice is the first one in the list because get_all_invoices sorts newest first
        if newest_invoice is None:
            newest_invoice = inv
            
        # 1. Compliance status count
        status = str(inv.get("compliance_status") or "").strip().lower()
        if status in ("compliant", "compliant"):
            compliant_count += 1
        else:
            non_compliant_count += 1
            
        # 2. Financial sums
        taxable = float(inv.get("taxable_value") or 0.0)
        cgst = float(inv.get("cgst") or 0.0)
        sgst = float(inv.get("sgst") or 0.0)
        igst = float(inv.get("igst") or 0.0) # Check for IGST
        total_amount = float(inv.get("total_amount") or 0.0)
        
        total_taxable_value += taxable
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_invoice_value += total_amount
        
        # 3. Supplier stats
        supplier_name = str(inv.get("supplier") or "UNKNOWN").strip()
        if supplier_name not in supplier_stats:
            supplier_stats[supplier_name] = {"supplier": supplier_name, "invoice_count": 0, "total_invoice_value": 0.0}
        supplier_stats[supplier_name]["invoice_count"] += 1
        supplier_stats[supplier_name]["total_invoice_value"] += total_amount
        
        # 4. Processing trends (today, week, month)
        proc_time = parse_processed_at(inv.get("processed_at"))
        if proc_time:
            # Check if today
            if proc_time.year == now.year and proc_time.month == now_month and proc_time.day == now_day:
                processed_today += 1
                
            # Check if this week
            inv_year, inv_week, _ = proc_time.isocalendar()
            if inv_year == now_year and inv_week == now_week:
                processed_this_week += 1
                
            # Check if this month
            if proc_time.year == now.year and proc_time.month == now_month:
                processed_this_month += 1
                
    # Calculate averages and percentages
    compliance_percentage = round((compliant_count / total_invoices * 100), 2) if total_invoices > 0 else 0.0
    average_invoice_value = round((total_invoice_value / total_invoices), 2) if total_invoices > 0 else 0.0
    
    # Calculate top supplier
    top_supplier = ""
    top_supplier_invoice_count = 0
    if supplier_stats:
        top_supplier_data = max(supplier_stats.values(), key=lambda x: x["invoice_count"])
        top_supplier = top_supplier_data["supplier"]
        top_supplier_invoice_count = top_supplier_data["invoice_count"]
        
    # Get latest processed details
    last_processed = ""
    latest_invoice_num = ""
    if newest_invoice:
        last_processed = newest_invoice.get("processed_at") or ""
        latest_invoice_num = newest_invoice.get("invoice_number") or ""
        
    # Build supplier breakdown list sorted by count descending
    supplier_breakdown = sorted(supplier_stats.values(), key=lambda x: x["invoice_count"], reverse=True)
    
    return {
        "success": True,
        "summary": {
            "total_invoices": total_invoices,
            "processed_today": processed_today,
            "processed_this_week": processed_this_week,
            "processed_this_month": processed_this_month,
            "compliant": compliant_count,
            "non_compliant": non_compliant_count,
            "compliance_percentage": compliance_percentage,
            "total_taxable_value": round(total_taxable_value, 2),
            "total_cgst": round(total_cgst, 2),
            "total_sgst": round(total_sgst, 2),
            "total_gst": round(total_cgst + total_sgst + total_igst, 2),
            "total_invoice_value": round(total_invoice_value, 2),
            "average_invoice_value": average_invoice_value,
            "top_supplier": top_supplier,
            "top_supplier_invoice_count": top_supplier_invoice_count,
            "last_processed": last_processed,
            "latest_invoice": latest_invoice_num
        },
        "supplier_breakdown": supplier_breakdown,
        "gst_distribution": {
            "cgst": round(total_cgst, 2),
            "sgst": round(total_sgst, 2),
            "igst": round(total_igst, 2)
        }
    }
