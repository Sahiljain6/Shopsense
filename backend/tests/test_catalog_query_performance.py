from sqlalchemy import event

from app.models.entities import Category, Product
from app.services.catalog import CatalogService


def _seed_catalog(db_session, count: int = 12) -> list[Product]:
    category = Category(name="Phones")
    db_session.add(category)
    db_session.flush()
    products = [
        Product(
            name=f"ShopSense Test Phone {index}",
            brand="TestBrand",
            description="smartphone for query-count testing",
            price=10000 + index,
            rating=4.0 + (index / 100),
            stock=10,
            image_url="",
            attributes={},
            category_id=category.id,
        )
        for index in range(count)
    ]
    db_session.add_all(products)
    db_session.commit()
    for product in products:
        db_session.refresh(product)
    return products


def _count_selects(db_session, callback):
    statements = []

    def before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        result = callback()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return result, len(statements)


def test_catalog_search_loads_categories_in_bounded_queries(db_session):
    _seed_catalog(db_session)

    products, query_count = _count_selects(
        db_session,
        lambda: CatalogService(db_session).search(None, limit=20),
    )
    category_names = [product.category.name for product in products]

    assert len(products) == 12
    assert all(name == "Phones" for name in category_names)
    # One query for products and one select-in query for their shared category.
    assert query_count <= 2


def test_catalog_get_many_does_not_issue_one_category_query_per_product(db_session):
    seeded = _seed_catalog(db_session)
    product_ids = [product.id for product in seeded]

    products, query_count = _count_selects(
        db_session,
        lambda: CatalogService(db_session).get_many(product_ids),
    )
    category_names = [product.category.name for product in products]

    assert len(products) == len(product_ids)
    assert all(name == "Phones" for name in category_names)
    assert query_count <= 2


def test_filtered_product_search_keeps_query_count_constant_with_more_results(db_session):
    _seed_catalog(db_session, count=10)

    products, query_count = _count_selects(
        db_session,
        lambda: CatalogService(db_session).search("phones under 20000", limit=20),
    )
    assert len(products) == 10
    assert all(product.category.name == "Phones" for product in products)
    # Category lookup + product rows + select-in category fetch; not O(products).
    assert query_count <= 3
