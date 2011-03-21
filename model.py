from __future__ import absolute_import
from .Language import corelanguage
from .Language.coretypes import core_types
from .Language.corelanguage import SINGLE, PLURAL, NONE, REFLECT
from .Language.corelanguage import PropertyStatement, SINGLE, PLURAL, NONE, REFLECT
from .Language.bake import prop

def new_language(scope = {}):
    Lang = []
    Lang.extend(core_types)
    scope['newtype'] = corelanguage.newtype(Lang)
    scope['setprop'] = corelanguage.setprop(Lang)
    scope['setliteral'] = corelanguage.setliteral(Lang)
    scope['setvalidator'] = corelanguage.setvalidator(Lang)
    scope['setflag'] = corelanguage.setflag(Lang)
    return Lang