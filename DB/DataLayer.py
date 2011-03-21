from __future__ import absolute_import
"""Sets up and returns an instatiated query language based on the language and DB engine of choice"""

from ..Language.bake import LanguageInstance
from .. import deployconfig

class DBLayer:
    def __init__(self, LD):
        self._db = deployconfig.get('dbengine')(LD)
        self._ld = LD
        self.LI = LanguageInstance(LD, self._db)