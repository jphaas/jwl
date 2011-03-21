"""
Uses google's datastore
"""

###
### POTENTIAL IMPROVEMENTS: CONSIDER USING TRICKLE-UP SEMANTICS FOR ADDING PROPERTIES,
### SUCH THAT IF I ADD IT TO PERSON, IT ALSO GETS ADDED TO STUDENT TO ENABLE SEARCHES (CONSEQUENCES OF THIS, THOUGH?)
###
### ANOTHER THING: WHAT HAPPENS WHEN THERE'S JUST ONE LIST ITEM: HOW DOES GOOGLE KNOW IT IS A LIST?
### FINALLY, IT IS DANGEROUS TO FILTER ON LISTS BECAUSE INDEXES CAN GROW REALLY FAST, SHOULD WE DE-GOOGLE IT?
###
### Currently, limit tests don't actually test the datastore's limit, they test the code version.
###
### Currently, we're only retrieving data on reads... should we retrieve data when we fetch an object on write?
###
### Pros / cons in terms of reliability from switching from DBObject to type stores for each individual class?  Might help the single list problems
###
### COonsider using a cursor hidden behind the offset semantics



from parse import QueryParser
from Language.corelanguage import GT, LT, LTE, GTE, NE, EQ, KINDS, PropertyStatement, exists, not_exists, is_listed, Compare, LimitFilter, GetV, Filter
from Utils.multimethods import getNamespace
mm = getNamespace()
from Language.bake import generate_metas
from google.appengine.ext import db
import logging

logger = logging.Logger('DB.googledb')

class DBObject(db.Expando):
    type_ = db.StringProperty(required=True)
    
@mm(EQ)
def get_op(op):
    return '='

@mm(GT)
def get_op(op):
    return '>'

@mm(LT)
def get_op(op):
    return '<'

@mm(LTE)
def get_op(op):
    return '<='

@mm(GTE)
def get_op(op):
    return '>='

@mm(NE)
def get_op(op):
    return '!='



class TypeSetFetcher(object):
    def __init__(self, typename, db):
        self.typename = typename
        self.db = db
        self.filters = []
    def __call__(self):
        query = DBObject.all()
        query.filter('type_ =', self.typename)
        query.filter('is_listed_ =', True)
        number = None
        offset = None
        for filter in self.filters:
            last = filter[-1]
            if isinstance(last, LimitFilter):
                number = last.number
                offset = last.offset
                print 'number, offset: ', (number, offset)
            else: #assumes it is a compare
                property = filter[0].property
                query.filter('%s %s'%(property, get_op(last)),last.value)
        
        if number is None:
            r = list(query)
        else:
            r = list(query.fetch(number, offset))
        for o in r:
            self.db.add_data(o)
        return [o.value_ for o in r]
        
class GQueryParser(QueryParser):
    def defaultFilter(self, node, base):
        b = self._get_base(base)
        if isinstance(b, TypeSetFetcher): #filter is after a TypeSet, so apply the filter to the typeset
            nogoogle = []
            google = []
            limit = []
            nec = None
            def ng(filter):
                nogoogle.append(filter)
                logger.warn('unable to google-fy ' + repr(filter))
            def g(filter):
                google.append(filter)
            def l(filter):
                limit.append(filter)
            for filter in node.filters:
                last = filter[-1]
                if isinstance(last, LimitFilter):
                    l(filter)
                elif isinstance(last, Compare) and len(filter) == 2 and isinstance(filter[0], GetV):
                    property = filter[0].property
                    if b.db.metas[b.typename][property].a.typename != b.typename: #This is an inherited property, so can't process (see idea in comments in top of file, though)
                        ng(filter)
                    elif isinstance(last, EQ):
                        g(filter)
                    elif (nec is None or nec == property):
                        g(filter)
                        nec = property
                    else:
                        ng(filter)
                else:
                    ng(filter)
            if len(limit) > 1:
                raise Exception('more than one limit filter in this filter!!')
            if len(nogoogle) > 0 and len(limit) > 0:
                nogoogle += limit
                logger.error('WARNING: limit statement being executed in code instead of via the datastore: ' + repr(base + (node,)))
            else:
                google += limit
            if len(nogoogle) > 0:  #if there are things we can't process, split into two and process seperately
                return QueryParser.defaultFilter(self, Filter(nogoogle), base + (Filter(google),))
            ts = TypeSetFetcher(b.typename, b.db)
            ts.filters = b.filters + google
            return ts
        else: #filter is not after a typeset, so use the default filter logic
            return QueryParser.defaultFilter(self, node, base)

def new_obj(type, value):
    obj = DBObject(key_name=mk_key(type, value), type_=type, value_=value)
    return obj
    
def mk_key(typename, value):
    return '%s_%s'%(typename, value)
    
def lookup_obj(typename, value):
    key = db.Key.from_path('DBObject', mk_key(typename, value))
    return db.get(key)
    
def _has_and_not_none(obj, propname):
    return hasattr(obj, propname) and getattr(obj, propname) is not None

class GoogleDB(object):
    
    def __init__(self, language):
        self.parser = GQueryParser(self._typeset, self._getv, self._remove_all, self._replace, self._remove, self._add, self._list, self._unlist)
        self.metas = generate_metas(language)
        
    def query(self, query):
        return self.parser.query(query)
        
    def querydata(self,query):
        return self.parser.querydata(query)
        
    def _typeset(self, typename):
        return TypeSetFetcher(typename, self)
        
    def _getv(self, set, typename, property):
        def dogetv():
            values = set()
            newvalues = []
            for v in values:
                newvalues.extend(self.dolookup(v, typename, property))
            return newvalues
        return dogetv
    
    def add_data(self, obj):
        """Takes an object that we've loaded and ships all its data up to the cache"""
        for propname, prop in self.metas[obj.type_].iteritems():  
            if isinstance(prop, PropertyStatement): #this represents a property
                if _has_and_not_none(obj, propname):
                    self.parser.add_data(exists(obj.value_, obj.type_, propname, getattr(obj, propname)))
                else:
                    self.parser.add_data(exists(obj.value_, obj.type_, propname, []))
    
    def dolookup(self, value, typename, property):
        obj = lookup_obj(typename, value)
        if property == "is_listed":
            if obj is None:
                return [False]
            self.add_data(obj)
            if not _has_and_not_none(obj, 'is_listed_'):
                return [False]
            else:
                return [obj.is_listed_]
        else:
            if obj is None: #object wasn't found, so return an empty list
                return []
            self.add_data(obj) #let's retrieve all the properties of the object while we're at it
            if not _has_and_not_none(obj, property): #obj exists but doesn't have property set
                return []
            return getattr(obj, property)
    
    def _remove_all(self, value, type, property):
        self._replace(value, type, property, [])
    
    def _replace(self, value, type, property, newvalues):  #tricky thing here is I want to do a bulk replace, but then I need to add each other half individually
        #iteratively add this object to its components if appropriate
        prop = self.metas[type][property]      
        if prop.b.kind in (KINDS.SINGLE, KINDS.PLURAL):
            for v in newvalues:
                self._add_half(v, prop.b.typename, prop.b.name, value)
    
        #then, do the bulk replace on the current object
        obj = lookup_obj(type, value)
        if obj is None:
            obj = new_obj(type, value)
        if newvalues == []:
            if hasattr(obj, property): delattr(obj, property)
        else:
            setattr(obj, property, newvalues)
        self.parser.add_data(exists(value, type, property, newvalues))
        obj.put()
        
    def _remove_half(self, obj, value, type, property, target):
        if _has_and_not_none(obj, property) and target in getattr(obj, property):
            getattr(obj, property).remove(target)
            if getattr(obj, property) == []:
                delattr(obj, property)
                self.parser.add_data(exists(value, type, property, []))
            else:
                self.parser.add_data(exists(value, type, property, getattr(obj, property)))
    
    def _remove(self, value, type, property, target):
        obj = lookup_obj(type, value)
        self._do_remove(obj, value, type, property, target)
        obj.put() #CATCH ERRORS!

            
    def _do_remove(self, obj, value, type, property, target):
        self._remove_half(obj, value, type, property, target)
        prop = self.metas[type][property]
        if prop.b.kind in (KINDS.SINGLE, KINDS.PLURAL):
            other = lookup_obj(prop.b.typename, target)
            self._remove_half(other, target, prop.b.typename, prop.b.name, value)
            other.put() #CATCH ERRORS!
    
    def _add_half(self, value, type, property, target):
        obj = lookup_obj(type, value)
        if obj is None:
            obj = new_obj(type, value)
        if not _has_and_not_none(obj, property):
            setattr(obj, property, [target])
        else:
            if target not in getattr(obj, property):
                getattr(obj, property).append(target)
        self.parser.add_data(exists(value, type, property, getattr(obj, property)))
        obj.put()
    
    def _add(self, value, type, property, target):
        self._add_half(value, type, property, target)
        prop = self.metas[type][property]
        if prop.b.kind in (KINDS.SINGLE, KINDS.PLURAL):
            self._add_half(target, prop.b.typename, prop.b.name, value)
        
    def _list(self, value, type):
        obj = lookup_obj(type, value)
        if obj is None:
            obj = new_obj(type, value)
        obj.is_listed_ = True
        obj.put()
        self.parser.add_data(is_listed(value, type, True))
        
    def _unlist(self, value, type):
        obj = lookup_obj(type, value)
        if obj is not None:
            obj.is_listed_ = False
            obj.put()
        self.parser.add_data(is_listed(value, type, False))