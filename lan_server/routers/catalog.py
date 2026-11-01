"""Router katalog: produk, kategori, unit, supplier."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import POSException
from app.models import Category, Product, Supplier, Unit
from app.services.master_data_service import MasterDataService
from lan_server.deps import get_current_user, get_db, require_roles
from lan_server.schemas import (
    CategoryCreate,
    CategoryOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockAdjustRequest,
    SupplierOut,
    UnitCreate,
    UnitOut,
)
from lan_server.serializers import serialize_product

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=list[ProductOut])
def list_products(
    search: str = Query(default="", max_length=200),
    include_inactive: bool = Query(default=False),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductOut]:
    statement = select(Product).where(Product.deleted_at.is_(None))
    if not include_inactive:
        statement = statement.where(Product.is_active.is_(True))
    term = search.strip()
    if term:
        like = f"%{term}%"
        statement = statement.where(
            Product.name.ilike(like)
            | Product.sku.ilike(like)
            | Product.barcode.ilike(like)
        )
    statement = statement.order_by(Product.name, Product.sku)
    return [serialize_product(product) for product in db.scalars(statement)]


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Produk tidak ditemukan."
        )
    return serialize_product(product)


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> ProductOut:
    service = MasterDataService(db)
    try:
        data = payload.model_dump()
        # Bila klien tidak mengirim kategori/satuan, pakai baseline yang sudah
        # ada atau buat "Umum"/"Pcs" supaya instalasi baru tidak buntu.
        if not data.get("category_id"):
            data["category_id"] = service.ensure_default_category(user).id
        if not data.get("unit_id"):
            data["unit_id"] = service.ensure_default_unit(user).id
        product = service.save_product(
            user,
            product_id=None,
            **data,
        )
        db.commit()
        db.refresh(product)
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return serialize_product(product)


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> ProductOut:
    service = MasterDataService(db)
    data = payload.model_dump()
    data.pop("product_id", None)
    try:
        product = service.save_product(user, product_id=product_id, **data)
        db.commit()
        db.refresh(product)
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return serialize_product(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> None:
    service = MasterDataService(db)
    try:
        service.delete_product(user, product_id)
        db.commit()
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/products/stock", response_model=ProductOut)
def adjust_stock(
    payload: StockAdjustRequest,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> ProductOut:
    """Penyesuaian stok tercatat sebagai StockMovement, bukan update diam-diam."""
    service = MasterDataService(db)
    try:
        product = service.add_stock(user, payload.product_id, payload.quantity)
        db.commit()
        db.refresh(product)
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return serialize_product(product)


@router.get("/products/{product_id}/price", response_model=dict)
def product_price(
    product_id: int,
    qty: int = Query(default=1, ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Harga satuan efektif untuk qty tertentu.

    Harga grosir/diskon bertingkat dihitung server memakai
    `BulkPricingService` yang sama dengan kasir desktop, supaya tampilan
    keranjang di klien LAN tidak pernah berbeda dari harga saat checkout.
    """
    from app.services.bulk_pricing_service import BulkPricingService

    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Produk tidak ditemukan."
        )
    pricing = BulkPricingService(db)
    rule = pricing.rule_for_product(product.id)
    return {
        "product_id": product.id,
        "qty": qty,
        "unit_price": pricing.unit_price(product, qty),
        "regular_price": product.selling_price,
        "has_rule": rule is not None,
        "rule_threshold": rule.quantity_threshold if rule is not None else None,
        "special_price": (
            pricing.effective_special_price(product, rule) if rule is not None else None
        ),
    }


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CategoryOut]:
    statement = (
        select(Category)
        .where(Category.deleted_at.is_(None))
        .order_by(Category.name)
    )
    return [
        CategoryOut(id=row.id, name=row.name) for row in db.scalars(statement)
    ]


@router.post(
    "/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED
)
def create_category(
    payload: CategoryCreate,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> CategoryOut:
    service = MasterDataService(db)
    try:
        category = service.create_category(user, payload.name)
        db.commit()
        db.refresh(category)
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return CategoryOut(id=category.id, name=category.name)


@router.get("/units", response_model=list[UnitOut])
def list_units(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UnitOut]:
    statement = select(Unit).where(Unit.deleted_at.is_(None)).order_by(Unit.name)
    return [
        UnitOut(id=row.id, name=row.name, symbol=row.symbol)
        for row in db.scalars(statement)
    ]


@router.post("/units", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def create_unit(
    payload: UnitCreate,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> UnitOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nama satuan wajib diisi."
        )
    existing = db.scalar(
        select(Unit).where(Unit.name == name, Unit.deleted_at.is_(None))
    )
    if existing is not None:
        return UnitOut(id=existing.id, name=existing.name, symbol=existing.symbol)
    unit = Unit(name=name, symbol=(payload.symbol or name).strip())
    db.add(unit)
    try:
        db.commit()
        db.refresh(unit)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Satuan sudah digunakan."
        ) from exc
    return UnitOut(id=unit.id, name=unit.name, symbol=unit.symbol)


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SupplierOut]:
    statement = (
        select(Supplier)
        .where(Supplier.deleted_at.is_(None))
        .order_by(Supplier.name)
    )
    return [
        SupplierOut(
            id=row.id,
            code=row.code,
            name=row.name,
            phone=row.phone,
            address=row.address,
        )
        for row in db.scalars(statement)
    ]
