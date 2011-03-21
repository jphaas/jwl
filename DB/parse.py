from __future__ import absolute_import

"""
Contains functions for traversing a query.
"""
from ..utils.multimethods import getNamespace
try:
    from threading import current_thread
except: #no threading on GAE
    current_thread = lambda: None
mm = getNamespace()
from ..Language.corelanguage import GetV, Node, GetSet, ValueSet, TypeSet, Filter, Compare, RemoveAll, Replace, Remove, Add, LimitFilter, List, Unlist
from ..Language.corelanguage import GT, LT, LTE, GTE, NE, EQ, KINDS, PropertyStatement

class QueryParser(object):
    
    def __init__(self, typeset, getv, remove_all, replace, remove, add, list, unlist): 
        """
        As used below, a set is a func on () -> [values].

        typeset(typename) -> set 
        getv(set, typename, property) -> set
              
        remove_all(value, type, property)
        replace(value, type, property, newvalues)
        remove(value, type, property, value)
        add(value, type, property, value)
        list(value, type)
        unlist(value, type)
        """
        self.typeset = typeset
        self.getv = getv
        
        self.remove_all = remove_all
        self.replace = replace
        self.remove = remove
        self.add = add
        self.list = list
        self.unlist = unlist
        self.data_dict = {}
        
    def add_data(self, data_piece):
        self.data_dict[current_thread()].append(data_piece)
        
    def start_data(self):
        self.data_dict[current_thread()] = []
        
    def end_data(self):
        del self.data_dict[current_thread()]
    
    def get_data(self):
        return tuple(self.data_dict[current_thread()])
        
    def query(self, query):
        return self.querydata(query)[0]
    
    def querydata(self, query):
        self.start_data()
        try:
            set = self._get_base(query.values)()
            r = self.execute_query(query, set)
            return r, self.get_data()
        finally:
            self.end_data()
        
    @mm(object, GetSet, object)
    def execute_query(self, command, set):
        return set
    
    @mm(object, RemoveAll, object)
    def execute_query(self, command, set):
        for v in set:
            self.remove_all(v, command.type, command.property)
            
    @mm(object, Replace, object)
    def execute_query(self, command, set):
        for v in set:
            self.replace(v, command.type, command.property, command.newvalues)
    
    @mm(object, Remove, object)
    def execute_query(self, command, set):
        for v in set:
            self.remove(v, command.type, command.property, command.value)
            
    @mm(object, Add, object)
    def execute_query(self, command, set):
        for v in set:
            self.add(v, command.type, command.property, command.value)
            
    @mm(object, List, object)
    def execute_query(self, command, set):
        for v in set:
            self.list(v, command.type)

    @mm(object, Unlist, object)
    def execute_query(self, command, set):
        for v in set:
            self.unlist(v, command.type)
        
    def _get_base(self, querybase):
        """returns a set (a func on () -> values)"""
        if querybase == ():
            raise Exception('query terminated prematurely -- must start with a ValueSet, TypeSet, or similar')
        return self._parse(querybase[-1], querybase[:-1])
        
    @mm(object, ValueSet, tuple)
    def _parse(self, node, base): #all instances of parse return a set (a func on () -> values)
        if base != ():
            raise Exception('Error: nothing should precede ValueSets')
        def ret():
            v = node.values
            if isinstance(v, list):
                return v
            elif isinstance(v, tuple):
                return list(v)
            else:
                return [v]
        return ret
        
    @mm(object, TypeSet, tuple)
    def _parse(self, node, base):
        if base != ():
            raise Exception('Error: nothing should precede TypeSets')
        return self.typeset(node.type)
    
    @mm(object, GetV, tuple)
    def _parse(self, node, base):
        return self.getv(self._get_base(base), node.type, node.property)
        
    def defaultFilter(self, node, base):
        def getset():
            newvalues = self._get_base(base)()
            for filter in node.filters:
                if isinstance(filter[0], LimitFilter):
                    if len(filter) > 1:
                        raise Exception('LimitFilters must be the only term in a filter sequence')
                    newvalues = newvalues[filter[0].offset : filter[0].offset + filter[0].number]
                else:
                    nv = []
                    for v in newvalues:
                        if self._get_base((ValueSet(v),) + filter):
                            nv.append(v)
                    newvalues = nv
            return newvalues
        return getset
        
    @mm(object, Filter, tuple)
    def _parse(self, node, base):
        return self.defaultFilter(node, base)
    
    @mm(object, Compare, tuple)
    def _parse(self, node, base):
        return self.defaultCompare(self._get_base(base)(), node)
        
    @mm(object, LimitFilter, tuple)
    def _parse(self, node, base):
        raise Exception('LimitFilters can only appear as the first (and only) term in a filter sequence')
        
    def defaultCompare(self, values, compare_node):
        for v in values: #find at least one value that passes
            if self.docompare(compare_node, v): 
                return True
        return False
        
    @mm(object, GT, object)
    def docompare(self, compare, value):
        return value > compare.value
    
    @mm(object, LT, object)
    def docompare(self, compare, value):
        return value < compare.value
    
    @mm(object, LTE, object)
    def docompare(self, compare, value):
        return value <= compare.value
    
    @mm(object, GTE, object)
    def docompare(self, compare, value):
        return value >= compare.value
    
    @mm(object, EQ, object)
    def docompare(self, compare, value):
        return value == compare.value
    
    @mm(object, NE, object)
    def docompare(self, compare, value):
        return value != compare.value