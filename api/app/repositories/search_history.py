from app.models.search_history import SearchHistory
from app.repositories.base import BaseRepository


class SearchHistoryRepository(BaseRepository[SearchHistory]):
    model = SearchHistory
