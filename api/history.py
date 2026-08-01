from fastapi import APIRouter, Query, HTTPException
from firebase.firebase_client import get_all_invoices, get_invoice

router = APIRouter()

EXPOSED_FIELDS = {
    "invoice_number",
    "supplier",
    "gstin",
    "taxable_value",
    "total_amount",
    "compliance_status",
    "issues",
    "processed_at",
    "file_path"
}

def filter_invoice_fields(invoice: dict) -> dict:
    """
    Filters the invoice dictionary to only expose the recommended fields,
    excluding internal Firestore metadata.
    """
    return {k: v for k, v in invoice.items() if k in EXPOSED_FIELDS}


@router.get("/history")
async def get_history(
    status: str = Query(None, description="Filter by compliance status (e.g. compliant, non_compliant)"),
    supplier: str = Query(None, description="Filter by supplier name"),
    limit: int = Query(None, description="Limit the number of returned invoices")
):
    """
    GET /history
    Retrieves all historically processed invoices stored in Firestore,
    ordered by processed_at descending (newest first).
    Supports optional status, supplier, and limit filtering.
    """
    try:
        # Retrieve all invoices sorted by processed_at descending
        all_invoices = get_all_invoices()
        
        filtered = []
        for inv in all_invoices:
            # 1. Filter by compliance status if provided (case-insensitive check)
            if status:
                inv_status = str(inv.get("compliance_status") or "").strip().lower()
                if status.strip().lower() != inv_status:
                    continue
                    
            # 2. Filter by supplier if provided (case-insensitive partial match)
            if supplier:
                inv_supplier = str(inv.get("supplier") or "").strip().lower()
                if supplier.strip().lower() not in inv_supplier:
                    continue
                    
            # Keep only the exposed fields
            filtered.append(filter_invoice_fields(inv))
            
        # 3. Apply limit if provided
        if limit is not None and limit > 0:
            filtered = filtered[:limit]
            
        return {
            "success": True,
            "count": len(filtered),
            "invoices": filtered
        }
        
    except Exception as e:
        print(f"Error in GET /history endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching invoice history: {str(e)}"
        )


@router.get("/history/{invoice_number}")
async def get_single_invoice(invoice_number: str):
    """
    GET /history/{invoice_number}
    Retrieves a single processed invoice metadata document by invoice number.
    Returns 404 if the document does not exist.
    """
    try:
        invoice = get_invoice(invoice_number)
        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail=f"Invoice with number '{invoice_number}' not found."
            )
            
        return {
            "success": True,
            "invoice": invoice
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in GET /history/{invoice_number} endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching invoice details: {str(e)}"
        )
