from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import (
    get_object_or_404,
    redirect,
)
from django.views.decorators.http import require_POST

from .models import Sale
from .void_services import void_completed_sale


@login_required
@require_POST
def sale_void(request, pk):
    sale = get_object_or_404(
        Sale,
        pk=pk,
    )

    try:
        void_completed_sale(
            sale_id=sale.pk,
            user=request.user,
            reason=request.POST.get(
                "void_reason",
                "",
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    else:
        messages.success(
            request,
            (
                f"Sale {sale.sale_number} was "
                "voided successfully. The FIFO "
                "stock used by the sale was restored."
            ),
        )

    return redirect(
        "sale-detail",
        pk=sale.pk,
    )
