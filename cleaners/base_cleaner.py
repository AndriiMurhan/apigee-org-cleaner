from abc import ABC, abstractmethod
from helpers.api_helper import APIHelper
from utils.logger import Logger
from request import RestRequest


class BaseCleaner(ABC):
    def __init__(self, hierarchy: dict, main_url: str):
        self.hierarchy = hierarchy
        self.main_url = main_url
        self.api_helper = APIHelper()
        self.logger = Logger(self.__class__.__name__)
        self.request = RestRequest()
    
    @abstractmethod
    def delete(self):
        pass