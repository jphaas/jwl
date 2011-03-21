"""
In memory database that stores each type as a entry in a hash table
"""

from parse import QueryParser
from Language.corelanguage import GT, LT, LTE, GTE, NE, EQ, KINDS, PropertyStatement, exists, not_exists, is_listed
from Utils.multimethods import getNamespace
mm = getNamespace()
from Language.bake import generate_metas

class HashDB(object):
    
    def __init__(self, language):
        self.objects = {} #contains type, value keys and points to property dicts
        self.types = {} #contains type keys and points to lists of object values
        self.parser = QueryParser(self._typeset, self._getv, self._remove_all, self._replace, self._remove, self._add, self._list, self._unlist)
        self.metas = generate_metas(language)
        
    def query(self, query):
        return self.parser.query(query)
        
    def querydata(self,query):
        return self.parser.querydata(query)
        
    def _typeset(self, typename):
        def gettypeset():
            if not self.types.has_key(typename):
                return []
            return list(self.types[typename])
        return gettypeset
        
    def _getv(self, set, typename, property):
        def dogetv():
            values = set()
            newvalues = []
            for v in values:
                newvalues.extend(self.dolookup(v, typename, property))
            return newvalues
        return dogetv
    
    def dolookup(self, value, typename, property):
        if property == "is_listed":
            if not typename in self.types:
                return [False]
            elif value in self.types[typename]:
                return [True]
            else:
                return [False]
        elif not self.objects.has_key((typename, value)):
            vlist = []
        else:
            properties = self.objects[(typename, value)]
            if not properties.has_key(property):
                vlist = []
            else:
                vlist = properties[property]
        self.parser.add_data(exists(value, typename, property, vlist))
        return vlist
    
    def _replace(self, value, type, property, newvalues): #implement replace as a remove_all followed by an add -- not the MOST efficient, but reliable, and given that this is in-memory its probably not too bad
        self._remove_all(value, type, property)
        for v in newvalues:
            self._add(value, type, property, v)
    
    def _remove_all(self, value, type, property):
        if not self.objects.has_key((type, value)):
            return None
        properties = self.objects[(type, value)]
        if properties.has_key(property):
            for v in list(properties[property]):
                self._remove(value, type, property, v)
    
    def _remove_half(self, value, type, property, target):
        if not self.objects.has_key((type, value)):
            return None
        properties = self.objects[(type, value)]
        if properties.has_key(property) and target in properties[property]:
            properties[property].remove(target)
            self.parser.add_data(exists(value, type, property, properties[property]))
    
    def _remove(self, value, type, property, target):
        self._remove_half(value, type, property, target)
        prop = self.metas[type][property]
        if prop.b.kind in (KINDS.SINGLE, KINDS.PLURAL):
            self._remove_half(target, prop.b.typename, prop.b.name, value)
    
    def _initobj(self, type, value):
        self.objects[(type, value)] = {}
    
    def _add_half(self, value, type, property, target):
        if not self.objects.has_key((type, value)):
            self._initobj(type, value)
        properties = self.objects[(type, value)]
        if not properties.has_key(property):
            properties[property] = []
        if target not in properties[property]:
            properties[property].append(target)
        self.parser.add_data(exists(value, type, property, properties[property]))
    
    def _add(self, value, type, property, target):
        self._add_half(value, type, property, target)
        prop = self.metas[type][property]
        if prop.b.kind in (KINDS.SINGLE, KINDS.PLURAL):
            self._add_half(target, prop.b.typename, prop.b.name, value)
        
    def _list(self, value, type):
        if not type in self.types:
            self.types[type] = []
        self.types[type].append(value)
        self.parser.add_data(is_listed(value, type, True))
        
    def _unlist(self, value, type):
        if type in self.types:
            self.types[type].remove(value)
        self.parser.add_data(is_listed(value, type, False))