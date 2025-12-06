'''
API endpoints for managing Payment Logs.
'''
from typing import Annotated, Any
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query

from ..database import models as db_models
from ..models import finance as finance_models
from ..services.security import verify_token_and_get_user
from ..services.finance_service import PaymentLogService

class PaymentLogsAPI:
    """
    A class to encapsulate endpoints for Payment Logs.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/payment-logs",
            tags=["Payment Logs"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        self.router.add_api_route(
                "/", 
                self.list_payment_logs, 
                methods=["GET"], 
                response_model=list[finance_models.PaymentLogRead])
        self.router.add_api_route(
                "/{log_id}", 
                self.get_payment_log, 
                methods=["GET"], 
                response_model=finance_models.PaymentLogRead)
        self.router.add_api_route(
                "/", 
                self.create_payment_log, 
                methods=["POST"], 
                status_code=status.HTTP_201_CREATED, 
                response_model=finance_models.PaymentLogRead)
        self.router.add_api_route(
                "/{log_id}/void", 
                self.void_payment_log, 
                methods=["PATCH"])
        self.router.add_api_route(
                "/{log_id}/correction", 
                self.correct_payment_log, 
                methods=["POST"], 
                response_model=finance_models.PaymentLogRead)

    async def list_payment_logs(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        payment_log_service: Annotated[PaymentLogService, Depends(PaymentLogService)],
        parent_id: Annotated[UUID | None, Query(description="Optional filter for Parent ID")] = None,
        teacher_id: Annotated[UUID | None, Query(description="Optional filter for Teacher ID")] = None
    ) -> list[Any]:
        """
        Retrieves a list of all payment logs relevant to the current user.
        """
        return await payment_log_service.get_all_payment_logs_for_api(
            current_user,
            parent_id=parent_id,
            teacher_id=teacher_id
        )

    async def get_payment_log(
        self,
        log_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        payment_log_service: Annotated[PaymentLogService, Depends(PaymentLogService)]
    ) -> Any:
        """
        Retrieves a single payment log by its ID.
        """
        return await payment_log_service.get_payment_log_by_id_for_api(log_id, current_user)

    async def create_payment_log(
        self,
        log_data: finance_models.PaymentLogCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        payment_log_service: Annotated[PaymentLogService, Depends(PaymentLogService)]
    ) -> Any:
        """
        Creates a new payment log. Restricted to Teachers only.
        """
        return await payment_log_service.create_payment_log(log_data.model_dump(), current_user)

    async def void_payment_log(
        self,
        log_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        payment_log_service: Annotated[PaymentLogService, Depends(PaymentLogService)]
    ):
        """
        Voids a specific payment log. Restricted to the owning Teacher.
        """
        await payment_log_service.void_payment_log(log_id, current_user)
        return {"message": "Payment log voided successfully."}

    async def correct_payment_log(
        self,
        log_id: UUID,
        correction_data: finance_models.PaymentLogCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        payment_log_service: Annotated[PaymentLogService, Depends(PaymentLogService)]
    ) -> Any:
        """
        Corrects a payment log by voiding the old one and creating a new one.
        Restricted to the owning Teacher.
        """
        return await payment_log_service.correct_payment_log(log_id, correction_data.model_dump(), current_user)

# Instantiate the class and export its router
payment_logs_api = PaymentLogsAPI()
router = payment_logs_api.router
