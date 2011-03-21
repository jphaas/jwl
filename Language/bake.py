"""
Contains functions for instantiating a data language definition into a set of objects,
that when manipulated, generate query language
"""
from UserDict import DictMixin
from corelanguage import TypeStatement, PropertyStatement, PropertyDefinition, KINDS, LiteralStatement, ValidatorStatement, TypeSet, FlagStatement
from corelanguage import GetV, ValueSet, Filter, QueryNode, LimitFilter
from corelanguage import GT, LT, GTE, LTE, EQ, NE
from corelanguage import GetSet, Add, Remove, RemoveAll, List, Unlist, Replace
import traceback
import sys

_reserved = ['typename', 'parents', 'walk', 'validators', 'validate', 'search', 'meta', 'type_', 'is_listed_', 'is_listed', 'value_', 'value', 'eval', 'subclass_of', 'keys', 'delete', 'add', 'remove', 'replace', 'filter', 'getFilter', 'namelist']

class meta(DictMixin):
    """Represents a type including its attribute search tree"""
    def __init__(self, typename, parents = None, dict = None, validators = None):
        self.typename = typename
        self.parents = parents
        self.flags = {}
        if dict is None:
            dict = {}
        self._dict = dict
        if validators is None:
            validators = []
        self._validators = validators
    def walk(self):
        """Yields first itself and then each of its parents"""
        yield self
        for p in self.parents:
            for m in p.walk():
                yield m
    def validators(self):
        for m in self.walk():
            for v in m._validators:
                yield v
    def validate(self, value):
        """Tries to validate value; returns a tuple (passed-validation, error-message-if-any)"""
        for v in reversed(list(self.validators())):
            result, message = v(value)
            if not result:
                return False, message
        return True, ''
    def search(self, name):
        """takes a attribute-name, and returns a tuple (defining-type, attribute-value)"""
        if name == "is_listed": #special processing for this
            return (self.typename, PropertyStatement(PropertyDefinition(self.typename, KINDS.SINGLE, 'is_listed'), PropertyDefinition('boolean', KINDS.NONE, '')))
        for m in self.walk():
            for n, v in m._dict.iteritems():
                if name == n:
                    return (m.typename, v)
        if name in self.flags:
            return (self.typename, self.flags[name])
        raise AttributeError('could not find attribute ' + repr(name) + ' in type ' + repr(self.typename))
    def keys(self):
        for m in self.walk():
            for n, v in m._dict.iteritems():
                yield n
    def __getitem__(self, name):
        try:
            return self.search(name)[1]
        except AttributeError, e:
            raise KeyError(e.message)
    def __getattr__(self, name):
        return self.search(name)[1]
    def subclass_of(self, other):
        for m in self.walk():
            if m.typename == other.typename:
                return True
        return False
        
        
class AttributeClashError(Exception):
    pass
        
def generate_metas(ddl):
    """
    Takes a ddl, defined in terms of a list of statements, and outputs a dictionary of "metas" which are essentially
    the search-tree for each type
    """
    metas = {}
    alter = []
    addp = []
    for statement in ddl:
        if isinstance(statement, TypeStatement):
            metas[statement.name] = meta(statement.name)
            addp.append(statement)
        else:
            alter.append(statement)
    for statement in addp:
        metas[statement.name].parents = [metas[pname] for pname in statement.parents]
    for statement in alter:
        if isinstance(statement, PropertyStatement):
            _add_property(statement.a, statement.b, metas)
            _add_property(statement.b, statement.a, metas)
        elif isinstance(statement, LiteralStatement):
            _add_to_dict(metas[statement.typename], statement.name, statement.literal)
        elif isinstance(statement, FlagStatement):
            metas[statement.typename].flags[statement.name] = statement.value
        elif isinstance(statement, ValidatorStatement):
            metas[statement.typename]._validators.append(statement.validator)
    return metas
    
def _add_property(a, b, metas): #used by generate_metas
    if a.kind != KINDS.NONE and a.kind != KINDS.REFLECT:
        if b.kind == KINDS.REFLECT:
            _add_to_dict(metas[a.typename], a.name, PropertyStatement(a, a))
        else:  
            _add_to_dict(metas[a.typename], a.name, PropertyStatement(a, b))
    
def _add_to_dict(meta, name, value): #used by generate-metas
    if meta._dict.has_key(name):
        raise AttributeClashError('type ' + meta.typename + ' already defines attribute ' + name)
    if name in _reserved or name.find('_') == 0:
        raise AttributeClashError('name ' + name + ' is a reserved word and cannot be used as an attribute')
    meta._dict[name] = value
      
class Query(object):
    """
    The object-oriented query language.
    
    Each instance of the query object represents an un-executed query.
    
    .value - executes the query and returns the object raw value (if the query ought to return a single object) or iterable of values
    .eval - executes the query and returns the query-wrapped-value (if the query ought to return a single object) or iterable of query-wrapped-value
    
    ['name'] or .name -- gets the return value of the attribute:
        1. if the attribute is a property, returns a new query
        2. if the attribute is a literal function, calls .eval on the current query, and returns a function
            that calls the function on the output: if current query returns a single item, will call it on that item,
            if it returns a set of items, calls it on each member of the set and returns an iterator over the return values
        3. if the attribute is a literal, but not callable, just returns the literal
    
    #list(), unlist -- "listing" a value means that searches against all values of a given type will return it.
    Listing / unlisting is a very weak form of create / delete: it has no effect on anything but Type()... searches
    and listing a value is not a prerequisite for using it.
    
    add(value) - when used on an object's property, adds the value to the set represented by the property.  Throws
    an error if used on a non-property attribute, if used on a Query that was not derived from a property-attribute,
    or on a SINGLE property that is not equal to None
    
    remove
    replace
    assignment (=)
    
    __call__

    == - true if two query objects have the same value and are the same type or one is a parent type of the other
    
    """
    def __init__(self, language_instance, single, current, meta, parent = None, myproperty = None):
        self.meta = meta
        self._single = single
        self._language_instance = language_instance
        
        
        if current is None:
            current = (TypeSet(meta.typename),)
        self._current = current
        if not self._is_q():
            tovalidate = self._current
            if not isinstance(self._current, (list, tuple)):
                tovalidate = [self._current]
            for tov in tovalidate:
                v, m = meta.validate(tov)
                if not v:
                    raise TypeError('Validation error for ' + meta.typename + ': ' + m)
        self._parent = parent
        self._myproperty = myproperty
    
    def _is_q(self):
        return type(self._current) in (tuple, list) and isinstance(self._current[0], QueryNode)
            
    def _current_q(self):
        if self._is_q():
            return self._current
        return (ValueSet(self._current),)
    
    def __eq__(self, other):
        return isinstance(other, Query) and (self.meta.subclass_of(other.meta) or other.meta.subclass_of(self.meta)) and self.value == other.value
        
    def __ne__(self, other):
        return not (isinstance(other, Query) and (self.meta.subclass_of(other.meta) or other.meta.subclass_of(self.meta)) and self.value == other.value)
        
    def _get_value(self):
        try:
            if not self._is_q():
                return self._current
            evaled = self.eval
            if self._single:
                return evaled._get_value()
            else:
                return (v._get_value() for v in evaled)
        except AttributeError, e: #because if this throws an attribute error, it gets sent to get_attr...
            traceback.print_exc(file=sys.stdout)
            raise Exception('attribute error: ' + e.message)
            
    def _get_eval(self):
        try:
            if not self._is_q():
                return self
            return self._language_instance.execute(GetSet(self._current_q()), self.meta.typename, self._single)
        except AttributeError, e: #because if this throws an attribute error, it gets sent to get_attr...
            traceback.print_exc(file=sys.stdout)
            raise Exception('attribute error: ' + e.message)
        
    value = property(_get_value)
    
    eval = property(_get_eval)
        
    def __getattr__(self, name):
        if name != "is_listed" and (name in _reserved or name.find('_') == 0):
            raise AttributeError('could not find ' + name)
        attribute = self.meta.__getattr__(name)
        return self._process_attribute(attribute)
        
    def list(self):
        self._language_instance.execute(List(self._current_q(), self.meta.typename), None)

    def unlist(self):
        self._language_instance.execute(Unlist(self._current_q(), self.meta.typename), None)
        
    def _validate_value(self, value):
        if not isinstance(value, Query):
            value = Query(self._language_instance, True, value, self.meta)
        if not value.meta.subclass_of(self.meta):
            raise TypeError('expecting type ' + self.meta.typename + ' but got type ' + value.meta.typename)
        return value
        
    def add(self, value):
        parent = self._parent
        myproperty = self._myproperty
        if myproperty == None:
            raise Exception('cannot add in this context!  Query must be a property')
        value = self._validate_value(value)
        if self._single:
            if len(list(self._language_instance.execute(GetSet(self._current_q()), self.meta.typename))) > 0:
                raise ValueError('Cannot add more than 1 to a single relationship!!!')
        self._language_instance.execute(Add(parent._current_q(), parent.meta.search(myproperty)[0], myproperty, value.value), None)
        
    def remove(self, value):
        parent = self._parent
        myproperty = self._myproperty
        if myproperty == None:
            raise Exception('cannot add in this context!  Query must be a property')
        value = self._validate_value(value)
        self._language_instance.execute(Remove(parent._current_q(), parent.meta.search(myproperty)[0], myproperty, value.value), None)
        
    def replace(self, value):
        parent = self._parent
        myproperty = self._myproperty
        if myproperty == None:
            raise Exception('cannot add in this context!  Query must be a property')
            
        if self._single:
            if hasattr(value, '__iter__'):
                raise ValueError('cannot pass in an iterable: expecting a single value')
            values = [self._validate_value(value).value]
        else:
            if not hasattr(value, '__iter__'):
                raise ValueError('expecting an iterable, not a single value')
            values = [self._validate_value(v).value for v in value]
                        
        self._language_instance.execute(Replace(parent._current_q(), parent.meta.search(myproperty)[0], myproperty, values), None)
    
    def __setattr__(self, name, value):
        if name in _reserved or name.find('_') == 0:
            object.__setattr__(self, name, value)
        else:
            attribute = self.__getattr__(name)
            if isinstance(attribute, Query):
                return attribute.replace(value)
            else:
                raise TypeError('cannot call replace on a non-query object')
            
    def __call__(self, *filters):
        if self._single:
            raise Exception('You cannot filter a query that only returns single values')
        newcurrent = self._current_q() + (Filter(tuple(f.getFilter(self. _language_instance._metas, self.meta.typename) for f in filters)),)
        
        return Query(self._language_instance, False, newcurrent, self.meta)
    
    def __iter__(self):
        raise Exception('this class is not iterable!  if you want to iterate through the attributes, try .meta')
    
    def __getitem__(self, name):
        attribute = self.meta[name]
        return self._process_attribute(attribute)
        
    def _process_attribute(self, attribute):
        if isinstance(attribute, PropertyStatement): #attribute is a property
            newcurrent = self._current_q() + (GetV(self.meta.search(attribute.a.name)[0], attribute.a.name),)
            single = self._single and attribute.a.kind == KINDS.SINGLE
            return Query(self._language_instance, single, newcurrent, self._language_instance.get_meta(attribute.b.typename), self, attribute.a.name)
        elif callable(attribute): #attribute is a literal function
            if self._single:
                def r1(*a1, **a2):
                    return attribute(self.eval, *a1, **a2)
                return r1
            else:
                def r2(*a1, **a2):
                    return (attribute(query, *a1, **a2) for query in self.eval)
                return r2
        else: #attribute is a non-callable literal, which means it is basically a constant, so just return it
            return attribute
      
class NoneQuery(object):
    """Represents a query object that returned None"""
    def _get_value(self):
        return None
    def _get_eval(self):
        return None
    value = property(_get_value)
    eval = property(_get_eval)
    
class _PropertyGenerator(object):
    """syntactic sugar for generating property types"""
    def __init__(self, namelist = [], filter = None):
        self.namelist = namelist
        self.filter = filter
    def __getattr__(self, name):
        return _PropertyGenerator(self.namelist + [name])
    def getFilter(self, metas, first_type):
        result = []
        type = first_type
        for name in self.namelist:
            result.append(GetV(metas[type].search(name)[0], name))
            type = metas[type].search(name)[1].b.typename
        result.append(self.filter)
        return tuple(result)
    def _f(self, filter):
        return _PropertyGenerator(self.namelist, filter)
    def __eq__(self, other):
        return self._f(EQ(other)) 
    def __ne__(self, other):
        return self._f(NE(other)) 
    def __lt__(self, other):
        return self._f(LT(other)) 
    def __le__(self, other):
        return self._f(LTE(other))
    def __gt__(self, other):
        return self._f(GT(other))
    def __ge__(self, other):
        return self._f(GTE(other))
    #CONSIDER ADDING SOME STRING OPERATIONS AS WELL
    #CONSIDER ADDING EXTENDED REFERENCE SYNTAX (A.B.C etc.)
        
prop = _PropertyGenerator()

class limit(object):
    """for easy creation of limit filters"""
    def __init__(self, number, offset):
        self.filter = (LimitFilter(number, offset),)
    def getFilter(self, metas, first_type):
        return self.filter

class LanguageInstance(object):
    def __init__(self, language, datasource):
        self.datasource = datasource
        self._metas = generate_metas(language)
        self.funcs = {}
        self.add_functions_to_namespace(self.funcs)
                  
    def get_meta(self, typename):
        return self._metas[typename]
               
    def add_functions_to_namespace(self, namespace):
        for typename, meta in self._metas.iteritems():
            def om(meta):
                def mk(value=None):
                    return Query(self, value is not None, value, meta)
                return mk
            namespace[typename] = om(meta)
                  
    def execute(self, query, typename, single = False):
        if typename is not None:
            type = self.get_meta(typename)
            if single:
                for value in self.datasource.query(query):
                    return Query(self, True, value, type)
                return NoneQuery()
            return (Query(self, True, value, type) for value in self.datasource.query(query))
        else:
            self.datasource.query(query)