"""Sets up and returns an instatiated query language based on the language and DB engine of choice"""

import ..Language.bake
import deployconfig
import logging

class DBLayer:
    def __init__(self, LD):
        self._db = deployconfig.get('dbengine')(LD)
        self._ld = LD
        self.LI = Language.bake.LanguageInstance(LD, self._db)