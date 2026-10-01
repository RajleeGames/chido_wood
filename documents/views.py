from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from xhtml2pdf import pisa

from .forms import (
    DocumentForm,
    DocumentItemFormSet,
)
from .models import (
    BusinessProfile,
    Document,
)


PRINT_EMPTY_ROWS = 6


# ================================================================
# VALID DOCUMENT TYPES
# ================================================================

VALID_DOCUMENT_TYPES = {
    Document.DocumentType.INVOICE,
    Document.DocumentType.PROFORMA_INVOICE,
    Document.DocumentType.DELIVERY_NOTE,
}


# ================================================================
# BUSINESS INFORMATION
# ================================================================

def business_context():
    business = (
        BusinessProfile.get_solo()
    )

    bank_accounts = list(
        business.bank_accounts
        .filter(
            is_active=True
        )
        .order_by(
            "sort_order",
            "pk",
        )[:2]
    )

    return (
        business,
        bank_accounts,
    )


# ================================================================
# COMMON DOCUMENT CONTEXT
# ================================================================

def build_document_context(
    document,
):
    business, bank_accounts = (
        business_context()
    )

    items = list(
        document.items.all()
    )

    return {
        "document": document,
        "business": business,
        "bank_accounts": bank_accounts,
        "items": items,

        # Keep the same document look currently used in the repo.
        "blank_rows": range(
            PRINT_EMPTY_ROWS
        ),
    }


# ================================================================
# DOCUMENT LIST
# ================================================================

@login_required
def document_list(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    type_filter = request.GET.get(
        "type",
        "",
    ).strip()

    documents = (
        Document.objects
        .select_related(
            "created_by"
        )
        .all()
    )

    if query:
        documents = documents.filter(
            Q(
                document_number__icontains=query
            )
            | Q(
                customer_name__icontains=query
            )
            | Q(
                customer_phone__icontains=query
            )
            | Q(
                subject__icontains=query
            )
        )

    if type_filter in VALID_DOCUMENT_TYPES:
        documents = documents.filter(
            document_type=type_filter
        )

    return render(
        request,
        "documents/document_list.html",
        {
            "documents": documents,
            "query": query,
            "document_type": type_filter,
            "page_title": (
                "Invoices, Proformas & Delivery Notes"
            ),
        },
    )


# ================================================================
# CREATE DOCUMENT
# ================================================================

@login_required
@transaction.atomic
def document_create(request):

    requested_type = (
        request.GET.get(
            "type",
            "",
        ).strip()
    )

    if (
        requested_type
        not in VALID_DOCUMENT_TYPES
    ):
        requested_type = (
            Document.DocumentType.INVOICE
        )

    document = Document(
        created_by=request.user,
        date=timezone.localdate(),
        document_type=requested_type,
    )

    if request.method == "POST":

        form = DocumentForm(
            request.POST,
            instance=document,
        )

        formset = DocumentItemFormSet(
            request.POST,
            instance=document,
            prefix="items",
        )

        if (
            form.is_valid()
            and formset.is_valid()
        ):
            document = form.save(
                commit=False
            )

            document.created_by = (
                request.user
            )

            document.document_number = (
                Document
                .allocate_document_number(
                    document.document_type
                )
            )

            document.save()

            formset.instance = document
            formset.save()

            # Rebuild clean item ordering.
            for index, item in enumerate(
                document.items.all(),
                start=1,
            ):
                if (
                    item.sort_order
                    != index
                ):
                    item.sort_order = index

                    item.save(
                        update_fields=[
                            "sort_order",
                        ]
                    )

            messages.success(
                request,
                (
                    f"{document.get_document_type_display()} "
                    f"{document.display_document_number} "
                    f"saved."
                ),
            )

            return redirect(
                "document-preview",
                pk=document.pk,
            )

    else:
        form = DocumentForm(
            instance=document,
        )

        formset = DocumentItemFormSet(
            instance=document,
            prefix="items",
        )

    return render(
        request,
        "documents/document_form.html",
        {
            "form": form,
            "formset": formset,
            "document": document,
            "page_title": (
                "Create document"
            ),
        },
    )


# ================================================================
# EDIT DOCUMENT
# ================================================================

@login_required
@transaction.atomic
def document_edit(
    request,
    pk,
):
    document = get_object_or_404(
        Document,
        pk=pk,
    )

    if request.method == "POST":

        form = DocumentForm(
            request.POST,
            instance=document,
        )

        formset = DocumentItemFormSet(
            request.POST,
            instance=document,
            prefix="items",
        )

        if (
            form.is_valid()
            and formset.is_valid()
        ):
            form.save()
            formset.save()

            for index, item in enumerate(
                document.items.all(),
                start=1,
            ):
                if (
                    item.sort_order
                    != index
                ):
                    item.sort_order = index

                    item.save(
                        update_fields=[
                            "sort_order",
                        ]
                    )

            messages.success(
                request,
                "Document updated.",
            )

            return redirect(
                "document-preview",
                pk=document.pk,
            )

    else:
        form = DocumentForm(
            instance=document,
        )

        formset = DocumentItemFormSet(
            instance=document,
            prefix="items",
        )

    return render(
        request,
        "documents/document_form.html",
        {
            "form": form,
            "formset": formset,
            "document": document,
            "page_title": (
                f"Edit "
                f"{document.get_document_type_display()} "
                f"{document.display_document_number}"
            ),
        },
    )


# ================================================================
# PREVIEW DOCUMENT
# ================================================================

@login_required
def document_preview(
    request,
    pk,
):
    document = get_object_or_404(
        Document.objects.prefetch_related(
            "items"
        ),
        pk=pk,
    )

    context = (
        build_document_context(
            document
        )
    )

    context.update(
        {
            "share_url": (
                request.build_absolute_uri(
                    reverse(
                        "document-public-pdf",
                        kwargs={
                            "token": (
                                document.share_token
                            )
                        },
                    )
                )
            ),

            "page_title": (
                f"{document.get_document_type_display()} "
                f"{document.display_document_number}"
            ),
        }
    )

    return render(
        request,
        "documents/document_preview.html",
        context,
    )


# ================================================================
# XHTML2PDF STATIC / MEDIA FILE RESOLUTION
# ================================================================

def link_callback(
    uri,
    rel,
):
    parsed = urlparse(
        uri
    )

    path = (
        parsed.path
        or uri
    )

    # ------------------------------------------------------------
    # MEDIA FILES
    # ------------------------------------------------------------

    if path.startswith(
        settings.MEDIA_URL
    ):
        relative = path[
            len(
                settings.MEDIA_URL
            ):
        ]

        absolute = (
            Path(
                settings.MEDIA_ROOT
            )
            / relative
        )

        return str(
            absolute
        )

    # ------------------------------------------------------------
    # STATIC FILES
    # ------------------------------------------------------------

    if path.startswith(
        settings.STATIC_URL
    ):
        relative = path[
            len(
                settings.STATIC_URL
            ):
        ]

        for directory in getattr(
            settings,
            "STATICFILES_DIRS",
            [],
        ):
            candidate = (
                Path(
                    directory
                )
                / relative
            )

            if candidate.exists():
                return str(
                    candidate
                )

        static_root = getattr(
            settings,
            "STATIC_ROOT",
            None,
        )

        if static_root:
            candidate = (
                Path(
                    static_root
                )
                / relative
            )

            if candidate.exists():
                return str(
                    candidate
                )

    return uri


# ================================================================
# RENDER PDF
# ================================================================

def render_pdf(
    document,
):
    context = (
        build_document_context(
            document
        )
    )

    html = get_template(
        "documents/document_pdf.html"
    ).render(
        context
    )

    output = BytesIO()

    result = pisa.CreatePDF(
        src=html,
        dest=output,
        link_callback=link_callback,
        encoding="utf-8",
    )

    if result.err:
        raise RuntimeError(
            "Could not generate PDF."
        )

    return output.getvalue()


# ================================================================
# AUTHENTICATED PDF DOWNLOAD
# ================================================================

@login_required
def document_pdf(
    request,
    pk,
):
    document = get_object_or_404(
        Document.objects.prefetch_related(
            "items"
        ),
        pk=pk,
    )

    try:
        pdf = render_pdf(
            document
        )

    except Exception as exc:
        return HttpResponse(
            (
                "PDF generation failed: "
                f"{exc}"
            ),
            status=500,
            content_type=(
                "text/plain"
            ),
        )

    filename_type = (
        document.document_type
        .replace(
            "_",
            "-",
        )
    )

    filename = (
        f"{filename_type}-"
        f"{document.display_document_number}.pdf"
    ).replace(
        "/",
        "-",
    )

    response = HttpResponse(
        pdf,
        content_type=(
            "application/pdf"
        ),
    )

    response[
        "Content-Disposition"
    ] = (
        f'attachment; filename="{filename}"'
    )

    return response


# ================================================================
# PUBLIC SHARE PDF
# ================================================================

def public_document_pdf(
    request,
    token,
):
    document = get_object_or_404(
        Document.objects.prefetch_related(
            "items"
        ),
        share_token=token,
    )

    try:
        pdf = render_pdf(
            document
        )

    except Exception:
        raise Http404(
            "Document could not be generated."
        )

    filename_type = (
        document.document_type
        .replace(
            "_",
            "-",
        )
    )

    filename = (
        f"{filename_type}-"
        f"{document.display_document_number}.pdf"
    ).replace(
        "/",
        "-",
    )

    response = HttpResponse(
        pdf,
        content_type=(
            "application/pdf"
        ),
    )

    response[
        "Content-Disposition"
    ] = (
        f'inline; filename="{filename}"'
    )

    response[
        "Cache-Control"
    ] = (
        "private, max-age=300"
    )

    return response


# ================================================================
# DELETE DOCUMENT
# ================================================================

@login_required
@require_POST
def document_delete(
    request,
    pk,
):
    document = get_object_or_404(
        Document,
        pk=pk,
    )

    document.delete()

    messages.success(
        request,
        "Document deleted.",
    )

    return redirect(
        "document-list"
    )