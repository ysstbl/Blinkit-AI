from app.clients.postgres_client import fetch_all, fetch_one


def search_by_embedding(vector: list[float], limit: int = 100):
    return fetch_all(
        """
        SELECT sku_id, name, price, in_stock, pack_size, category
        FROM grocery_catalog
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """,
        (vector, limit),
    )


def find_price_extreme(order: str, filter_terms: list[str]):
    conditions = ["in_stock = TRUE", "price IS NOT NULL"]
    parameters = []
    for term in filter_terms:
        conditions.append("(name ILIKE %s OR category ILIKE %s)")
        wildcard = f"%{term}%"
        parameters.extend([wildcard, wildcard])

    statement = f"""
        SELECT name, price, pack_size
        FROM grocery_catalog
        WHERE {' AND '.join(conditions)}
        ORDER BY price {order}
        LIMIT 1;
    """
    return fetch_one(statement, parameters)
