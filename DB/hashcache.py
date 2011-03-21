"""
In memory cache that stores each item as a hash
"""

from parse import QueryParser
from Language.corelanguage import GT, LT, LTE, GTE, NE, EQ, KINDS, PropertyStatement, GetSet, ValueSet, exists, not_exists, GetV, TypeSet, is_listed
from Utils.multimethods import getNamespace
mm = getNamespace()
from Language.bake import generate_metas
import logging
logger = logging.getLogger('DB.hashcache')

class HashCache(object):
    
    def __init__(self, language, underlying):
        self.objects = {} #contains type, value keys and points to property dicts
        #self.types = {} #contains type keys and points to lists of object values
        self.parser = QueryParser(self._typeset, self._getv, self._remove_all, self._replace, self._remove, self._add, self._list, self._unlist)
        self.metas = generate_metas(language)
        self.underlying = underlying
        self.cachemiss = 0
        self.cachehit = 0
        
    def _insert_data(self, data):
        for d in data:
            if isinstance(d, exists):
                if not (d.type, d.value) in self.objects:
                    self.objects[(d.type, d.value)] = {}
                properties = self.objects[(d.type, d.value)]
                properties[d.property] = d.target
            elif isinstance(d, not_exists):
                if (d.type, d.value) in self.objects:
                    properties = self.objects[(d.type, d.value)]
                    if d.property in properties:
                        del properties[d.property]
            elif isinstance(d, is_listed):
                pass
            else:
                raise Exception('unrecognized data element: ' + repr(type(d)))
        
    def query(self, query):
        search = query.values[0]
        if isinstance(search, ValueSet): #handle value-driven look ups
            if isinstance(query, GetSet):  #GetSets we handle
                return self.parser.query(query)
            else: #modifications we pass to underlying and just read in the result
                results, data = self.underlying.querydata(query)
                self._insert_data(data)
                return results
        elif isinstance(search, TypeSet): #pass Type-driven look ups to underlying
            logger.info('cachemiss on %s', query)
            self.cachemiss += 1
            results, data = self.underlying.querydata(query)
            self._insert_data(data)
            return results
        else:
            raise Exception('query started with an unrecognized type ' + repr(type(query[0])))
        
    def querydata(self,query):
        raise Exception('this class does not support data mode -- not meant to sit under a cache')
        
    def _typeset(self, typename):
        raise Exception('Should never hit this code since this class does not try to parse queries that start with typeset')
        
    def _list(self, value, type):
        raise Exception('should never hit this -- this class passes writes to underlying')
        
    def _unlist(self, value, type):
        raise Exception('should never hit this -- this class passes writes to underlying')
        
    def _getv(self, set, typename, property):
        def dogetv():
            values = set()
            newvalues = []
            for v in values:
                newvalues.extend(self.dolookup(v, typename, property))
            return newvalues
        return dogetv 
    
    def dolookup(self, value, typename, property):
        if not self.objects.has_key((typename, value)) or not property in self.objects[(typename, value)]: #CACHE MISS -- SEND TO UNDERLYING!!
            q = GetSet((ValueSet(value), GetV(typename, property)))
            logger.info('cache miss on %s', q)
            self.cachemiss += 1
            vlist, data = self.underlying.querydata(q)
            self._insert_data(data)
        else:
            logger.info('cache hit')
            self.cachehit += 1
            properties = self.objects[(typename, value)]
            vlist = properties[property]
        return vlist
    
    def _replace(self, value, type, property):
        raise Exception('should never hit this -- this class passes writes to underlying')
    
    def _remove_all(self, value, type, property):
        raise Exception('should never hit this -- this class passes writes to underlying')
      
    def _remove(self, value, type, property, target):
        raise Exception('should never hit this -- this class passes writes to underlying')
      
    def _add(self, value, type, property, target):
        raise Exception('should never hit this -- this class passes writes to underlying')