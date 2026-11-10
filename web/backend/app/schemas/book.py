from typing import Optional, List
from pydantic import BaseModel

class Book(BaseModel):
    id: int
    goodreads_id: Optional[int] = None
    title: str
    author_name: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    isbn: Optional[str] = None
    isbn13: Optional[str] = None
    published_year: Optional[int] = None
    pages: Optional[int] = None
    language: str = "en"
    rating: float = 0
    ratings_count: int = 0
    publisher: Optional[str] = None
    tags: List[str] = []
    trending_rank: Optional[int] = None
    price: float = 0

class PaginatedBooks(BaseModel):
    data: List[Book]
    total: int
    page: int
    limit: int
    pages: int

class SampleReview(BaseModel):
    review_id: str
    user_id: int
    rating: int
    review_text: Optional[str] = None
    date_added: Optional[str] = None

class BatchBookRequest(BaseModel):
    ids: List[int]

class CategoryItem(BaseModel):
    name: str
    count: int

class StatsResponse(BaseModel):
    total_books: int
    total_category_tags: int
    avg_rating: float

