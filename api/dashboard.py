from fastapi import APIRouter, HTTPException
from services.dashboard_service import calculate_dashboard_analytics

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard():
    """
    GET /dashboard
    Aggregates invoice data from Firestore (or the local backup DB fallback)
    and returns a summary of GST totals, compliance statuses, supplier stats, and trends.
    """
    try:
        analytics = calculate_dashboard_analytics()
        return analytics
    except Exception as e:
        print(f"Error in GET /dashboard endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while compiling the dashboard analytics: {str(e)}"
        )
