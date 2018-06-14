from abc import ABC, abstractmethod

from .imagecollection import ImageCollection

"""
openeo.sessions
~~~~~~~~~~~~~~~~
This module provides a Session object to manage and persist settings when interacting with the OpenEO API.
"""


class Session(ABC):
    """
    A `Session` class represents a connection with an OpenEO service. It is your entry point to create new Image Collections.
    """

    @property
    @abstractmethod
    def auth(self, username, password, auth) -> bool:
        pass

    @abstractmethod
    def list_collections(self) -> dict:
        """
        Retrieve all products available in the backend.
        :return: a dict containing product information. The 'product_id' corresponds to an image collection id.
        """
        pass

    @abstractmethod
    def imagecollection(self, image_collection_id:str) -> ImageCollection:
        """
        Retrieves an Image Collection object based on the id of a given layer.
        A list of available collections can be retrieved with :meth:`openeo.sessions.Session.list_collections`.

        :param image_collection_id: The id of the image collection to retrieve.

        :rtype: openeo.imagecollection.ImageCollection
        """
        pass

