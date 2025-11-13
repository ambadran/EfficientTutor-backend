'''
API endpoint for retrieving role-based financial summaries.
'''
from typing import Annotated, Any, Union
from fastapi import APIRouter, Depends

from ..database import models as db_models
from ..models import finance as finance_models
from ..services.security import verify_token_and_get_user
from ..services.finance_service import FinancialSummaryService

# Define a union type for role-based financial summary responses
FinancialSummaryRoleBased = Union[
    finance_models.FinancialSummaryForTeacher,
    finance_models.FinancialSummaryForParent,
]

class FinancialSummariesAPI:
    """
    A class to encapsulate the endpoint for Financial Summaries.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/financial-summary",
            tags=["Financial Summary"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        self.router.add_api_route("/", self.get_financial_summary, methods=["GET"], response_model=FinancialSummaryRoleBased)

    async def get_financial_summary(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        summary_service: Annotated[FinancialSummaryService, Depends(FinancialSummaryService)]
    ) -> Any:
        """
        Retrieves a financial summary for the current user.
        - For a Teacher, shows total owed, credit held, and lessons given.
        - For a Parent, shows total due, credit balance, and unpaid lesson count.
        """
        return await summary_service.get_financial_summary_for_api(current_user)

# Instantiate the class and export its router
financial_summaries_api = FinancialSummariesAPI()
router = financial_summaries_api.router
