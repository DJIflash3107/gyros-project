import math
from typing import Tuple, Any
from sqlalchemy.orm import Query


def paginate_query(query: Query, page: int, page_size: int) -> Tuple[list[Any], dict]:
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    pagination = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return items, pagination
