from abc import ABC, abstractmethod


class StockProviderError(Exception):
    pass


class BaseStockProvider(ABC):

    @property
    @abstractmethod
    def name(self):

        raise NotImplementedError


    @abstractmethod
    def search_videos(
        self,
        query,
        per_page=10
    ):

        raise NotImplementedError


    @abstractmethod
    def search_images(
        self,
        query,
        per_page=10
    ):

        raise NotImplementedError